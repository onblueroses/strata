#!/usr/bin/env python3
"""PreToolUse(Bash) for Codex: hand every command to BOTH shared privacy gates.

Exit 0 permits, exit 2 refuses with a reason on stderr. Anything else the runtime reads as
"hook errored" and permits the command, so every path that cannot obtain a clean 0/2 verdict --
a crash, a signal, a timeout, a closed stderr, a payload that will not parse -- spells itself
out here as a refusal. One gate is not enough: a `git push` reached only the gh gate, whose
git-free prefilter allows immediately, so every Codex push bypassed the outgoing-history scan
(review, 2026-09-01).
"""

import json
import os
import signal
import subprocess
import sys
from pathlib import Path

GATES_DIR = Path(__file__).resolve().parents[2] / "claude" / "hooks"
# (filename, budget). The gh gate declares 3000 ms; the pre-push gate holds its own 17 s
# deadline, and 18 leaves room for process start-up without reaching the runtime's patience.
GATES = (("gate-gh-public-actions.sh", 3), ("gate-pre-push.sh", 18))


def emit(text: str) -> None:
    """stderr can already be closed: a failed write must not turn a refusal into status 120."""
    try:
        sys.stderr.write(text)
        sys.stderr.flush()
    except (OSError, ValueError):  # closed descriptor, broken pipe -- the verdict still stands
        pass


def deny(reason: str) -> int:
    emit(f"BLOCKED (Codex privacy hook): {reason}\n")
    return 2


def on_signal(
    signum, _frame
):  # a signal kills the process without a verdict; 128+n permits
    emit(f"BLOCKED (Codex privacy hook): signal {signum} arrived before a verdict.\n")
    os._exit(2)


def main() -> int:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError):
        return deny("the hook event is not JSON, so no gate could judge the command")
    if not isinstance(payload, dict):
        return deny(
            "the hook event is not an object, so no gate could judge the command"
        )
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command:
        return deny("the hook event carries no command, so no gate could judge it")
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd or not Path(cwd).is_dir():
        return deny("the payload carries no usable cwd, so paths cannot be resolved")

    # Test-only redirection to a directory of stub gates. Production reads absolute paths.
    root = Path(os.environ.get("CODEX_PRIVACY_GATE") or GATES_DIR)
    # Drop exported bash functions and startup files: the gates run under `bash -p` and must
    # not inherit a redefined builtin from the session that called them.
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith("BASH_FUNC_") and k not in ("BASH_ENV", "ENV")
    }

    for name, budget in GATES:
        gate = root / name
        if not gate.is_file():
            return deny(f"the privacy gate is missing at {gate}")
        env["CODEX_PRETOOL_SELECTED_GATE"] = name
        try:
            done = subprocess.run(
                ["bash", "-p", str(gate)],
                input=raw,
                text=True,
                capture_output=True,
                cwd=cwd,
                env=env,
                timeout=budget,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return deny(f"{name} exceeded its {budget}s budget")
        except OSError as exc:
            return deny(f"{name} could not run: {exc}")
        # The first refusal wins; a clean 0 moves on to the next gate.
        if done.returncode == 2:
            emit(done.stderr or done.stdout or f"BLOCKED by {name}.\n")
            return 2
        if done.returncode != 0:
            return deny(f"{name} exited {done.returncode} without a 0/2 verdict")
    return 0


if __name__ == "__main__":
    for _sig in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT, signal.SIGPIPE):
        try:
            signal.signal(_sig, on_signal)
        except (
            OSError,
            ValueError,
            AttributeError,
        ):  # a signal this platform will not take
            pass
    try:
        code = main()
    except BaseException as exc:  # a crash must read as a refusal, never as a permit
        code = deny(f"the hook itself failed: {exc!r}")
    try:
        sys.stdout.flush()
    except (OSError, ValueError):  # same: a flush that cannot land must not change the status
        pass
    # os._exit, not SystemExit: the interpreter's own final flush of a closed stdout or stderr
    # exits 120, which the runtime reads as a hook error and permits the command.
    os._exit(code)
