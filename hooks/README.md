# hooks/

Event-driven shell scripts wired by `settings.json`. Each hook does one job and exits.

## Event matrix

| Event | When it fires | Hooks shipped |
|-------|---------------|---------------|
| `SessionStart` | Claude Code session opens | `session-ensure-daily-note`, `session-check-dev-servers`, `session-cleanup-verify-markers`, `session-cleanup-codex`, `session-post-compaction-restore`, `session-sibling-awareness` |
| `Stop` | Session closing | `gate-verify` (blocking), `lifecycle-auto-end-fallback`, `lifecycle-sync-state`, `lifecycle-warn-unpushed` |
| `UserPromptSubmit` | After each user prompt, before model sees it | `context-nudge`, `context-doc-router` |
| `PreCompact` | Before the runtime compresses prior turns | `context-pre-compaction-save` |
| `PreToolUse` | Before a tool call executes | `allow-claude-dir-edits`, `warn-file-ownership`, `gate-pre-push` (blocking), `gate-nested-clone`, `gate-gh-public-actions`, `gate-rm-guard`, `gate-codex-exec`, `gate-paid-compute-destroy` |
| `PostToolUse` | After a tool call returns | `context-suggest-compact`, `observe-track-skill-runs`, `quality-lint-on-write` (blocking), `observe-track-edits`, `observe-track-session-events`, `context-enrich-search` |

## Blocking vs advisory

- **Blocking hooks** surface as errors and prevent the operation from continuing. Fix the underlying issue rather than bypassing. The three blocking hooks are listed in `CLAUDE.md` under `## Hooks`.
- **Advisory hooks** run silently and persist state to `$STATE_DIR/` or print informational lines. They do not block tool calls.

## State and side effects

Hooks read `$CLAUDE_SESSION_ID` from the environment and write state files keyed to the 8-char session id at `$STATE_DIR/.session-edits-<sid>`, `$STATE_DIR/.verify-passed-<sid>`, `$STATE_DIR/session-events-<sid>.jsonl`, and similar. Parallel sessions never collide on the same file. The `session-sibling-awareness` hook injects a summary of other live sessions at SessionStart.

## Adding a hook

1. Drop the script under `$STRATA_HOME/hooks/`. Make it executable.
2. Wire it in `$STRATA_HOME/settings.json` under the right event with a sensible `timeout` (advisory: 2000-5000ms; blocking that runs Codex: up to 1800000ms).
3. Honor `$CLAUDE_SESSION_ID` when persisting state, so parallel sessions stay isolated.
4. Read stdin only when the event actually provides JSON (Stop / Notification / PreCompact). Other events leave stdin empty.
5. Exit 0 for success; exit non-zero for blocking events to refuse the operation; print user-facing messages to stderr.
