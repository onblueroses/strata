---
description: "Collect results from dispatched dmux tasks — reads .task-result.md files in worktrees, evaluates status (completed/blocked/in-progress), suggests merge order based on file overlap, provides cleanup commands. Pre-check: skip if no .dmux/worktrees/ exists in the current project. Triggers on: 'collect', 'collect results', 'gather the dispatched work', 'how are the tasks', 'are they done', 'check on the agents', 'what's the progress', 'dispatch status', 'dmux status', 'task status', 'are the panes done', 'merge the worktrees', 'pull in the work'. Also triggers when: /dispatch was used earlier in this session and the user returns after a pause; the user references dmux panes or worktrees without explicit /collect; a session is ending and dispatched tasks haven't been collected. Pairs with /dispatch (upstream — collect handles what dispatch fanned out), /review (downstream — review merged results before commit), /commit (downstream — commit after collect surfaces a clean merge order). Manual: /collect."
---

# Collect

Read results from dispatched dmux panes, evaluate status, plan merge order, and guide integration.

```
/collect                    # Collect from current project
/collect /path/to/project   # Collect from specific project
```

Arguments via `$ARGUMENTS`.

## Skip Conditions

- **Skip if** no `.dmux/worktrees/` directory exists in the project
- **Skip if** no worktrees contain `.task-brief.md` (not dispatched tasks)

---

## Steps

### 1. Discover dispatched worktrees

Find all dispatched worktrees:
```bash
find {project}/.dmux/worktrees/ -name '.task-brief.md' -maxdepth 2
```

For each worktree, determine its status by checking which files exist:
- `.task-result.md` exists -> read it (complete, partial, or failed)
- `.task-blocked.md` exists -> read it (blocked)
- Neither exists but worktree has new commits (vs branch_from) -> infer complete (non-Claude agents may not write protocol files; use `git log --oneline {branch_from}..{slug}` to check for commits)
- Neither exists, no commits, but worktree has uncommitted changes -> infer complete-uncommitted (Codex behavior: creates files but doesn't commit or write protocol files). Run `git -C {worktree} status --short` to detect. For these, auto-commit the changes: `git -C {worktree} add -A && git -C {worktree} commit -m "Auto-commit: {slug} dispatch work (Codex)"` before merging.
- Neither exists, no commits, no changes, pane dead -> orphan (agent crashed or failed silently)
- Neither exists, no commits, no changes, pane active -> still running

### 2. Report status

Output a status table:

```
Dispatched Tasks ({N} total):
| # | Slug | Agent | Status | Files Changed |
|---|------|-------|--------|---------------|
| 1 | auth-middleware | claude | complete | 3 files |
| 2 | cost-tests | codex | blocked | - |
| 3 | readme-update | claude | running | - |
```

For blocked tasks, show the blocker summary inline.
For completed tasks, show the summary from .task-result.md.

### 3. Evaluate results

For each completed task:
1. Read `.task-result.md` fully
2. Run `git diff --stat {branch_from}..{slug}` to see actual changes
3. Check for file overlap with other completed tasks (same file changed by 2+ tasks)
4. Read the Surprises section - flag anything that affects other tasks

If file overlaps exist, warn:
```
WARNING: File overlap detected:
  - src/types.ts changed by both auth-middleware and cost-tests
  Merge these sequentially and resolve conflicts.
```

### 4. Plan merge order

Build a merge order based on `merge_order_hint` from each result:
1. `merge-first` tasks go first
2. `merge-after:{slug}` tasks go after their dependency
3. `no-dependency` tasks fill remaining slots
4. Tasks with file overlaps are ordered to minimize conflicts

Output the merge plan:

```
Merge Order:
  1. auth-middleware (merge-first: changes API interfaces)
  2. cost-tests (no-dependency)
  3. readme-update (no-dependency)

Conflicts expected: none
```

### 5. Provide merge commands

For each task in merge order, output the exact git commands:

```bash
# 1. Merge auth-middleware
cd {project}
git merge auth-middleware --no-edit
# If conflicts: resolve, then git add . && git commit

# 2. Merge cost-tests
git merge cost-tests --no-edit

# 3. Merge readme-update
git merge readme-update --no-edit
```

After all merges, suggest running tests:
```bash
# Verify merged state
{test command for project}
```

### 6. Update orchestration log

Append a wave entry to `{project}/.dmux/orchestration.md`. This file survives compaction and enables multi-wave orchestration. The parent reads it after compaction to restore the full dispatch history.

```markdown
## Wave {N} - {ISO timestamp}
Parent session: {session-id}
Phase: {spec phase name, if active spec exists}

### Dispatched
| Slug | Agent | Status | Summary |
|------|-------|--------|---------|
| {slug} | {agent} | {status from result} | {1-line from result Summary} |

### Decisions from results
- {What the parent decided based on these results}
- {What to dispatch next, or "orchestration complete"}

### Surprises
- {Anything from result Surprises sections that affects the project}
```

If the file doesn't exist, create it with a header: `# Orchestration Log - {project-name}`.
If an active spec exists, cross-reference the phase. This log is the compaction lifeline for multi-wave orchestration.

### 7. Archive and cleanup

After successful merges (user confirms), provide cleanup commands:

```bash
# Archive task artifacts
mkdir -p {project}/.dmux/archive
for slug in auth-middleware cost-tests readme-update; do
  mkdir -p {project}/.dmux/archive/$slug
  cp {project}/.dmux/worktrees/$slug/.task-brief.md {project}/.dmux/archive/$slug/
  cp {project}/.dmux/worktrees/$slug/.task-result.md {project}/.dmux/archive/$slug/ 2>/dev/null
  git worktree remove --force {project}/.dmux/worktrees/$slug
  git branch -d $slug
done

# Clean scratchpad
rm -f {project}/.dmux/scratchpad/*.md
```

Do NOT execute cleanup automatically. Present the commands and let the user confirm. Respect the deletion constraint - `git worktree remove` and `git branch -d` are safe (they fail if unmerged).

---

## Handling Blocked Tasks

If a task is blocked:
1. Read `.task-blocked.md` to understand what's needed
2. Present options via AskUserQuestion:
   - "Provide context": write additional info to the worktree and restart the agent
   - "Take over": jump into the pane manually to resolve
   - "Abort": remove the worktree without merging
   - "Re-dispatch": create a new brief with more context and dispatch again

---

## Edge Cases

**Orphan worktrees:** If the dispatch script created a worktree but the tmux pane failed to launch (tmux crash, dmux session closed), the worktree exists with a .task-brief.md but no agent ever ran. Detected by: .task-brief.md exists, no .task-result.md, no .task-blocked.md, no new commits on the branch, no active tmux pane. Offer to re-dispatch or abort.

**Non-Claude agents (Codex, Gemini):** May not write .task-result.md at all (they lack /end). If a worktree has new commits but no result file, infer completion from git state. Use `git log --oneline {branch_from}..{slug}` for commit history and `git diff --stat {branch_from}..{slug}` for change summary. Synthesize a minimal result for the merge plan.

**Pane layout:** Multiple dispatches create horizontal tmux splits that get narrow. If panes are hard to read, suggest: `tmux select-layout -t {session} tiled`

---

## DO NOT

- Merge without showing the merge plan first
- Execute cleanup commands without user confirmation
- Ignore file overlaps between tasks
- Skip reading the Surprises section (it's the highest-value part)
- Merge a blocked or failed task
