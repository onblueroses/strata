#!/usr/bin/env python3
"""context-doc-router v2 — UserPromptSubmit hook.

Routes reference docs by WORK CONTEXT, not prompt vocabulary:
  cwd-path (markers + path patterns) + recent-edits (transcript tail) + lex (pure-py TF-IDF).
Winner of the .router-eval bake-off (aggregate F1 0.792 vs 0.10 for the old keyword router).

Contract: reads hookData JSON on stdin, prints a `REFERENCE DOCS:` block on stdout when docs
match, exits 0 silently otherwise. NEVER crashes, never writes stderr, never exceeds the
2000ms hook budget (combo is ~75ms). All failure paths degrade to a clean exit 0.
"""

import sys
import json
import os
import re
import math
import datetime
import hashlib
import tempfile

# STRATA_HOME is exported by the install (see CONFIG.md); fall back to the install
# tree derived from this hook's own location (hooks/ sits directly under STRATA_HOME)
# so the router still resolves its docs when STRATA_HOME is unset.
STRATA_HOME = os.environ.get("STRATA_HOME") or os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)
REF = os.path.join(STRATA_HOME, "reference")
EVAL = os.path.join(REF, ".router-eval")
LEX_CACHE = os.path.join(EVAL, ".lex-cache.json")
# Env overrides exist for the gauntlet only: hermetic runs point both at scratch files
# so tests never write the real log or depend on live registry contents. Unset in
# production (the hook chain sets neither), so the defaults below are the live paths.
LOG = os.environ.get("DOC_ROUTER_LOG") or os.path.join(EVAL, "injection-log.jsonl")
SUPPRESS_FILE = os.environ.get("DOC_ROUTER_SUPPRESS") or os.path.join(
    EVAL, "suppressed-docs.json"
)


def load_suppressed():
    # Data-driven suppression of measured-dead docs: a doc that keeps routing but a
    # retrieval eval shows is never actually used can be listed here to drop it from
    # routing. A registry FILE, not a hardcoded set, so the list is tunable without code
    # edits and revisitable once a real retrieval eval exists. Ships EMPTY in this
    # skeleton; populate it from your own measured injection-log. Fail-open:
    # unreadable/malformed -> suppress nothing. A hand-edited non-list (e.g. a bare
    # string) would iterate as characters, so guard the type before comprehending.
    try:
        with open(SUPPRESS_FILE) as f:
            d = json.load(f)
        names = d.get("suppressed")
        if not isinstance(names, list):
            return set()
        return {n for n in names if isinstance(n, str)}
    except Exception:
        return set()


def _lex_thresh():
    # Guard the parse: a non-numeric ROUTER_LEX_THRESHOLD must fall back to the
    # default, never raise at import time (module-level raises bypass main()'s
    # backstop and would break the user's prompt with a traceback).
    try:
        return float(os.environ.get("ROUTER_LEX_THRESHOLD", "0.16"))
    except (TypeError, ValueError):
        return 0.16


def _lex_solo_thresh():
    # A solo (corpus-unique, rare-in-English, len>=5) token has already passed the
    # precision filter that the >=2-token rule enforces for everyone else, so it may
    # fire at a lower cosine. A bare "vitest"/"waybar" prompt scores ~0.12-0.15 against
    # its big home doc (one rare keyword among many), just under LEX_THRESH; this
    # recovers those. Applies ONLY to the solo-bypass path, so it never weakens
    # multi-token routing. Same import-safe guard as _lex_thresh.
    try:
        return float(os.environ.get("ROUTER_LEX_SOLO_THRESHOLD", "0.10"))
    except (TypeError, ValueError):
        return 0.10


LEX_THRESH = _lex_thresh()
LEX_SOLO_THRESH = _lex_solo_thresh()
LEX_TOPK = 2
# A lex candidate must match at least this many DISTINCT query tokens to fire.
# Single-token matches are irreducibly ambiguous (homonyms: "prime rib" vs "prime
# intellect", "node on my network" vs node.js) and let one rare high-IDF token
# dominate the cosine. The deterministic cwd/recent-edit signals carry the legit
# single-strong-keyword cases, so demanding corroboration costs ~0 recall.
LEX_MIN_TOK = 2
MAX_INJECT = 3
STOP = set(
    "the a an and or of to in for on with is are be this that it as at by from your you "
    "i we my our use using used setup set up add new run check make help me can do "
    "how want really today getting into over".split()
)

CWD_PATH_RULES = [
    ("/.claude/skills", "skill-design-principles.md"),
    ("/.claude/hooks", "claude-code-patterns.md"),
    ("/.claude", "claude-code-patterns.md"),
    ("/workspace", "knowledge-management.md"),
]
CWD_MARKERS = [
    ("Cargo.toml", "rust-ai-project-setup.md"),
    ("package.json", "nodejs-typescript-setup.md"),
]
EXT_RULES = {
    ".rs": "rust-ai-project-setup.md",
    ".ts": "nodejs-typescript-setup.md",
    ".tsx": "nodejs-typescript-setup.md",
    ".js": "nodejs-typescript-setup.md",
    ".jsx": "nodejs-typescript-setup.md",
}
EDIT_PATH_RULES = [
    ("/.claude/skills", "skill-design-principles.md"),
    ("/.claude/hooks", "claude-code-patterns.md"),
    ("/workspace/", "knowledge-management.md"),
]
# mandatory docs: force-inject when their context marker is present (keyword-independent)
MANDATORY = {"rust-ai-project-setup.md": ("Cargo.toml", "marker")}


def has_marker(cwd, fname, depth=6):
    d = cwd
    for _ in range(depth):
        if os.path.exists(os.path.join(d, fname)):
            return True
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    return False


def cwd_path_docs(cwd):
    out = {}
    if not isinstance(cwd, str) or not cwd:
        return out
    # segment-accurate match (append "/" so "/workspace" matches ".../workspace" but not ".../myworkspace");
    # rules are most-specific-first, break on first hit so "/.claude/skills" doesn't also fire "/.claude"
    probe = cwd.rstrip("/") + "/"
    for seg, doc in CWD_PATH_RULES:
        if (seg + "/") in probe:
            out[doc] = 0.9
            break
    for marker, doc in CWD_MARKERS:
        if has_marker(cwd, marker):
            out[doc] = max(out.get(doc, 0), 0.95)
    return out


def tail_lines(path, n=200, max_bytes=262_144):
    # Read at most the last max_bytes in ONE seek+read, then take the last n lines.
    # Bounding by BYTES (not by newline count) is the budget-safe direction: Claude
    # transcript JSONL lines can be huge (tool outputs / pasted content inline), so a
    # scan-back-until-200-newlines could read hundreds of MB (with O(n^2) prepend) and
    # blow the 2000ms budget, losing every route. 256KB holds many recent tool events.
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            f.seek(max(0, size - max_bytes))
            data = f.read(max_bytes)
        return data.decode("utf-8", "replace").splitlines()[-n:]
    except Exception:
        return []


def recent_edit_docs(tx):
    out = {}
    if not (isinstance(tx, str) and tx and os.path.exists(tx)):
        return out
    for line in tail_lines(tx):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue  # a valid JSON line that isn't an object (e.g. "[]") must not raise
        msg = obj.get("message")
        content = msg.get("content") if isinstance(msg, dict) else None
        if not isinstance(content, list):
            continue
        for item in content:
            if (
                isinstance(item, dict)
                and item.get("type") == "tool_use"
                and item.get("name") in ("Edit", "Write", "MultiEdit", "NotebookEdit")
            ):
                inp = item.get("input")
                fp = (inp.get("file_path") if isinstance(inp, dict) else "") or ""
                ext = os.path.splitext(fp)[1].lower()
                if ext in EXT_RULES:
                    out[EXT_RULES[ext]] = max(out.get(EXT_RULES[ext], 0), 0.85)
                for seg, doc in EDIT_PATH_RULES:
                    if seg in fp:
                        out[doc] = max(out.get(doc, 0), 0.85)
    return out


def toks(text):
    return [
        t
        for t in re.split(r"[^a-z0-9]+", text.lower())
        if len(t) >= 3 and t not in STOP
    ]


def lex_docs(prompt, cwd):
    if not os.path.exists(LEX_CACHE):
        return {}
    try:
        cache = json.load(open(LEX_CACHE))
        idf, vecs = cache["idf"], cache["vecs"]
        solo = set(cache.get("solo", []))
    except Exception:
        return {}
    # Bound the tokenized prompt: routing signal saturates well before 50k chars, and
    # this keeps a huge prompt from blowing the 2000ms budget at tokenize time (the
    # deterministic cwd/recent-edit signals do not depend on prompt size at all).
    base = (
        (prompt or "")[:50_000]
        + " "
        + (os.path.basename(cwd.rstrip("/")) if isinstance(cwd, str) else "")
    )
    qt = toks(base)
    if not qt:
        return {}
    qtf = {}
    for t in qt:
        qtf[t] = qtf.get(t, 0) + 1
    qv = {t: (f / len(qt)) * idf.get(t, 0) for t, f in qtf.items()}
    qn = math.sqrt(sum(x * x for x in qv.values())) or 1.0
    qv = {t: x / qn for t, x in qv.items()}
    scored = []
    for name, dv in vecs.items():
        matched = [t for t in dv if qv.get(t, 0) > 0]
        # fire on >=2 corroborating tokens (reject single-token homonyms) OR a single
        # strong-solo token (corpus-unique non-dictionary term, e.g. "hyprland")
        solo_only = len(matched) < LEX_MIN_TOK and any(t in solo for t in matched)
        if len(matched) < LEX_MIN_TOK and not solo_only:
            continue
        s = sum(qv[t] * dv[t] for t in matched)
        # solo-only matches use the relaxed threshold; multi-token matches keep the
        # full bar, so the relaxed threshold cannot weaken normal routing.
        if s >= (LEX_SOLO_THRESH if solo_only else LEX_THRESH):
            scored.append((round(s, 3), name))
    scored.sort(reverse=True)
    return {n: s for s, n in scored[:LEX_TOPK]}


def valid_doc(name):
    """A routable doc is a plain .md basename that actually exists under REF.
    Rejects a poisoned cache doc name (path traversal) and drops a retired doc
    whose file is gone (catalog/cache drift) instead of injecting a dead reference."""
    return (
        isinstance(name, str)
        and name.endswith(".md")
        and "/" not in name
        and "\\" not in name
        and not name.startswith(".")
        and os.path.isfile(os.path.join(REF, name))
    )


def quick_nav(doc):
    if not valid_doc(doc):
        return None
    path = os.path.join(REF, doc)
    try:
        lines = open(path).read().splitlines()
    except Exception:
        return None
    out, found = [], False
    for ln in lines:
        if ln.startswith("## Quick Nav"):
            found = True
            continue
        if found and ln.startswith("## "):
            break
        if found:
            out.append(ln)
    out = [x for x in out if x.strip()][:12]
    return "\n".join(out) if out else None


def _seen_path(session):
    # Readable sanitized prefix + full-session hash suffix: a [:N] prefix alone collided
    # for ids sharing the first N chars (one session could suppress another's docs).
    # Sanitizing also blocks a crafted session_id from path-injecting the filename.
    raw = str(session or "default")
    safe = re.sub(r"[^A-Za-z0-9_-]", "", raw)[:32] or "x"
    h = hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()[:16]
    return f"/tmp/claude-doc-router-{safe}-{h}.json"


def read_seen(flag):
    # Coerce to {doc_name: finite_float} only. A corrupt/poisoned flag value (e.g. a
    # string or NaN) must read as "unseen", never raise into the routing path.
    try:
        with open(flag) as f:
            s = json.load(f)
    except Exception:
        return {}
    if not isinstance(s, dict):
        return {}
    out = {}
    for k, v in s.items():
        # Per-entry guard that cannot raise: a huge JSON int (10**1000) overflows
        # float() in math.isfinite; NaN/+-Inf fail isfinite; bool/str/list are excluded.
        # Any bad entry is skipped, legit dedup state is preserved.
        try:
            if (
                isinstance(k, str)
                and isinstance(v, (int, float))
                and not isinstance(v, bool)
            ):
                fv = float(v)
                if math.isfinite(fv):
                    out[k] = fv
        except Exception:
            continue
    return out


def write_seen(flag, seen):
    # Unique temp via mkstemp (O_EXCL + random name): no predictable path for a symlink
    # to disable the write, and no collision between concurrent writers. os.replace does
    # NOT follow a symlinked flag (it swaps the name), so it can't clobber a link target.
    tmp = None
    try:
        fd, tmp = tempfile.mkstemp(
            dir="/tmp", prefix="claude-doc-router.", suffix=".tmp"
        )
        with os.fdopen(fd, "w") as f:
            json.dump(seen, f)
        os.replace(tmp, flag)
        tmp = None
    except Exception:
        if tmp:
            try:
                os.unlink(tmp)
            except Exception:
                pass


def log_rows(rows):
    # Persistent observability log (rotated so it never grows without limit). Each row is
    # a pre-shaped dict -> one JSONL line. Privacy: callers pass plen, never prompt text.
    # Wrapped so a log failure (full disk, perms) never breaks routing or the prompt.
    try:
        if os.path.exists(LOG) and os.path.getsize(LOG) > 1_000_000:
            with open(LOG) as lf:
                keep = lf.readlines()[-2000:]
            with open(LOG, "w") as lf:
                lf.writelines(keep)
        with open(LOG, "a") as lf:
            for r in rows:
                lf.write(json.dumps(r) + "\n")
    except Exception:
        pass


def main():
    # Generous read ceiling: a realistic prompt (even a multi-MB paste) parses fine and
    # still routes ALL signals incl. the deterministic cwd/recent-edit ones. The expensive
    # path (lex tokenization) is bounded separately, so a large prompt stays in budget.
    # Only a >20MB payload (pathological) truncates and degrades to a clean no-route.
    raw = sys.stdin.read(20_000_000) if not sys.stdin.isatty() else ""
    if not raw.strip():
        return
    try:
        data = json.loads(raw)
    except Exception:
        return
    prompt = data.get("prompt")
    if not isinstance(prompt, str):
        prompt = ""
    cwd = data.get("cwd") if isinstance(data.get("cwd"), str) else ""
    tx = data.get("transcript_path")
    # Coerce to str at the source: a non-string session_id (e.g. a numeric JSON value)
    # would otherwise raise on session[:8] / _seen_path slicing. Keeping it a str here
    # makes every downstream use (dedup flag, log rows) safe.
    session = str(data.get("session_id") or "default")

    def _safe(fn, *a):
        # Isolate each signal: a raising matcher (e.g. a structurally corrupt lex cache)
        # degrades to an empty result for THAT signal only, never suppressing the others.
        try:
            return fn(*a)
        except Exception:
            return {}

    merged = {}
    for src, sig in (
        (_safe(cwd_path_docs, cwd), "cwd-path"),
        (_safe(recent_edit_docs, tx), "recent-edits"),
        (_safe(lex_docs, prompt, cwd), "lex"),
    ):
        for name, score in src.items():
            if name not in merged or score > merged[name][0]:
                merged[name] = (score, sig)
    # measured-dead docs drop out here, BEFORE mandatory: an explicit context-marker
    # force-inject outranks the suppression registry by design.
    suppressed = load_suppressed()
    dropped_suppressed = [n for n in merged if n in suppressed]
    for n in dropped_suppressed:
        del merged[n]
    # mandatory force-inject (keyword-independent)
    for doc, (marker, kind) in MANDATORY.items():
        if kind == "marker" and cwd and has_marker(cwd, marker):
            merged.setdefault(doc, (0.95, "mandatory"))
    # A doc that was suppressed but then mandatory-reinjected is NOT actually dropped;
    # keep only docs still absent from the final candidates so the "suppressed"
    # signal/field never records a drop that did not happen.
    dropped_suppressed = [n for n in dropped_suppressed if n not in merged]

    flag = _seen_path(session)
    seen = read_seen(flag)
    fresh = {
        n: (sc, sg) for n, (sc, sg) in merged.items() if sc > seen.get(n, 0) + 1e-9
    }
    ranked = sorted(fresh.items(), key=lambda kv: -kv[1][0])
    ranked = [(n, v) for n, v in ranked if valid_doc(n)][:MAX_INJECT]
    if not ranked:
        # Zero-route: a substantive prompt that fired no doc. Log it (plen only, never the
        # prompt text) so the zero-route RATE is measurable -- the data that decides
        # whether a semantic/embedding fallback earns its keep. Distinguish a TRUE
        # zero-route (no doc matched any signal -> a fallback candidate) from a dedup-
        # suppressed route (a relevant doc matched but already fired this session -> the
        # doc already reached the model, NOT a fallback candidate); conflating them would
        # inflate the rate the decision rests on. Skip blank/whitespace prompts.
        if prompt.strip():
            # Three distinguishable absences (conflating them corrupts the zero-route
            # rate any fallback decision rests on): "deduped" = a valid doc matched but
            # already fired this session; "suppressed" = only registry-dead docs matched
            # (sole cause; co-injection cases ride the "suppressed" field on injected
            # rows below); "none" = nothing valid matched, a true zero-route / fallback
            # candidate. Keyed on valid_doc, NOT raw merged: an invalid/drift match must
            # not masquerade as deduped.
            if any(valid_doc(n) for n in merged):
                zero_signal = "deduped"
            elif any(valid_doc(n) for n in dropped_suppressed):
                zero_signal = "suppressed"
            else:
                zero_signal = "none"
            log_rows(
                [
                    {
                        "ts": datetime.datetime.now().isoformat(timespec="seconds"),
                        "session": session[:8],
                        "doc": None,
                        "signal": zero_signal,
                        "work_context": zero_signal,
                        "plen": len(prompt),
                        "cwd": cwd[-120:],
                    }
                ]
            )
        return
    # Build and EMIT the block first; commit the dedup state only AFTER a successful
    # write+flush. If delivery fails (broken pipe / interrupt) the docs stay unseen and
    # re-fire next prompt -- prefer a duplicate injection over a silent permanent loss.
    out = [
        "REFERENCE DOCS — routed by work-context. Read the ones that fit; skip those that don't.\n"
    ]
    for name, (score, sig) in ranked:
        out.append(f"=== {name} ===  (why: {sig} match, score {score})")
        out.append(f"→ Read `{REF}/{name}` — it covers this; jump via its Quick Nav.")
        nav = quick_nav(name)
        out.append(nav if nav else "(no Quick Nav — read the full doc)")
        out.append("")
    sys.stdout.write("\n".join(out))
    sys.stdout.flush()  # surface a broken-pipe failure BEFORE committing seen-state

    # commit dedup state only after successful emission
    for name, (score, sig) in ranked:
        seen[name] = score
    write_seen(flag, seen)

    # persistent log (observability) -- one row per fired doc (prompt text never logged;
    # plen + cwd only). cwd makes the matched deterministic rule derivable offline (the
    # cwd/edit rule tables are first-match static), so a cwd-path injection stays
    # attributable to a specific rule after the fact. The "suppressed" field carries
    # registry drops that co-occurred with an injection -- without it the zero-route
    # branch alone undercounts suppression cost (a doc dropped beside a successful
    # injection would be logged nowhere). Field, not extra rows: unify counts doc/null
    # rows into its rate denominators, so a new row kind would skew every fraction.
    ts = datetime.datetime.now().isoformat(timespec="seconds")
    sup_note = {"suppressed": dropped_suppressed} if dropped_suppressed else {}
    log_rows(
        [
            {
                "ts": ts,
                "session": session[:8],
                "doc": name,
                "signal": sig,
                "work_context": sig,
                "score": score,
                "plen": len(prompt),
                "cwd": cwd[-120:],
                **sup_note,
            }
            for name, (score, sig) in ranked
        ]
    )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # absolute backstop: a router bug must never break the user's prompt
        pass
    sys.exit(0)
