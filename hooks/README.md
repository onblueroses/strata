# hooks/

Event-driven scripts wired by `settings.json`. The template registers 31 hook commands across seven events; each hook does one job and exits.

## Event matrix

| Event | When it fires | Hooks shipped |
|-------|---------------|---------------|
| `SessionStart` | Claude Code session opens | `session-ensure-daily-note`, `session-check-dev-servers`, `session-cleanup-verify-markers`, `session-cleanup-codex`, `session-post-compaction-restore`, `session-sibling-awareness`, `memory-digest`, `memory-entities` |
| `Stop` | Session closing | `gate-verify` (blocking), `lifecycle-auto-end-fallback`, `lifecycle-sync-state`, `lifecycle-warn-unpushed` |
| `SessionEnd` | Session has ended | `memory-access-log` |
| `UserPromptSubmit` | After each user prompt, before model sees it | `context-nudge` |
| `PreCompact` | Before the runtime compresses prior turns | `context-pre-compaction-save` |
| `PreToolUse` | Before a tool call executes | `gate-resume-read`, `allow-claude-dir-edits`, `warn-file-ownership`, `gate-pre-push` (blocking), `gate-nested-clone`, `gate-gh-public-actions`, `gate-rm-guard`, `gate-codex-exec`, `gate-destructive-git`, `gate-paid-compute-destroy` |
| `PostToolUse` | After a tool call returns | `observe-track-skill-runs`, `quality-lint-on-write` (blocking), `quality-resource-sizing`, `observe-track-edits`, `observe-track-session-events`, `observe-track-mcp-tools` |

## Blocking vs advisory

- **Blocking hooks** surface as errors and prevent the operation from continuing. Fix the underlying issue rather than bypassing. The primary user-visible gates are listed in `CLAUDE.md` under `## Hooks`.
- **Advisory hooks** run silently and persist state to `$STATE_DIR/` or print informational lines. They do not block tool calls.

## State and side effects

Hooks read `$CLAUDE_SESSION_ID` from the environment and write state files keyed to the 8-char session id at `$STATE_DIR/.session-edits-<sid>`, `$STATE_DIR/.verify-passed-<sid>`, `$STATE_DIR/session-events-<sid>.jsonl`, and similar. Parallel sessions never collide on the same file. The `session-sibling-awareness` hook injects a summary of other live sessions at SessionStart.

## Telemetry ledgers

Two invisible-by-design sinks under `$STATE_DIR` answer "what actually fires" without adding any model-visible output. `hook-firings.jsonl` records that a model-visible hook (context-nudge, resource-sizing, restore, warn-file-ownership) emitted, and how many bytes; `lib-ledger.sh` is the shared writer the instrumented hooks pipe their payload into. `mcp-tool-calls.jsonl` records which MCP servers' tools get called (`observe-track-mcp-tools`, PostToolUse `mcp__.*`). Both loggers exit 0 with no stdout or stderr and never alter a hook's own output; each sink is size-capped at 512 KB with one `.1` rollover generation.

## Adding a hook

1. Drop the script under `$STRATA_HOME/hooks/`. Make it executable.
2. Wire it in `$STRATA_HOME/settings.json` under the right event with a sensible `timeout` (advisory: 2000-5000ms; blocking that runs Codex: up to 1800000ms).
3. Honor `$CLAUDE_SESSION_ID` when persisting state, so parallel sessions stay isolated.
4. Read stdin only when the event actually provides JSON (Stop / Notification / PreCompact). Other events leave stdin empty.
5. Exit 0 for success; exit non-zero for blocking events to refuse the operation; print user-facing messages to stderr.
