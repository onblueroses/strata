#!/usr/bin/env python3
"""router-combo — ARCHIVAL bake-off candidate (won the original signal bake-off; its
design was then promoted into the live hook). NOT the source of truth: it predates the
>=2-token rule, the strong-solo bypass, and LEX_SOLO_THRESH, so its lex branch routes
differently from production. Authoritative behavior lives in
`hooks/context-doc-router.py`, and `gauntlet.py` validates THAT hook, not this file.
Kept only for `run-eval.py router-combo` historical comparison; do not rely on its routing.

Original design — the layered production candidate, ALL signals in ONE pure-Python
process (no network, no sklearn) so measured latency reflects the real hook. Union of:
  - cwd-path     (marker files + path patterns)              deterministic, instant
  - recent-edits (bounded transcript tail -> ext/dir)         deterministic, instant
  - lex          (pure-Python TF-IDF over cached doc vectors) ~1ms, semantic
Deterministic signals win ties (higher base score). Tuned via env on the `tune` split."""

import sys
import json
import time
import os
import re
import math

START = time.time()
EVAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEX_CACHE = os.path.join(EVAL, ".lex-cache.json")
LEX_THRESH = float(os.environ.get("ROUTER_LEX_THRESHOLD", "0.16"))
LEX_SOLO_THRESH = float(os.environ.get("ROUTER_LEX_SOLO_THRESHOLD", "0.10"))
LEX_TOPK = int(os.environ.get("ROUTER_LEX_TOPK", "2"))
# A lex candidate must corroborate on >=2 distinct query tokens to fire (single-token
# matches are irreducibly ambiguous homonyms), OR be a single strong-solo token
# (corpus-unique, rare-in-English) firing at the relaxed solo threshold. Mirrors the
# shipped hook (context-doc-router.py) so this eval grades the router that actually ships.
LEX_MIN_TOK = 2
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
}
EDIT_PATH_RULES = [
    ("/.claude/skills", "skill-design-principles.md"),
    ("/.claude/hooks", "claude-code-patterns.md"),
    ("/workspace/", "knowledge-management.md"),
]


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
    for seg, doc in CWD_PATH_RULES:
        if seg in cwd:
            out[doc] = max(out.get(doc, 0), 0.9)
    for marker, doc in CWD_MARKERS:
        if cwd and has_marker(cwd, marker):
            out[doc] = max(out.get(doc, 0), 0.95)
    return out


def tail_lines(path, n=200):
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            data = b""
            while size > 0 and data.count(b"\n") <= n:
                step = min(4096, size)
                size -= step
                f.seek(size)
                data = f.read(step) + data
            return data.decode("utf-8", "replace").splitlines()[-n:]
    except Exception:
        return []


def recent_edit_docs(tx):
    out = {}
    if not (tx and os.path.exists(tx)):
        return out
    for line in tail_lines(tx):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        content = (obj.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if (
                isinstance(item, dict)
                and item.get("type") == "tool_use"
                and item.get("name") in ("Edit", "Write", "NotebookEdit")
            ):
                fp = (item.get("input") or {}).get("file_path") or ""
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
    cache = json.load(open(LEX_CACHE))
    idf, vecs = cache["idf"], cache["vecs"]
    solo = set(cache.get("solo", []))
    qt = toks((prompt or "")[:50_000] + " " + os.path.basename(cwd.rstrip("/")))
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
        # fire on >=2 corroborating tokens, OR a single strong-solo token at the
        # relaxed threshold (so the solo bypass can never weaken multi-token routing).
        solo_only = len(matched) < LEX_MIN_TOK and any(t in solo for t in matched)
        if len(matched) < LEX_MIN_TOK and not solo_only:
            continue
        s = sum(qv[t] * dv[t] for t in matched)
        if s >= (LEX_SOLO_THRESH if solo_only else LEX_THRESH):
            scored.append((round(s, 3), name))
    scored.sort(reverse=True)
    return {n: s for s, n in scored[:LEX_TOPK]}


def main():
    try:
        data = json.load(sys.stdin)
    except Exception as e:
        print(
            json.dumps(
                {
                    "docs": [],
                    "matcher": "router-combo",
                    "latency_ms": 0,
                    "error": str(e),
                }
            )
        )
        return
    prompt = data.get("prompt") or ""
    cwd = data.get("cwd") or ""
    merged = {}
    for src, sig in (
        (cwd_path_docs(cwd), "cwd-path"),
        (recent_edit_docs(data.get("transcript_path")), "recent-edits"),
        (lex_docs(prompt, cwd), "lex"),
    ):
        for name, score in src.items():
            if name not in merged or score > merged[name][0]:
                merged[name] = (score, sig)
    docs = [
        {"name": n, "score": s, "signal": sig}
        for n, (s, sig) in sorted(merged.items(), key=lambda kv: -kv[1][0])
    ]
    print(
        json.dumps(
            {
                "docs": docs,
                "matcher": "router-combo",
                "latency_ms": int((time.time() - START) * 1000),
            }
        )
    )


if __name__ == "__main__":
    main()
