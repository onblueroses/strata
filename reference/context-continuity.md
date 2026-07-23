<!-- keywords: compaction, context window, context-save, context-resume, pre-compaction, post-compaction, read-gate, save file, session events, transcript backup, recovery, resume -->
# Context Continuity

How session state survives compaction. One principle governs every layer: **capture what dies with the context window; point at what lives on disk.** Compaction destroys only in-window state (the live loop, unrecorded decisions, last outputs); specs, canonical docs, the entity KB, and git survive untouched, so saves prefer pointers to them. Deliberate exceptions are bounded orientation snapshots: `>> Current Step` excerpts, the git status/log snapshot, daily-note summary lines, and a quoted North Star claim.

## Quick Nav

| Task | Section |
|------|---------|
| What fires when | The pipeline |
| Which file holds what | File inventory |
| Section/path literals tooling parses | Parse contracts |
| Which skill to reach for | Skills |

## The pipeline

1. **PreCompact** — `hooks/context-pre-compaction-save.sh` (synchronous; atomic tmp+mv publish) writes the mechanical snapshot + Frame map to `auto-context-save-{sid}-hook.md`: repo identity, canonical doc paths with line counts, entity KB paths, git state, owned specs' `>> Current Step` excerpts, daily-note summaries. Appends a `compaction` event to the session JSONL, backs up the transcript (keep 5), ages out saves of dead sessions (>24h).
2. **Harness-native recovery** — the harness writes its own compaction summary into the next window and reloads the cwd CLAUDE.md chain. The save layer supplements this; it does not duplicate it.
3. **SessionStart (post-compaction)** — `hooks/session-post-compaction-restore.sh` fires only on `source: compact`. Injects the recovery map (save-file paths, owned specs, dmux orchestration, last 10 mechanical events, uncommitted files) and arms the read-gate sentinel.
4. **Read-gate** — `hooks/gate-resume-read.sh` + `.py` (PreToolUse): blocks consequential tools until a listed save is Read this window. Read-only tools stay open; 30-min TTL is the anti-deadlock backstop; any gate error fails open.
5. **Resume** — the model reads the saves, then opens what their maps name. `/context-resume` is the manual fallback when the injection is missing or thin.

`/context-save` (manual, at milestones or before manual compaction) writes the semantic companion `auto-context-save-{sid}.md`: the live loop (In-Flight, Decisions with reasoning, Read On Resume, Last Run Outputs) that no hook can know.

## File inventory

| File (in `$STATE_DIR/`) | Writer | Read by | Lifecycle |
|---|---|---|---|
| `auto-context-save-{sid}-hook.md` | PreCompact hook | restore hook (pointer), read-gate, model | overwritten per compaction; aged out >24h after session death |
| `auto-context-save-{sid}.md` | `/context-save` skill | same | merged on re-save; aged out >24h |
| `session-events-{sid}.jsonl` | `observe-track-session-events.sh` (edit/commit), PreCompact hook (compaction) | restore hook (last 10, mechanical only), `lifecycle-auto-end-fallback.sh` (commit events), telemetry distillation | aged out >24h; semantic kinds (goal/decision/milestone/hypothesis) are historical — producer retired 2026-07-23 |
| `.session-edits-{sid}` | `observe-track-edits.sh` | spec-ownership filters in both compaction hooks | session-scoped |
| `$SPECS_DIR/*.md` | `/spec` | everything (source of truth for implementation state) | owned via `Session:` field |
| `$STRATA_HOME/transcript-backups/pre-compaction-*.jsonl` | PreCompact hook | forensics only | keep 5 |
| `/tmp/claude-compact-window-{sid}.txt` | PreCompact hook | restore hook (window number) | tmpfs |
| `/tmp/claude-needs-resume-read-{full-sid}` | restore hook | read-gate | cleared on save-read; 30-min TTL |

## Parse contracts

Literals that tooling greps or matches; change any of them only by updating every consumer in the same commit.

- `## >> Current Step` — sed-extracted by the PreCompact hook from specs; the resume pointer everywhere.
- `## Read On Resume` — named by the restore hook and read-gate block message; the save's file-pointer block.
- Save file **paths** (`auto-context-save-{sid}[-hook].md`) — the read-gate matches Read calls against the exact paths in the sentinel; `/end` recovers the session id from the hook-save filename.
- Spec `Status:` / `Session:` fields — ownership filters in both compaction hooks (sibling isolation: the owner runs multiple parallel sessions; only owned specs surface in a session's recovery). The shared filter: header `Status: in-progress|planning` (first 10 lines only; body prose can quote historical status), AND (`Session:` matches | absent | spec listed in `.session-edits-{sid}`).

## Skills

- **`/context-save`** — semantic save for THIS session's own compaction. Pointer-first; template at `skills/context-save/references/save-template.md`.
- **`/context-resume`** — manual reconstruction fallback; confidence-gated (work starts at ≥ 4).
- **`/handoff`** — different job: brief a *fresh* session for a *different next task*; writes `$STATE_DIR/handoffs/`.
- **`/spec`** — the durable implementation state itself; a current `>> Current Step` on disk makes most of the save layer redundant for spec-driven work. Keep it current and the saves stay thin.
