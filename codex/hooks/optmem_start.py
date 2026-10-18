#!/usr/bin/env python3
"""SessionStart: inject the OptMem wake document and Codex's memory authority."""
import json, os, re, shlex, subprocess, sys
from pathlib import Path

MEMO = Path(os.environ.get("OPTMEM_MEMO_PATH", str(Path.home() / "Work/optmem/memo")))
MEMORY_DIR = Path(os.environ.get("OPTMEM_MEMORY_DIR", Path.home() / ".optmem" / "memory"))
# The measured wake budget of the production Claude hook; the 5 s hook timeout wraps it.
WAKE_TIMEOUT = 3.867
SESSION_SCOPE = re.compile(r"^[a-z0-9]{8}$", re.ASCII)
AUTHORITY = (
    "CODEX OPTMEM AUTHORITY: a user-facing primary Codex session may call memo note and "
    "memo nap under knowledge-management.md, with the same authority as primary Claude. "
    "Delegated agents may wake or recall, but return candidates to their primary and never "
    "settle memory directly."
)


# Set by codex-fast/codex-strong. A delegate returns candidates and never settles memory, so the
# nap handover that memo wake appends is cut rather than shown as an order (a ticket).
DELEGATE = os.environ.get("OPTMEM_ROLE") == "delegate"
NAP = re.compile(r"^(Cannot wake:|Compress memories #)", re.M)


def without_nap(text: str) -> str:
    match = NAP.search(text) if DELEGATE else None
    return text if match is None else text[:match.start()].rstrip()


def emit(context: str) -> int:
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart", "additionalContext": context,
    }}, separators=(",", ":")))
    return 0


def header() -> str:
    try:
        raw = json.load(sys.stdin).get("session_id")
    except BaseException:
        raw = None
    scope = raw[:8] if isinstance(raw, str) else ""
    if SESSION_SCOPE.fullmatch(scope):
        return (f"SESSION SCOPE: @s/{scope}\nUse this token verbatim for session-scoped "
                "notes, candidates, and Linear claims.")
    return ("SESSION SCOPE: unresolved\nDo not guess a session scope; report that the hook "
            "payload did not provide one.")


def main() -> int:
    top = header()
    manual = f"env MEMORY_DIR={shlex.quote(str(MEMORY_DIR))} {shlex.quote(str(MEMO))} wake"
    if not os.access(MEMO, os.X_OK):
        return emit(f"{top}\n\nOPTMEM WAKE FAILURE: no executable at {MEMO}. "
                    f"Run the read-only command by hand: {manual}")
    if not (MEMORY_DIR / "LOG.txt").is_file() or not (MEMORY_DIR / "TREE").is_dir():
        return emit(f"{top}\n\nOPTMEM WAKE FAILURE: store incomplete at {MEMORY_DIR}. "
                    f"Run by hand after repairing the store: {manual}")
    try:
        done = subprocess.run([str(MEMO), "wake"], check=False, text=True, capture_output=True,
                              env={**os.environ, "MEMORY_DIR": str(MEMORY_DIR)},
                              timeout=WAKE_TIMEOUT)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return emit(f"{top}\n\nOPTMEM WAKE FAILURE: {exc}. Run by hand: {manual}")

    output = without_nap((done.stdout or done.stderr).strip())
    if done.returncode == 0 and "You are awake." in output.splitlines():
        return emit(f"{top}\n\n{AUTHORITY}\n\n{output}")
    detail = output or f"memo wake exited with status {done.returncode} and no output"
    return emit(f"{top}\n\n{AUTHORITY}\n\nOPTMEM WAKE UNAVAILABLE: {detail}\n\n"
                "Treat memory as unavailable, report the condition, and continue from current "
                "files, AGENTS.md and Linear. Do not settle or append OptMem meanwhile.")


if __name__ == "__main__":
    raise SystemExit(main())
