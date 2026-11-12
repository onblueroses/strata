#!/usr/bin/env python3
"""SessionStart: inject the OptMem wake document and Codex's memory authority."""
import json, os, re, shlex, subprocess, sys, time
from pathlib import Path

try:  # the recorder is optional: its absence must never change a verdict or cost a wake
    from record import record
except Exception:  # noqa: BLE001
    def record(*_args, **_kwargs):
        return None

STARTED = time.monotonic()
RUN = {"sid": "unknown", "source": "", "missing": []}

MEMO = Path(os.environ.get("OPTMEM_MEMO_PATH", str(Path.home() / ".local/bin/memo")))
MEMORY_DIR = Path(os.environ.get("OPTMEM_MEMORY_DIR", Path.home() / ".optmem" / "memory"))
# The hook timeout wraps everything here: wake, then the core notes and the clock. Keep both values
# below the timeout you register for this hook (sample values).
WAKE_TIMEOUT = 3.0
# Everything after the wake shares what is left of this; a slow block is dropped, never the wake.
BUDGET = 4.5
SHARED_HOOKS = Path(os.environ.get("CODEX_SHARED_HOOKS") or Path(__file__).resolve().parents[2] / "claude" / "hooks")
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


def emit(context: str, status: str, detail: str = "") -> int:
    """Print the injection, then leave one row saying how the run ended (see record.py)."""
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "SessionStart", "additionalContext": context,
    }}, separators=(",", ":")), flush=True)
    missing = ",".join(RUN["missing"])
    if status == "ok" and missing:
        status, detail = "degraded", f"missing {missing}"
    record("optmem_start", status, STARTED, RUN["sid"], detail=detail, chars=len(context))
    return 0


def shared(script: str, budget: float, feed: str = "") -> str:
    """Output of one of Claude's SessionStart hooks, so both runtimes run one implementation.

    Until 2026-11-10 Codex woke with the wake document only: no core notes (rules such as the
    style line reached Claude alone) and no clock, which is the UTC confusion
    session-inject-time.sh exists to stop. A failure here costs that block, never the wake.
    """
    budget = min(budget, BUDGET - (time.monotonic() - STARTED))
    if budget < 0.05:
        return ""
    command = ["python3" if script.endswith(".py") else "bash", str(SHARED_HOOKS / script)]
    try:
        done = subprocess.run(command, check=False, text=True,
                              capture_output=True, input=feed, timeout=budget,
                              env={**os.environ, "MEMORY_DIR": str(MEMORY_DIR)})
        return json.loads(done.stdout)["hookSpecificOutput"]["additionalContext"].strip()
    except Exception:
        return ""


def extras() -> str:
    clock = json.dumps({"hook_event_name": "SessionStart", "source": RUN["source"]})
    blocks = {"core": shared("optmem-core.sh", 1.0),
              "clock": shared("session-inject-time.sh", 0.5, feed=clock)}
    RUN["missing"] = [name for name, block in blocks.items() if not block]
    return "".join(f"\n\n{block}" for block in blocks.values() if block)


def header() -> str:
    try:
        payload = json.load(sys.stdin)
        raw = payload.get("session_id")
        # The clock block labels its reading by this: a resume is not a start.
        RUN["source"] = payload["source"] if isinstance(payload.get("source"), str) else ""
    except BaseException:
        raw = None
    scope = raw[:8] if isinstance(raw, str) else ""
    if SESSION_SCOPE.fullmatch(scope):
        RUN["sid"] = scope
        return (f"SESSION SCOPE: @s/{scope}\nUse this token verbatim for session-scoped "
                "notes, candidates, and Linear claims.")
    return ("SESSION SCOPE: unresolved\nDo not guess a session scope; report that the hook "
            "payload did not provide one.")


def main() -> int:
    top = header()
    manual = f"env MEMORY_DIR={shlex.quote(str(MEMORY_DIR))} {shlex.quote(str(MEMO))} wake"
    if not os.access(MEMO, os.X_OK):
        return emit(f"{top}\n\nOPTMEM WAKE FAILURE: no executable at {MEMO}. "
                    f"Run the read-only command by hand: {manual}", "error", "no-memo")
    if not (MEMORY_DIR / "LOG.txt").is_file() or not (MEMORY_DIR / "TREE").is_dir():
        return emit(f"{top}\n\nOPTMEM WAKE FAILURE: store incomplete at {MEMORY_DIR}. "
                    f"Run by hand after repairing the store: {manual}", "error", "no-store")
    try:
        done = subprocess.run([str(MEMO), "wake"], check=False, text=True, capture_output=True,
                              env={**os.environ, "MEMORY_DIR": str(MEMORY_DIR)},
                              timeout=WAKE_TIMEOUT)
    except (subprocess.TimeoutExpired, OSError) as exc:
        return emit(f"{top}\n\nOPTMEM WAKE FAILURE: {exc}. Run by hand: {manual}",
                    "error", type(exc).__name__)

    output = without_nap((done.stdout or done.stderr).strip())
    if done.returncode == 0 and "You are awake." in output.splitlines():
        return emit(f"{top}\n\n{AUTHORITY}\n\n{output}{extras()}", "ok")
    detail = output or f"memo wake exited with status {done.returncode} and no output"
    return emit(f"{top}\n\n{AUTHORITY}\n\nOPTMEM WAKE UNAVAILABLE: {detail}\n\n"
                "Treat memory as unavailable, report the condition, and continue from current "
                f"files, AGENTS.md and Linear. Do not settle or append OptMem meanwhile.{extras()}",
                "degraded", f"wake-unavailable exit {done.returncode}")


if __name__ == "__main__":
    raise SystemExit(main())
