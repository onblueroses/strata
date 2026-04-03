# Context Save

Persist session state to disk before it's lost to compaction.

## Step 1: Gather current state

Collect:
- What you're currently working on (task, feature, bug)
- What's done so far in this session
- Key decisions made (and rationale)
- What's next (immediate next step, not vague goals)
- Files being edited
- Any blockers or open questions

## Step 2: Update active spec (if exists)

If working on a spec in `.strata/specs/`:

1. Update `>> Current Step` with precise status
2. Check off completed steps
3. Add any new decisions to the Decisions table
4. Add discoveries to Learnings
5. Update `Last updated` timestamp

The spec is the primary persistence mechanism - if it's up to date, the context save
file is a backup.

## Step 3: Write context save file

Create `.strata/sessions/auto-context-save-{session-id}.md`:

```markdown
# Context Save - {date} {time}

## Working On
[What task/feature is in progress]

## Status
[What's done, what's remaining]

## Decisions
- [Decision 1]: [rationale]
- [Decision 2]: [rationale]

## Files Being Edited
- `path/to/file.ts` - [what changed/is changing]

## Next Steps
1. [Immediate next action - specific enough to continue without context]
2. [Following action]

## Open Questions
- [Anything unresolved that needs user input]
```

## Step 4: Git snapshot (optional)

If there's significant uncommitted work:

```bash
git stash push -m "context-save: [brief description]"
```

Or commit as a WIP:

```bash
git add -A && git commit -m "WIP: [what's in progress]"
```

## Anti-Examples

| Bad | Why | Better |
|-----|-----|--------|
| Not saving before compaction | Everything in the context window is lost | Save at milestones and before expected compaction |
| Vague context save ("working on feature X") | Doesn't help post-compaction recovery | Specific: files, decisions, exact next step |
| Saving context but not updating the spec | Spec is the primary source, context save is backup | Always update spec first |
| Saving every 5 minutes | Overhead exceeds value | Save at natural milestones (after each step/phase) |

## Quality Self-Check

1. Active spec (if any) is up to date?
2. Context save file has specific next steps (not "continue working")?
3. All decisions made this session are recorded somewhere (spec or save file)?
4. Uncommitted work is either committed or noted in the save?
