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


def _has_git_metadata_ancestor(path):
    current = os.path.realpath(path)
    while True:
        marker = os.path.join(current, ".git")
        try:
            if os.path.isfile(marker):
                return True
            if os.path.isdir(marker):
                entries = set(os.listdir(marker))
                if "HEAD" in entries or "commondir" in entries:
                    return True
        except OSError:
            return True
        parent = os.path.dirname(current)
        if parent == current:
            return False
        current = parent


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
    if not os.path.isdir(parent):
        return False
    git_env = os.environ.copy()
    for key in (
        "GIT_CEILING_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_DIR",
        "GIT_INDEX_FILE",
        "GIT_WORK_TREE",
    ):
        git_env.pop(key, None)
    try:
        top = subprocess.run(
            ["git", "-C", parent, "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
            env=git_env,
        )
    except Exception:
        return not _has_git_metadata_ancestor(parent)
    if top.returncode != 0:
        return not _has_git_metadata_ancestor(parent)
    toplevel = top.stdout.strip()
    if not toplevel:
        return False
    rel_target = os.path.relpath(target, os.path.realpath(toplevel))
    if rel_target == ".." or rel_target.startswith(f"..{os.sep}"):
        return False
    try:
        chk = subprocess.run(
            ["git", "-C", toplevel, "check-ignore", "-q", "--", rel_target],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            env=git_env,
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
    "skill-runs": f"{STATE_DIR}/skill-runs.jsonl",
    "live": f"{TEL_DIR}/events.jsonl",  # MUST equal the emitter's sink
}
# Sink-append failures the emitter could not write to the live stream land here as
# already-enveloped telemetry_error rows; fold them in so a dropping instrument surfaces.
TELEMETRY_ERRORS = f"{TEL_DIR}/telemetry-errors.jsonl"
SESSION_EVENTS_GLOB = f"{STATE_DIR}/session-events-*.jsonl"


def norm(source, obj):
    """Map one raw record from `source` to the common envelope, or None to drop it."""
    if not isinstance(obj, dict):
        return None
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
    for obj in read_jsonl(TELEMETRY_ERRORS):
        # already enveloped (ts/sid/kind/source) like events.jsonl -> norm("live") passes through
        e = norm("live", obj)
        if e and e.get("ts"):
            events.append(e)

    events.sort(key=lambda e: str(e.get("ts")))

    try:
        out = open(args.out, "w") if args.out else sys.stdout
    except OSError as exc:
        print(f"unify.py: cannot open --out {args.out}: {exc}", file=sys.stderr)
        return 1
    for e in events:
        out.write(json.dumps(e) + "\n")
    if args.out:
        out.close()

    if args.counts:
        from collections import Counter

        kinds, sources = Counter(), Counter()
        for e in events:
            kinds[e.get("kind", "?")] += 1
            sources[e.get("source", "?")] += 1
        print(
            f"\n[unify] {len(events)} events from {len(sources)} sources",
            file=sys.stderr,
        )
        print("  by source:", dict(sources.most_common()), file=sys.stderr)
        print("  by kind:  ", dict(kinds.most_common()), file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
