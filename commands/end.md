---
description: |
  Close a session: run checks, update the active spec, commit and push, and write a field-agent result when dispatched.
  Auto-trigger: MANDATORY when session is ending, user says goodbye/done/wrap up/thanks/
  that's all/signing off/goodnight, or before closing. Invoke even for short sessions.
---

# End Session

Goal: Leave the work tested, restartable, committed, and pushed.

Success means:

- Applicable tests and checks pass, or the unresolved failure is reported without committing broken work.
- The active spec's `>> Current Step` matches the repository state.
- Session-owned changes are committed and pushed; pre-existing work remains untouched.
- A dispatched field agent leaves the result file that `/collect` expects.

Stop when: The checks, spec update, repository handoff, and any field-agent result are complete, then return a concise status and stop.

## 1. Inspect the work

Run `git status --short` and `git status -sb` in every repository touched this session. Use the session edit list and current working directory to find those repositories.

Separate session-owned changes from pre-existing or sibling-owned changes. Leave changes you do not own untouched.

## 2. Run checks

Run the project's documented tests, linters, type checks, or build checks that cover the changed behavior. Include a fresh `/verify` receipt when the user ran that self-check.

If a required check fails, report the command and failure. Stop before commit or push unless the user explicitly accepts the failure.

## 3. Update the active spec

Find the session-owned in-progress spec under `$SPECS_DIR`. If one exists:

- Re-read its goal, decisions, `>> Current Step`, and newest trail entry.
- Update `>> Current Step` to the first action that remains true after the checks.
- Record completed work and verification in the trail.
- Mark the spec complete only when its stated goal and acceptance checks are satisfied.

Do not edit a spec owned by another session. Skip this step when no active spec belongs to this work.

## 4. Commit and push

For each repository with session-owned changes:

1. Invoke `/commit` so review and logical grouping happen before the commit.
2. Run `git status --short` again and confirm only intended changes entered the commit.
3. Run `git push`.

Also push a repository that is already ahead of its upstream because of this session. Report a push failure and preserve the local commit.

## 5. Field agent result

When `.task-brief.md` exists, write `.task-result.md` for `/collect` after the repository checks finish. Copy the task id from the brief and record:

```markdown
---
id: {task id}
status: {complete|partial|failed}
completed: {ISO timestamp}
files_changed:
  - {path}
tests_passed: {true|false|unknown}
merge_order_hint: {merge-first|no-dependency|merge-after:{slug}}
---

## Summary
{What changed and why}

## Decisions
{Choices the parent must preserve}

## Surprises
{Unexpected facts, or "None"}

## Integration Notes
{Merge order, configuration, or follow-up work}
```

Write `.task-blocked.md` instead when an external blocker prevents meaningful progress. Name the blocker, work completed, and input required.

## 6. Stop

Report checks, active-spec state, commit hashes, push state, and field-agent result path when present. Then stop; do not begin new work during session close.
