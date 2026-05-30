<!-- keywords: followup, autonomous command, get-to-work, batch op, followup file, autonomous -->
# Follow-up Convention

Pattern for structured decision deferral during autonomous command execution. Used by commands that run without user input (/get-to-work, future batch commands) to record uncertain decisions instead of stopping.

## Quick Nav

| Task | Section |
|------|---------|
| Create a follow-up file | File Format |
| Add an item during autonomous work | Adding Items |
| Resolve items with the user | Resolution |
| Understand the lifecycle | Lifecycle |

## When to Create

Any command running autonomously (without user input) should create a follow-up file when it encounters decisions that need human judgment. Currently: `/get-to-work`. The file persists across the autonomous run and gets reviewed at session end.

## File Format

**Naming**: `.claude/followup-{session-id}.md` where session-id is the 8-char ID from the daily note filename.

**Template**:

```markdown
# Follow-up: [command name] ([date])

## Controversial Decisions
Judgment calls made without user input. Each entry: what was decided, why, and what the alternative was.

## Skipped Items
Work identified but deliberately deferred. Each entry: what was skipped and why.

## User Input Needed
Questions that blocked progress. Each entry: the question, what context is needed to answer it, and what assumption was made to keep going.

## Borderline Insights
Observations that might be worth persisting to the knowledge base but aren't clearly actionable yet.
```

## Adding Items

Use checkboxes for each item so resolution tracking is visible:

```markdown
- [ ] **Entity staleness**: Marked myapp as STALE (12d) but didn't run /reconcile because it requires VPS access. User should run `/reconcile --entity myapp` when VPS is reachable.
```

Include enough context that the user can make a decision without re-reading the original source. "Fixed X" is useless. "Changed port from 3003 to 3004 in infrastructure summary because PM2 output showed 3004 - but myapp summary still says 3003, unclear which is current" is actionable.

## Resolution

Follow-up files are reviewed at session start or by `/get-to-work`. For each unresolved item, use AskUserQuestion with concrete options:

- "Keep as-is" (accept the autonomous decision)
- "Revert" (undo the change)
- "Modify to [specific alternative]"
- "Defer to next session"

Mark resolved items with `[x]` or append `[RESOLVED: kept as-is]` / `[RESOLVED: reverted]`.

## Lifecycle

1. **Created** by autonomous commands at run start
2. **Populated** during autonomous execution as decisions arise
3. **Reviewed** at session start or by /get-to-work when follow-up files are detected
4. **Cleaned up** after review - moved to ~/to-delete/ when all items resolved, left in place if deferred items remain

## DO NOT

- Put routine status updates in follow-up files - only genuinely uncertain decisions
- Create a follow-up file for interactive commands - they can ask the user directly
- Leave follow-up files without the session-id suffix - concurrent instances would collide
