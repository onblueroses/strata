#!/usr/bin/env python3
"""SessionStart, compaction only: the two things the compaction summary cannot know.

Where the working tree stands, and what the session save on disk says. No map file,
no spec scan, no PreCompact half: the SessionStart payload already carries the
session id, so nothing has to be written before compaction to read it after.
Every failure exits 0 and prints nothing -- a hook error costs more than a missing hint.
"""
import json, os, subprocess, sys
from pathlib import Path

HEAD_LINES = 150


def git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"}
    done = subprocess.run(["git", "-C", str(cwd), *args], check=False, text=True,
                          capture_output=True, env=env, timeout=5)
    return done.stdout.strip() if done.returncode == 0 else ""


def report(payload: dict) -> str:
    lines = ["POST-COMPACTION"]
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and Path(cwd).is_dir() and git(Path(cwd), "rev-parse", "--git-dir"):
        lines += ["", f"Git state of {cwd}:",
                  *git(Path(cwd), "status", "-sb").splitlines()[:12],
                  *git(Path(cwd), "log", "--oneline", "-3").splitlines()]
    sid = payload.get("session_id")
    root = Path(os.environ.get("STATE_DIR") or Path.home() / "life/areas/claude-code-setup/state")
    save = root / f"auto-context-save-{sid[:8]}.md" if isinstance(sid, str) and sid else None
    if save is not None and save.is_file():
        body = save.read_text(encoding="utf-8", errors="replace").splitlines()
        lines += ["", f"Session save {save}:", "", *body[:HEAD_LINES]]
        # Report the tail rather than hiding it; the model can read the file.
        if len(body) > HEAD_LINES:
            lines += ["", f"(+{len(body) - HEAD_LINES} more lines in the file)"]
    return "\n".join(lines)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict) or payload.get("source") != "compact":
            return 0
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": report(payload),
        }}, separators=(",", ":")))
    except BaseException:
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
