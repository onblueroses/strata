<!-- keywords: dmux, dispatch, parallel agents, worktree, tmux panes, field agent, task brief, collect, scratchpad, orchestrate parallel work, fan out agents -->
# dmux Dispatch Protocol

## Quick Nav
| Task | Section |
|------|---------|
| Understand the two-tier orchestrator/field-agent model | Problem Statement |
| Write a field-agent task brief | Brief Format |
| Dispatch parallel work across worktrees | Roles |
| Merge results back | Result Format |

## Problem Statement

Claude Code's parallel work model has three costs: (1) subagent output inflates parent context, compounding over a session, (2) a capable cross-model reviewer is otherwise confined to reviewer-only use, (3) no visibility into parallel agent status. Beyond fixing these, the deeper need is meaningful orchestration - one Claude Code session spreading work across multiple independent agents without losing overview or control.

## Understanding

### Facts
- dmux manages parallel AI agents in tmux panes with git worktree isolation
- dmux has NO pane creation API - only TUI-based creation (pressing 'n')
- dmux DOES have worktree discovery (resumeBranches.ts, worktreeDiscovery.ts)
- dmux's status detection polls tmux pane content via LLM (small fast models racing)
- dmux supports 11 agent CLIs with per-agent prompt transport and permission flags
- Claude Code subagents share the parent context window - output compounds
- a substantial skill/hook system: skills, hooks, entity summaries, MEMORY.md, daily notes

### Context
- No existing framework handles independent CLI session handoffs (CrewAI/AutoGen/LangGraph work in-process)
- The community pattern for parallel AI coding is raw worktrees with no formalized protocol
- the skill/hook system travels with CLAUDE.md and settings.json (global config)
- Entity summaries contain project context that code exploration alone can't surface

### Constraints
- Must work from any terminal (not just inside dmux session)
- Must be fully programmatic (parent dispatches without human intervention)
- Must work across all projects (global change)
- Loose coupling to dmux - use conventions, not internals
- Protocol must survive dmux version updates

### Unknowns (Resolved)
- [x] Does dmux detect externally-created panes? > Status detection polls ALL panes in its tmux session
- [x] How to create panes without API? > tmux + git commands directly, using dmux's directory conventions
- [x] What context do children need most? > Entity summaries + project CLAUDE.md sections (things code can't reveal)

### Unknowns (Open)
- [ ] Will dmux's TUI correctly display externally-created panes in its sidebar?
- [ ] Performance impact of embedded entity context in every brief (~70 lines)
- [ ] Whether dmux's autopilot works on externally-created panes

## Research & Input

### Multi-Agent Framework Patterns
- **LangGraph**: Shared state dictionary with reducers. Partial updates compose into final state. Closest analogy to our brief/result protocol.
- **CrewAI (A2A)**: Structured HTTP+JSON messages with typed artifacts. Agent autonomously decides local vs. remote delegation.
- **OpenAI Swarm** (deprecated): Handoff passes FULL conversation history. Opposite of our approach.
- **AutoGen/AG2**: Message-based via ConversableAgent. GroupChat selector determines next speaker.

### Community Patterns
- dmux, workmux, and the community all converge on: worktree per agent, filesystem isolation, merge when done
- No one has formalized the communication layer between orchestrator and workers
- Claude Code's built-in EnterWorktree/ExitWorktree provides isolation but no handoff protocol

## Solutions Considered

### Option A: Deep dmux Integration
Contribute a pane creation API to dmux, build on its state management.
- **Pros**: Full dmux feature set (status, autopilot, merge UI), clean integration
- **Cons**: Upstream PR timeline uncertain, tight coupling, API may change
- **Sacrifices**: Independence, development speed

### Option B: Loose Coupling via tmux + git (Chosen)
Use dmux's filesystem conventions but create panes via raw tmux/git commands.
- **Pros**: Works today, no dmux modifications, survives version updates, simple
- **Cons**: Panes may not fully appear in dmux's TUI sidebar, no autopilot guarantee
- **Sacrifices**: Some dmux TUI features

### Option C: Custom Orchestration (No dmux)
Build everything from scratch: tmux management, status detection, merge workflow.
- **Pros**: Full control, no external dependency
- **Cons**: Massive scope, reimplements what dmux does well
- **Sacrifices**: Development time, proven UX

## Tradeoffs Matrix

| Criterion | A: Deep Integration | B: Loose Coupling | C: Custom |
|-----------|--------------------|--------------------|-----------|
| Works today | No (needs upstream PR) | Yes | No (weeks of work) |
| dmux features | Full | Partial | None |
| Maintenance | Tied to dmux releases | Independent | All on us |
| Complexity | Medium | Low | High |
| Future-proof | Depends on dmux | Very | Very |

## Recommendation

**Option B: Loose Coupling via tmux + git.** Use dmux as the visual layer and monitoring substrate. Build orchestration in Claude Code. Communicate via filesystem. If dmux gains a proper CLI/API, the integration gets cleaner. If it doesn't, the current approach still works.

## The Protocol

### Architecture

```
Parent Claude Code (orchestrator)
  |
  |-- Subagents (inline, sync, context-sharing)
  |   Used when: parent needs result IN CONTEXT for next decision
  |
  |-- dmux panes (independent, async, filesystem-sharing)
  |   Used when: task can be fully specified and executed independently
  |   Each pane: own worktree, own branch, own context window
  |   Communication: .task-brief.md / .task-result.md / scratchpad
  |
  +-- dmux visual layer (monitoring, notifications, merge UI)
```

### ID Scheme

- Dispatch ID: `{parent-session-8char}-{slug}` (e.g., `f5419cfb-auth-middleware`)
- Session ID in frontmatter (traceability), slug as filesystem key
- Worktree path: `.dmux/worktrees/{slug}/` (dmux convention)

### Three File Types

All live in the worktree root.

#### .task-brief.md (Parent writes, Child reads)

```yaml
---
id: f5419cfb-auth-middleware
parent_session: f5419cfb
dispatched: 2026-04-13T21:45:00Z
agent: claude
permission_mode: acceptEdits
entity: example-project
branch_from: main
scratchpad: true
siblings:
  - slug: cost-tests
    scope: "cost tracker tests - owns src/cost.test.ts"
  - slug: readme-update
    scope: "README update - owns README.md"
---

## Goal
[One sentence: the destination this task reaches.]

## Success means
- [Checkable output element]
- [Checkable output element]
- [Format / location / quality criterion]

## Stop when
[Explicit stopping condition the field agent self-evaluates against. Example: "All acceptance checkboxes are checked, the test suite passes, and changes are committed."]

## Objective
[1-2 sentences: WHY this task matters. Prescriptive about goal, silent about approach. Lead with a positive verb.]

## Constraints
[Hard boundaries that survive negation - safety, scope edges, file ownership across siblings. Reserve for the four legitimate negation cases (safety, near-identical-path disambiguation, large acceptable space, specific banned items). Everything else gets a positive directional sibling sentence above.]

## Acceptance Criteria
- [ ] [Self-verifiable checkbox written as the action that satisfies it]
- [ ] [Self-verifiable checkbox]

## Coordination
[What siblings are doing, shared boundaries, merge order dependencies]

## Entity Context
[Embedded: first ~40 lines of entity summary.md via /pickup]

## Project Rules
[Embedded: relevant constraint/quality sections from project CLAUDE.md]
```

**Design principles**: Outcome on top (Goal / Success means / Stop when), directional body underneath. Prescriptive about WHAT, descriptive about WHY, silent about HOW. Every sentence in Objective / Acceptance Criteria leads with the positive verb of the correct action. Negation survives only in Constraints, and only in the four legitimate cases. See global CLAUDE.md `## Prompt Authoring` and `/directional-prompting` skill.

Contains things the child CAN'T discover (entity context, sibling coordination). Points to things it CAN discover (key files, not code snippets).

#### .task-result.md (Child writes via /end, Parent reads)

```yaml
---
id: f5419cfb-auth-middleware
status: complete  # complete | partial | blocked | failed
completed: 2026-04-13T22:15:00Z
files_changed:
  - examples/infra/auth-middleware.ts
  - examples/infra/__tests__/auth.test.ts
tests_passed: true
merge_order_hint: merge-first  # merge-first | no-dependency | merge-after:{slug}
---

## Summary
[What was done - 2-3 sentences]

## Decisions
[Non-obvious choices that affect the project]

## Surprises
[Things the parent didn't anticipate - the HIGHEST VALUE section]

## Integration Notes
[What the parent needs for merge - env vars, config, ordering]
```

#### .task-blocked.md (Child writes when stuck)

```yaml
---
id: f5419cfb-auth-middleware
status: blocked
blocked_since: 2026-04-13T22:00:00Z
blocker: need-architecture-decision
---

## What's Blocking
[Clear description of the decision or information needed]

## Done So Far
[Work completed before hitting the block]

## What I Need
[Specific request - decision, context, or unblocking action]
```

### Bootstrap Prompt (agent-specific)

Common prefix (all agents):
> You are a dispatched field agent in a dmux worktree. Read .task-brief.md for your mission. Execute the task respecting all constraints. Check .dmux/scratchpad/ if the brief has scratchpad: true. If you discover something siblings should know, write to .dmux/scratchpad/{your-slug}.md.

**Claude** suffix: "When done: commit your work, run /end. If blocked, write .task-blocked.md and go idle."

**Codex/Gemini/other** suffix: "When done: commit your work, then write .task-result.md with YAML frontmatter (id, status, files_changed, merge_order_hint) and sections: Summary, Decisions, Surprises, Integration Notes. If blocked, write .task-blocked.md and go idle."

The split exists because only Claude has the /end skill which auto-generates .task-result.md. Non-Claude agents get inline instructions to write it manually.

### Shared Scratchpad

- Location: `{project-root}/.dmux/scratchpad/{slug}.md`
- Convention: each pane writes ONLY its own file, reads all files
- Format: freeform markdown, no frontmatter needed
- Check: once at start, and when hitting something unexpected
- Lifecycle: cleared when parent session's dispatches are all merged

### Dispatch Flow

```
PARENT                              CHILD (dmux pane)
  |                                    |
  +-- decomposes task                  |
  +-- writes .task-brief.md            |
  +-- git worktree add                 |
  +-- copies brief into worktree       |
  +-- tmux split-window in dmux        |
  +-- launches agent ─────────────────>|
  |                                    +-- reads .task-brief.md
  |                                    +-- explores codebase
  |   (monitors via dmux status)       +-- executes task
  |                                    +-- writes to scratchpad (optional)
  |                                    +-- runs /verify, /review
  |                                    +-- commits work
  |                                    +-- runs /end -> writes .task-result.md
  |                                    +-- goes idle
  +-- reads .task-result.md  <─────────|
  +-- reads git diff                   |
  +-- evaluates merge order            |
  +-- merges worktrees                 |
  +-- archives artifacts               |
```

### Multi-Wave Orchestration

For large projects where a parent session dispatches multiple rounds of tasks, reacting
to results each time:

```
Parent (orchestrator, long-lived)
  │
  ├─ /dispatch Wave 1: agents A, B, C
  │   ├─ [agents work in parallel, 30-90 min]
  │   ├─ /collect → read results → log to orchestration.md → merge
  │   └─ React: "A found X, B suggests Y → dispatch D, E for Phase 2"
  │
  ├─ /dispatch Wave 2: agents D, E (branch from updated main)
  │   ├─ [agents work in parallel]
  │   ├─ /collect → read results → log → merge
  │   └─ React: "All done" or "New issues found → dispatch Wave 3"
  │
  ├─ [compaction may happen here]
  │   ├─ Spec survives (phase tracker)
  │   └─ orchestration.md survives (wave history)
  │
  └─ Read spec + orchestration.md → continue from current wave
```

**Compaction survival:**
- The **spec** tracks WHAT phase we're in and WHAT was decided (Decisions table)
- The **orchestration log** (`{project}/.dmux/orchestration.md`) tracks WHAT each wave dispatched, WHAT came back, and WHY we decided to dispatch the next wave
- Together, these let the parent fully restore orchestration context after compaction

**Monitoring between waves:** The parent is idle while agents work. Options:
- Manual: watch dmux TUI, run `/collect` when agents finish
- poll every 5 minutes with a repeating `/collect` (stop when all complete)
- Watch for `.task-result.md` files: `watch -n 10 'find .dmux/worktrees -name .task-result.md'`

### Decision Framework: Subagent vs. dmux

**Default: dmux.** Exception: subagent when the parent needs the result in its working memory to make its next decision.

| Use subagent | Use dmux pane |
|---|---|
| "Find where auth is handled" (need answer to decompose) | "Implement auth middleware" |
| "What test framework does this use?" (need answer for brief) | "Write tests for the cost tracker" |
| Quick lookup (<30s, <500 tokens) | Implementation task (minutes to hours) |
| Parent would block waiting | Parent does other work while waiting |

## Contemplation Summary

Two contemplative-reasoning journeys across 13 steps.

**Journey 1** (begin -> open -> examine -> direct -> integrate -> meditate -> sudden -> embody):
Domains: process_flow -> meta_cognitive -> skillful_means -> non_dual -> meditation -> skillful_means -> non_dual.
Key turns: (1) The brief is a mission briefing, not a recipe. (2) During meditation, realized result format should converge with /end output. (3) Entity summaries are the critical context gap.

**Journey 2** (begin -> direct -> verify -> refine -> complete):
Domains: skillful_means -> meta_cognitive.
Key turns: (1) Session-scoped IDs belong in frontmatter, not directory structure. (2) Scratchpad uses per-pane files to avoid locking. (3) merge_order_hint enables dependency-aware integration.

## Implementation Plan

### Phase 1: Minimum Viable Dispatch (~30 min)
1. Write `dmux-dispatch.sh` shell script
2. Add field agent paragraph to global CLAUDE.md
3. Install dmux globally
4. Test: manually dispatch one task, verify worktree + agent launch

### Phase 2: Orchestrator Skills (~45 min)
1. Write `/dispatch` skill (task decomposition, brief writing, dispatch calling)
2. Write `/collect` skill (result reading, merge ordering, integration)
3. Test: dispatch 3 parallel tasks from parent session

### Phase 3: /end Integration + Scratchpad (~30 min)
1. Modify /end to detect .task-brief.md and write .task-result.md
2. Document scratchpad convention in bootstrap prompt
3. Test: child runs /end, parent reads structured result

### Phase 4: Polish (~30 min)
1. Edge cases: blocked handling, failed panes, orphan cleanup
2. Archive workflow for completed dispatches
3. Decision framework documentation in CLAUDE.md

## Operational Notes

### Trust Dialog Auto-Approval
Claude Code shows a workspace trust dialog for new directories (including worktrees). The dispatch
script auto-approves this by polling the pane content and sending Enter when the trust pattern
is detected. This matches dmux's own `autoApproveTrustPrompt` pattern in `paneCreation.js`.
Polling: 2s initial delay, then check every 250ms for up to 10s. Runs in a background subshell
so it doesn't block the script.

### Session Matching
When multiple dmux tmux sessions exist (e.g., `dmux-projectA-*` and `dmux-projectB-*`), the
dispatch script matches the project name against session names first, falling back to the first
dmux session. This prevents dispatching a project's tasks to the wrong dmux instance.

### Pane Layout
Each dispatch creates a horizontal tmux split. After 3+ dispatches, panes become too narrow for
agent UIs. The /dispatch command runs `tmux select-layout tiled` after all dispatches complete.
With tiled layout, 3 panes get ~80x11 each (workable), 5 panes get ~40x8 (tight but usable).

### Non-Claude Agents (Codex, Gemini)
Codex and Gemini lack Claude Code's /end skill. The bootstrap prompt is agent-specific:
- **Claude**: "run /end" - handles daily note, .task-result.md, entity reconciliation
- **Codex/Gemini**: explicit instructions to write .task-result.md directly with template
- /collect has fallback: if no .task-result.md exists but worktree has new commits, infer task completed
- Codex plan mode falls back to default (interactive approval) - no Codex equivalent

### Field Agent Daily Notes
Each dispatched field agent creates its own daily note via /end step 3 (Claude agents only).
This is by design - provides per-task audit trail and session tracking. For 3-task dispatches,
expect 3 child daily notes + 1 parent daily note = 4 total.

### Sync Conflict Prevention
Field agents skip /end step 6 ($KB_DIR git sync) to avoid concurrent push conflicts.
Only the parent session syncs $KB_DIR/ after /collect completes.

### Token Budget (per dispatch cycle)
- /dispatch command load: ~800 tokens
- Brief generation (3 tasks): ~600 tokens
- Script execution: ~200 tokens
- /collect command load: ~620 tokens
- Result reading (3 tasks): ~600 tokens
- Total orchestration overhead: ~2,800 tokens (negligible vs. child session costs)
- CLAUDE.md field agent paragraph: ~160 tokens (always loaded, unavoidable)

### Worktree Lifecycle
- Worktrees live at `{project}/.dmux/worktrees/{slug}/`
- The dispatch script adds `.task-brief.md`, `.task-result.md`, `.task-blocked.md`, `.dmux/` to each
  worktree's `.gitignore` on first dispatch. This prevents protocol files from being committed.
  The `.gitignore` modification gets committed and merged to main (one-time setup per project).
- Scratchpad is shared via symlink: each worktree's `.dmux/scratchpad/` symlinks to
  `{project}/.dmux/scratchpad/`. This enables cross-agent communication.
- The dispatch script deletes stale branches before creating worktrees (prevents collision)
- Cleanup requires `git worktree remove --force` because protocol files are untracked
- Archive preserves briefs and results at `.dmux/archive/{slug}/`

### tmux Pane Layout
The dispatch script uses `tmux split-window -h` (horizontal split). Multiple dispatches
create progressively narrower panes. dmux's layout management handles this for its own
panes, but externally-created panes may not be in its layout. If panes become too narrow,
manually run `tmux select-layout -t {session} tiled` to rebalance.

### eval Usage in dispatch script
`run_or_print` uses `eval` for non-dry-run commands. This works for clean paths
(no shell metacharacters). your project paths are all under $HOME/Work/ with simple names.
If a project path ever contains `$`, backticks, or other shell-interpreted chars, the
eval will misbehave. Not a current risk but noted for awareness.

### Security
Slug validation enforces `[a-z0-9][a-z0-9-]*` to prevent shell injection via `$()`
in tmux command construction. `git check-ref-format` alone is insufficient (allows `$`, `(`, `)`).
The bootstrap prompt embeds the slug directly in a shell string that tmux passes to `sh -c`.

### Nested Dispatch (dispatch-within-dispatch)
Field agents CAN dispatch sub-tasks. Git worktrees can be created from within other worktrees.
The inner dispatch must use the PROJECT ROOT path (not the outer worktree path) for `--project`.
The entity field in .task-brief.md resolves to the project root via MEMORY.md entity table.
Not yet tested with real agents but the git mechanics work.

### Concurrent Parents
Multiple parent sessions dispatching to the same project simultaneously works without
contention. Git worktrees, scratchpad, and tmux panes are all independent resources.
Tested: 2 concurrent worktree creations + cross-scratchpad reads via symlinks.

## Open Questions

- Will dmux's TUI sidebar render externally-created panes? (Status detection confirmed via tmux polling; sidebar rendering untested)
- Should we PR a CLI mode to dmux upstream? (Evaluate after v1 is working)
- Can the scratchpad scale to 5+ siblings? (10 concurrent writes tested without corruption; real-world scaling TBD)
- ~~Should Codex panes use a different brief format?~~ Resolved: agent-specific bootstrap prompt
- Does Codex actually follow the inline .task-result.md template? (Untested with real Codex agent)
- Field agent compaction recovery: if a child agent compacts mid-task, does it recover from the brief? (Untested)

