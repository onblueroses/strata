#!/usr/bin/env python3
"""SessionStart, compaction only: the two things the compaction summary cannot know.

Where the working tree stands, and what the session save on disk says. No map file,
no spec scan, no PreCompact half: the SessionStart payload already carries the
session id, so nothing has to be written before compaction to read it after.

A save is inlined once per version and bounded by characters, the same contract as
Claude's hooks/session-post-compaction-restore.sh (reasons there): a later boundary with
an unchanged save gets one line naming the file.
Every failure exits 0 and prints nothing -- a hook error costs more than a missing hint.
"""
import json, os, subprocess, sys, time
from pathlib import Path

try:  # the recorder is optional: its absence must never change a verdict or cost a wake
    from record import record
except Exception:  # noqa: BLE001
    def record(*_args, **_kwargs):
        return None

# Sample value; set COMPACTION_SAVE_CHARS (claude/config/hooks-runtime.env.example) to fit the harness.
SAVE_CHARS = int(os.environ.get("COMPACTION_SAVE_CHARS", "7000"))
STARTED = time.monotonic()


def git(cwd: Path, *args: str) -> str:
    env = {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "LC_ALL": "C"}
    done = subprocess.run(["git", "-C", str(cwd), *args], check=False, text=True,
                          capture_output=True, env=env, timeout=5)
    return done.stdout.strip() if done.returncode == 0 else ""


def save_block(save: Path, seen: Path) -> tuple[list[str], str]:
    """Lines for the save and how it was shown: inlined or pointed."""
    stat = save.stat()
    version = f"{int(stat.st_mtime)} {stat.st_size}"
    written = time.strftime("%Y-%m-%d %H:%M", time.localtime(stat.st_mtime))
    try:
        if seen.read_text().strip() == version:
            return ["", f"Session save {save} (written {written}) was inlined after an earlier "
                        "compaction and has not changed since. Read it if the summary lacks "
                        "something it holds."], "pointed"
    except OSError:
        pass
    body = save.read_text(encoding="utf-8", errors="replace").rstrip("\n")
    lines = ["", f"Session save {save} (written {written}):", ""]
    if len(body) > SAVE_CHARS:
        head = body[:SAVE_CHARS]
        head = head[:head.rfind("\n")] if "\n" in head else head
        # Report the rest rather than hiding it; the model can read the file.
        lines += [head, "", f"(+{len(body) - len(head)} more characters in the file)"]
    else:
        lines.append(body)
    try:
        seen.parent.mkdir(parents=True, exist_ok=True)
        seen.write_text(version + "\n")
    except OSError:
        pass
    return lines, "inlined"


def report(payload: dict) -> tuple[str, str]:
    lines, mode = ["POST-COMPACTION"], "none"
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and Path(cwd).is_dir() and git(Path(cwd), "rev-parse", "--git-dir"):
        lines += ["", f"Git state of {cwd}:",
                  *git(Path(cwd), "status", "-sb").splitlines()[:12],
                  *git(Path(cwd), "log", "--oneline", "-3").splitlines()]
    sid = payload.get("session_id")
    if isinstance(sid, str) and sid:
        # BRIEF_DIR first (briefs live there since 2026-11-10, newest match wins), then the
        # read-only archive (STATE_DIR) for a session saved before that.
        notes = Path(os.environ.get("NOTES_ROOT") or Path.home() / "notes")
        archive = Path(os.environ.get("NOTES_ARCHIVE") or Path.home() / "notes-archive")
        briefs = Path(os.environ.get("BRIEF_DIR") or notes / "briefs")
        root = Path(os.environ.get("STATE_DIR") or archive / "state")
        seen = Path(os.environ.get("COMPACTION_STATE_DIR")
                    or Path.home() / ".cache/claude-compaction") / sid[:8]
        found = sorted(briefs.glob(f"*-{sid[:8]}-brief.md"))
        save = found[-1] if found else root / f"auto-context-save-{sid[:8]}.md"
        if save.is_file():
            block, mode = save_block(save, seen)
            lines += block
    return "\n".join(lines), mode


def main() -> int:
    sid = "unknown"
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict) or payload.get("source") != "compact":
            return 0
        sid = str(payload.get("session_id") or "unknown")[:8]
        context, mode = report(payload)
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }}, separators=(",", ":")), flush=True)
        record("continuity", "ok", STARTED, sid, save=mode, chars=len(context))
    except BaseException as exc:
        record("continuity", "error", STARTED, sid, detail=type(exc).__name__)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
