#!/usr/bin/env python3
"""Unify all opt-in telemetry streams into one normalized, time-sorted JSONL stream.

Read-time merger (the "shared place"): folds the live sink (events.jsonl) plus the
other runtime streams into a common envelope so analysis reads ONE surface. Non-invasive:
each emitter keeps its own log; this just brings them together on read. Idempotent.

This is a reader. It runs on demand and makes no assumption that telemetry is enabled;
absent streams simply contribute nothing. (Emission is opt-in via STRATA_TELEMETRY=1.)

  python3 unify.py            -> normalized JSONL on stdout (time-sorted)
  python3 unify.py --counts   -> same, plus a kind/source tally to stderr
  python3 unify.py --out F     -> write to F instead of stdout

Envelope: {"ts","sid","kind","source", ...kind-fields}
"""

import sys
import os
import json
import glob
import argparse
import subprocess


def out_path_is_safe(path):
    """Refuse dumping the unified stream (it can carry raw query text) to a git-TRACKED path;
    the install tree may be a tracked repo with a remote. Refuse a symlinked destination and
    resolve to the REAL target before asking git (a lexical-path guard is bypassable via an
    ignored symlink pointing at a tracked file). Fail CLOSED: a git error on a path inside a
    work tree refuses rather than risk a leak."""
    raw = os.path.expanduser(path)
    if os.path.islink(raw):
        return False  # a symlinked export destination is refused outright
    target = os.path.realpath(raw)
    parent = os.path.dirname(target) or "."
    try:
        inside = subprocess.run(
            ["git", "-C", parent, "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except Exception:
        return False  # cannot determine repo status -> fail closed
    if inside.returncode != 0 or inside.stdout.strip() != "true":
        return True  # outside any git work tree -> safe to write
    try:
        chk = subprocess.run(
            ["git", "-C", parent, "check-ignore", "-q", target],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except Exception:
        return False  # inside a work tree and git failed -> fail closed
    return chk.returncode == 0  # 0 = gitignored (safe); else tracked -> refuse


# Runtime path contract (matches telemetry-emit.sh + the lane wrappers).
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STRATA_HOME = os.environ.get("STRATA_HOME") or os.path.dirname(_SCRIPT_DIR)
KB_DIR = os.environ.get("KB_DIR") or f"{STRATA_HOME}/workspace"
STATE_DIR = os.environ.get("STATE_DIR") or f"{KB_DIR}/state"
TEL_DIR = os.environ.get("STRATA_TELEMETRY_DIR") or f"{STATE_DIR}/telemetry"

SOURCES = {
    "injection-log": f"{STRATA_HOME}/reference/.router-eval/injection-log.jsonl",
    "lifecycle": f"{STATE_DIR}/logs/lifecycle-events.jsonl",
    "skill-runs": f"{STATE_DIR}/skill-runs.jsonl",
    "live": f"{TEL_DIR}/events.jsonl",  # MUST equal the emitter's sink
}
SESSION_EVENTS_GLOB = f"{STATE_DIR}/session-events-*.jsonl"

LIFECYCLE_KIND = {
    "PostToolUseFailure": "tool_fail",
    "SubagentStop": "subagent_stop",
    "SessionEnd": "session_end",
    "TaskCreated": "task_created",
    "TaskCompleted": "task_completed",
    "PostCompact": "post_compact",
}


def norm(source, obj):
    """Map one raw record from `source` to the common envelope, or None to drop it."""
    if not isinstance(obj, dict):
        return None
    if source == "injection-log":
        doc = obj.get("doc")
        return {
            "ts": obj.get("ts"),
            "sid": obj.get("session"),
            "source": source,
            "kind": "doc_inject" if doc else "doc_zero_route",
            "doc": doc,
            "signal": obj.get("signal"),
            "work_context": obj.get("work_context"),
            "score": obj.get("score"),
            "plen": obj.get("plen"),
        }
    if source == "lifecycle":
        ev = obj.get("event", "unknown")
        return {
            "ts": obj.get("ts"),
            "sid": obj.get("session_id"),
            "source": source,
            "kind": LIFECYCLE_KIND.get(
                ev, ev.lower() if isinstance(ev, str) else "unknown"
            ),
        }
    if source == "skill-runs":
        return {
            "ts": obj.get("ts"),
            "sid": obj.get("sid"),
            "source": source,
            "kind": "skill_run",
            "skill": obj.get("skill"),
            "loaded": obj.get("loaded"),
        }
    if source == "session-events":
        t = obj.get("type", "event")
        e = {"ts": obj.get("ts"), "sid": obj.get("sid"), "source": source, "kind": t}
        for k in ("file", "msg", "text", "what", "why", "claim", "status"):
            if k in obj:
                e[k] = obj[k]
        return e
    if source == "live":  # already enveloped
        obj.setdefault("source", "live")
        return obj
    return None


def read_jsonl(path):
    try:
        with open(path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except Exception:
                    continue  # telemetry is best-effort: skip a malformed/partial line, never abort the merge
    except FileNotFoundError:
        return
    except Exception:
        return  # a stream that can't be read (perms/encoding) drops out of the view, never crashes analysis


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--counts", action="store_true")
    ap.add_argument("--out")
    args = ap.parse_args()

    if args.out and not out_path_is_safe(args.out):
        print(
            f"unify.py: refusing --out {args.out}: it is inside a git work tree and not gitignored, "
            "and the unified stream contains raw query text. Emitting to stdout instead.",
            file=sys.stderr,
        )
        args.out = None

    events = []
    for source, path in SOURCES.items():
        for obj in read_jsonl(path):
            e = norm(source, obj)
            if e and e.get("ts"):
                events.append(e)
    for path in glob.glob(SESSION_EVENTS_GLOB):
        for obj in read_jsonl(path):
            e = norm("session-events", obj)
            if e and e.get("ts"):
                events.append(e)

    events.sort(key=lambda e: str(e.get("ts")))

    out = open(args.out, "w") if args.out else sys.stdout
    for e in events:
        out.write(json.dumps(e) + "\n")
    if args.out:
        out.close()

    if args.counts:
        from collections import Counter

        kinds, sources = Counter(), Counter()
        for e in events:
            kinds[e["kind"]] += 1
            sources[e["source"]] += 1
        print(
            f"\n[unify] {len(events)} events from {len(sources)} sources",
            file=sys.stderr,
        )
        print("  by source:", dict(sources.most_common()), file=sys.stderr)
        print("  by kind:  ", dict(kinds.most_common()), file=sys.stderr)


if __name__ == "__main__":
    main()
