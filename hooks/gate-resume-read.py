#!/usr/bin/env python3
"""Read-gate body — invoked by gate-resume-read.sh ONLY when a post-compaction
sentinel exists for this session. Blocks consequential tools until EVERY
session save listed in the sentinel has been Read *since* the compaction.

Generalizes the router thesis: injected recovery context lands only if it is
both compelling AND enforced. session-post-compaction-restore.sh injects the
"read these first" map (compelling); this gate makes the first consequential
action wait until the model actually opened it (enforced).

Contract (matches the repo's PreToolUse deny convention):
  - allow  -> exit 0 (silent)
  - block  -> print {"result":"block","reason":...} to stdout, exit 2
Any unexpected error fails OPEN (exit 0) so a gate bug can never brick a
session. The TTL is the second backstop; read-only tools are the third.

argv[1] = sentinel path. hookData JSON on stdin.
"""

import sys
import os
import json
import time
import datetime
from typing import NoReturn  # noqa: F401  (used in allow()/block() return annotations)

TTL_SEC = 30 * 60  # anti-deadlock: an unread sentinel auto-expires
TAIL = 400  # transcript lines scanned for the save read
# read-only / orientation tools are never gated (defense-in-depth; the settings.json
# matcher already excludes them, but a future matcher widening must not deadlock reads).
# Strictly read-only: a Read of the save is the only thing that clears the gate, so the
# exemptions stay narrow — no write/dispatch tool sits here.
ALLOW_TOOLS = {"Read", "Glob", "Grep", "NotebookRead"}


def allow() -> NoReturn:
    sys.exit(0)


def block(saves) -> NoReturn:
    primary = sorted(saves) if saves else []
    reads = "\n".join(f"  Read {p}" for p in primary) or "  Read your session save file"
    reason = (
        "POST-COMPACTION READ-GATE — read your session save before acting.\n"
        "You just resumed from a compaction. The recovery block injected at "
        "SessionStart points at a session-specific save that names the active "
        "spec, the handoff, and the exact files + line ranges to open next. "
        "Open it now:\n"
        f"{reads}\n"
        "Then open the files its `## Read On Resume` / `## Active Specs` "
        "block lists. This gate clears itself automatically once every listed "
        "save is Read; read-only tools (Read/Grep/Glob) stay open, and it "
        "self-expires after 30 minutes regardless."
    )
    print(json.dumps({"result": "block", "reason": reason}))
    sys.exit(2)


def parse_ts(s):
    if not isinstance(s, str):
        return None
    try:
        return datetime.datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def saves_read_since(tx, saves, since):
    """Return the subset of `saves` the transcript shows as Read (tool_use) with
    a timestamp at/after the compaction boundary. Unparseable-timestamp entries
    do NOT count (a pre-compaction read must not satisfy the gate)."""
    read = set()
    if not (isinstance(tx, str) and tx and os.path.exists(tx)):
        return read
    try:
        lines = open(tx, encoding="utf-8", errors="replace").read().splitlines()[-TAIL:]
    except Exception:
        return read
    # require the Read strictly at/after the sentinel creation (compaction boundary).
    # No negative skew: filesystem mtime and transcript timestamps share one machine
    # clock, so a tolerance would only let a pre-compaction read clear the gate.
    floor = since
    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue
        try:
            o = json.loads(ln)
        except Exception:
            continue
        ts = parse_ts(o.get("timestamp"))
        if ts is None or ts < floor:
            continue
        content = (o.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for it in content:
            if (
                isinstance(it, dict)
                and it.get("type") == "tool_use"
                and it.get("name") == "Read"
            ):
                fp = (it.get("input") or {}).get("file_path", "")
                if fp in saves:
                    read.add(fp)
    return read


def main():
    sentinel = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        mtime = os.path.getmtime(sentinel)
    except Exception:
        allow()  # no sentinel -> nothing to gate (race with clear; fail open)

    # TTL backstop: a stale gate frees itself so a session can never be bricked.
    if time.time() - mtime > TTL_SEC:
        try:
            os.remove(sentinel)
        except Exception:
            pass
        allow()

    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except Exception:
        allow()
    tool = data.get("tool_name") or ""
    tx = data.get("transcript_path") or ""

    if tool in ALLOW_TOOLS:
        allow()

    try:
        saves = {p.strip() for p in open(sentinel).read().splitlines() if p.strip()}
    except Exception:
        allow()
    if not saves:
        allow()

    remaining = saves - saves_read_since(tx, saves, mtime)
    if not remaining:
        try:
            os.remove(sentinel)  # every listed save read: clear so steady state resumes
        except Exception:
            pass
        allow()

    block(remaining)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # absolute backstop: a gate bug must never block the user. Fail open.
        sys.exit(0)
