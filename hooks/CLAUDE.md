# hooks/ conventions

Event-driven scripts wired by `settings.json`; each does one job and exits fast.
The full event matrix, the blocking-vs-advisory split, and the add-a-hook
checklist live in `README.md`.

## Local invariants

- **Session-key runtime state.** Read `$CLAUDE_SESSION_ID` and key every state
  file to the 8-char id (`$STATE_DIR/.verify-passed-<sid>`,
  `session-events-<sid>.jsonl`, ...). Parallel sessions must never collide on a
  shared path.
- **Tolerate stdin.** Hooks receive their payload as JSON on stdin (the file
  path is `.tool_input.file_path`). Empty or unparseable stdin exits 0, not with
  an error; a hook that hard-fails on a missing field blocks unrelated tool use.
- **No repo-controlled execution in PostToolUse.** These run automatically after
  every edit. Keep them to tools that inspect files (linters, formatters);
  running code from the edited tree on each write is a code-execution path.
- **Blocking hooks fail only on a real gate.** `gate-verify`,
  `quality-lint-on-write`, and `gate-pre-push` surface a nonzero exit as an
  error to the user. Exit 0 (silent) unless the gate genuinely trips; loud false
  positives train people to bypass.

## Local checks

Most hooks are shell with no unit suite; smoke-test by piping a sample event
JSON on stdin and reading the exit code. The memory hook wrappers have a wiring
test:

```
python3 -m pytest memory/tests_deep/test_wiring_hooks.py -q
```
