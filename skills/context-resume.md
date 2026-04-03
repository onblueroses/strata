# Context Resume

Recover working context after compaction or context loss.

## Step 1: Find context sources

Check these in order:

1. **Active specs** - `.strata/specs/` for any file with `Status: in-progress`
2. **Context save files** - `.strata/sessions/` for auto-context-save files
3. **Session notes** - most recent session note in `.strata/sessions/`
4. **Git state** - `git status`, `git log --oneline -10`, `git stash list`

## Step 2: Load active spec (highest priority)

If an in-progress spec exists:

1. Read the spec file
2. Go to `>> Current Step` - this tells you exactly where work was interrupted
3. Read `Decisions` - these are settled, do NOT re-debate
4. Read `Learnings` - non-obvious discoveries from previous work
5. Read `Quick Start` - files being touched and next action

**After loading:** Update the spec's `Session:` field to your current session ID and
continue from `>> Current Step`.

## Step 3: Load context save (if no active spec)

Read the most recent auto-context-save file. It contains:
- What you were working on
- Key decisions made
- Files being edited
- Next steps

## Step 4: Verify git state

```bash
git status                # uncommitted changes?
git log --oneline -5      # recent commits from this session?
git stash list           # stashed work?
git branch -vv           # which branch, tracking info?
```

If there are uncommitted changes, they're likely from the interrupted session. Review before
continuing.

## Step 5: Resume

Based on what you found:

- **Has active spec:** Continue from `>> Current Step`. Don't re-plan.
- **Has context save but no spec:** Read the save, pick up where noted.
- **Has session notes only:** Read the "Next steps" section, start there.
- **Nothing found:** Ask the user what they want to work on.

## Anti-Examples

| Bad | Why | Better |
|-----|-----|--------|
| Re-exploring the entire codebase | Wasteful if context save exists | Check for saves and specs first |
| Re-debating decisions from the spec | They were made with full context you no longer have | Trust the Decisions table |
| Starting fresh work without checking for active specs | Abandons in-progress work | Always check .strata/specs/ first |
| Ignoring git state | Miss uncommitted changes from previous work | Check git status early |

## Quality Self-Check

1. Checked for active specs before doing anything else?
2. Loaded the most specific context source available?
3. Did NOT re-plan or re-debate settled decisions?
4. Git state reviewed (uncommitted changes, stashes, branch)?
5. Ready to continue from where work was interrupted?
