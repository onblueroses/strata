---
description: "Dispatch independent tasks to dmux panes — decomposes a goal into parallel tasks, writes task briefs (.task-brief.md), and launches agent sessions in isolated git worktrees. The parent orchestrates, dmux executes. For 2+ independent tasks, decompose and dispatch in parallel. For a single task, dispatch solo. Pre-check: a dmux tmux session must exist (`tmux list-sessions -F '#{session_name}' 2>/dev/null | grep -q '^dmux'`). If no session, falls back to inline implementation. Triggers on: 'dispatch this to dmux', 'dispatch', 'send to dmux', 'parallel tasks', 'split this work', 'fan out the work', 'parallelize this', 'work in worktrees', 'isolate these tasks', 'multi-pane work'. Also triggers when: the user requests implementation work ('build X', 'add Y', 'fix Z', 'refactor W', 'write tests for X') and a dmux session exists; planning reveals 2+ independent work streams that can run in parallel without sharing state; the user explicitly mentions dmux, worktrees, or pane-based execution. Pairs with /collect (downstream — gather results from dispatched panes), /spec (upstream — spec phases tagged for dispatch get fanned out here), /best-of-n (different parallelism — BoN runs N candidates of the same task; dispatch runs N different tasks)."
---

# Dispatch

Decompose a goal into independent tasks and dispatch each to a dmux pane with its own git worktree and agent session. Communication via filesystem protocol (.task-brief.md, .task-result.md).

```
/dispatch                  # Decompose current goal and dispatch
/dispatch "add auth, write tests, update docs"   # Explicit task list
```

Arguments via `$ARGUMENTS`.

## Skip Conditions

- **Skip if** the work is a single task that doesn't benefit from parallelism
- **Skip if** tasks have hard sequential dependencies (A must complete before B can start)
- **Skip if** dmux is not installed (`which dmux` fails)
- **Skip if** no tmux session with "dmux" prefix exists (`tmux list-sessions` check)

## Prerequisites

Verify before proceeding:
1. `which dmux-dispatch.sh` returns a path
2. `tmux list-sessions -F '#{session_name}' | grep '^dmux'` finds a session
3. Current directory is a git repo (or entity's repo path is known)

If any fail, tell the user what's missing and how to fix it.

---

## Steps

### 1. Identify the entity and project

Determine which entity/project the work targets:
- If in a known repo directory, use the corresponding entity from MEMORY.md
- If user specifies an entity, resolve via the `/pickup` entity resolution table
- Read the entity's `summary.md` (first ~40 lines) - this will be embedded in every brief

Also locate the project's CLAUDE.md if one exists (at the repo root). Extract the Constraints and Code Quality sections for embedding.

**Multi-wave awareness:** Check if `{project}/.dmux/orchestration.md` exists. If yes, read the **last 2 wave entries** only (not the full file - it grows over time). This prevents re-dispatching completed work and informs task decomposition. After compaction, this file + the spec are the primary sources of orchestration history. To read efficiently: `grep -n '^## Wave' orchestration.md | tail -2 | head -1` gives the start line of the second-to-last wave.

### 2. Decompose into tasks

Break the goal into 2-5 **independent** tasks. Each task must be:
- Executable without results from other tasks
- Scoped to files that don't overlap with other tasks
- Completable in a single agent session

For each task, determine:
- **slug**: lowercase, hyphenated, filesystem-safe (e.g., `auth-middleware`, `cost-tests`)
- **scope**: 1-sentence description of what the task covers
- **agent**: which agent CLI to use (`claude`, `codex`, `gemini`)
- **file ownership**: which files/directories this task owns (no overlap with siblings)

Present the decomposition to the user for confirmation:

```
Use AskUserQuestion:
  "I've decomposed this into N tasks. Confirm or adjust?"
  Options:
  - "Dispatch all": launch all tasks
  - "Adjust": let me modify the decomposition
  - "Dispatch selected": choose which tasks to launch
```

### 3. Generate task briefs

For each confirmed task, write a `.task-brief.md` file to a staging area at `{project}/.dmux/tasks/{slug}.md`.

<details>
<summary>Brief template</summary>

```markdown
---
id: {session-id}-{slug}
parent_session: {session-id}
dispatched: {ISO-timestamp}
agent: {claude|codex|gemini}
permission_mode: {acceptEdits|bypassPermissions|plan}
entity: {entity-name}
branch_from: {main|branch-name}
scratchpad: true
siblings:
  - slug: {other-slug}
    scope: "{other-scope}"
---

## Objective
{1 paragraph: WHAT to do and WHY. Prescriptive about goal, silent about approach.}

## Constraints
{Hard boundaries:}
- Do not modify files outside your ownership scope
- {Project-specific constraints from CLAUDE.md}
- {Any technical constraints}

## Acceptance Criteria
- [ ] {Observable, testable criterion}
- [ ] {Observable, testable criterion}
- [ ] Tests pass (if applicable)
- [ ] No lint errors

## Coordination
{What siblings are doing and shared boundaries:}
- Sibling "{slug}" owns {files} - do not touch
- {Merge order dependencies if any}

## Entity Context
{Embedded: first ~40 lines of entity summary.md}

## Project Rules
{Embedded: relevant Constraints/Code Quality sections from project CLAUDE.md, if one exists}
```

</details>

**Brief writing rules:**
- Objective: prescriptive about WHAT, descriptive about WHY, silent about HOW
- Constraints: hard boundaries only (not preferences)
- Acceptance criteria: observable outcomes, not vague ("works correctly" is banned)
- Entity context: copy from summary.md, not paraphrased
- Siblings: list ALL other tasks in this dispatch, with their file ownership

### 4. Dispatch tasks

For each task, call the dispatch script:

```bash
dmux-dispatch.sh \
  --project "{project-root}" \
  --slug "{slug}" \
  --agent "{agent}" \
  --brief "{project}/.dmux/tasks/{slug}.md" \
  --branch-from "{branch}" \
  --permission-mode "{mode}"
```

Run dispatches sequentially (not parallel) to avoid tmux race conditions. Wait 2 seconds between dispatches for pane creation to settle. The script auto-approves the Claude Code trust dialog in new worktree directories.

**Branch detection:** The default `--branch-from` is `main`. Before dispatching, check the project's actual default branch:
```bash
git -C "{project-root}" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's|refs/remotes/origin/||' || git -C "{project-root}" branch --show-current
```

After all dispatches, rebalance the tmux layout:
```bash
tmux select-layout -t {dmux-session} tiled
```

Then output a summary table:

```
Dispatched 3 tasks:
| Slug | Agent | Branch | Status |
|------|-------|--------|--------|
| auth-middleware | claude | auth-middleware | launched |
| cost-tests | codex | cost-tests | launched |
| readme-update | claude | readme-update | launched |

Monitor in dmux. Run /collect when tasks complete.
```

### 5. Initialize scratchpad

If any brief has `scratchpad: true`:
1. `mkdir -p {project}/.dmux/scratchpad`
2. Check if `.dmux/` is in the project's `.gitignore`. If not, warn: "Add `.dmux/` to .gitignore to prevent committing protocol files."

---

## Session ID

Your session ID is the 8-character suffix of your daily note filename. Extract it from the SessionStart hook output or from `ls $KB_DIR/daily/*$(date +%Y-%m-%d)*.json | tail -1`.

---

## Agent Selection Guide

| Task type | Recommended agent | Why |
|-----------|-------------------|-----|
| Implementation (new feature, refactor) | claude | Full skill/hook ecosystem, best at complex reasoning |
| Test writing | claude or codex | Both capable; codex for speed, claude for thoroughness |
| Code review / adversarial | codex | Built for adversarial review, different perspective |
| Data transformation, scripting | gemini | Strong at structured data tasks |
| Documentation | claude | Best at prose and technical writing |

Default to `claude` unless there's a reason to choose otherwise.

**Agent limitations:**
- **Codex/Gemini**: No /end skill. The dispatch script gives them inline instructions to write .task-result.md directly. Results may be less structured than Claude's. /collect has fallback handling for missing result files.
- **Codex**: No `plan` permission mode. Falls back to interactive approval (most restrictive).
- **Gemini**: No `plan` permission mode. Falls back to default approval.
- **All non-Claude agents**: Won't create daily notes, reconcile entities, or sync $KB_DIR/. Only Claude field agents produce full audit trail.

---

## Edge Cases

**Non-existent branch-from:** If `--branch-from` points to a branch that doesn't exist, `git worktree add` will fail. The dispatch script will abort (`set -e`). Check that the base branch exists before dispatching.

**Orphan worktrees on tmux failure:** If worktree creation succeeds but tmux pane creation fails (session closed, dmux crashed), an orphan worktree remains. /collect detects these: worktree with brief but no result, no commits, no active pane. Offer re-dispatch.

**Pane layout:** Each dispatch creates a horizontal tmux split. After 3-4 dispatches, panes get narrow. dmux may auto-manage layout for its panes, but externally-created panes may not be in its layout system. Fix with: `tmux select-layout -t {session} tiled`

**Project without .dmux/ in .gitignore:** dmux auto-adds `.dmux/` to .gitignore when it runs in a project. If dmux hasn't run there yet, .dmux/ will show as untracked in git status. Step 5 warns about this.

---

## Failure Mode Defenses

These are real failure patterns from multi-agent systems. The protocol has specific countermeasures:

| Failure mode | How it manifests | Our defense |
|-------------|-----------------|-------------|
| Semantic conflict | Two agents make incompatible design choices | File ownership in brief prevents touching same code. Scratchpad carries decisions between siblings. /collect checks for overlap before merge. |
| Goal drift | Agent strays from objective over long sessions | Acceptance criteria in brief are testable checkboxes. /verify gate blocks completion without passing checks. |
| Orchestrator amnesia | Parent forgets what it dispatched after compaction | orchestration.md logs every wave. Spec tracks phase state. Restore hook injects orchestration status. |
| Reasoning loop | Agent retries same failed action endlessly | set -e in dispatch script aborts on failure. /end has priority mode for stuck sessions. .task-blocked.md is the escape valve. |
| Context explosion | Results flood parent context | Results stay in .task-result.md files (filesystem). Parent reads summaries only. Implementation details never enter parent context. |

---

## DO NOT

- Dispatch tasks with overlapping file ownership (causes merge conflicts)
- Dispatch tasks that depend on each other's output (sequence them instead)
- Include implementation steps in the brief (child chooses its own approach)
- Embed code snippets in the brief (child reads files itself)
- Dispatch more than 5 tasks at once (diminishing returns, merge complexity)
- Skip the AskUserQuestion confirmation step
- Pass large data blobs in briefs (pass file paths instead - agent reads them itself)
