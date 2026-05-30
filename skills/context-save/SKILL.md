---
name: context-save
version: 3.0.0
description: |
  Pre-compaction context preservation. Saves session state to files including spec file progress.
  Manual: PreCompact hook handles basic saves automatically. Invoke /context-save for thorough manual save at milestones.
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
---

# Context Save

Save current session state before compaction or at a milestone.

**Guard:** Save files are session-specific: `$STATE_DIR/auto-context-save-{session-id}.md` (session ID = 8-char suffix of daily note filename). Read your session's existing save file first. If it has more detail than what you're about to write (e.g., from a previous manual save this session), merge: keep the more detailed Goal and Critical Context, union the Decisions and Key Files tables, update Status checkboxes to current state.

**Note:** The PreCompact hook writes to a separate path (`auto-context-save-{session-id}-hook.md`) holding fresh mechanical state (Git/Specs/Daily Notes). It will NOT clobber this skill's file. Both files survive and `/context-resume` reads both.

**Avoid these - they cause real problems:**
- **Don't overwrite with less detail** - a previous manual save this session may have richer context than the current state. Merging preserves information; overwriting destroys it.
- **Don't list every file changed** - after compaction, the model reads this file. A 50-file list wastes tokens and obscures what matters. Summarize by area (e.g., "12 files in src/components/") if >10 files.
- **Don't include sensitive data** - save files are plaintext in the repo. Passwords, API keys, and tokens in the save file are a security leak.
- **Don't skip Next Actions** - this section is the primary driver for post-compaction resumption. Without it, the model has to re-derive what to do next, which wastes time and risks going in a different direction.

## Step 1: Gather State

<details>
<summary>Step 1: Gather State</summary>

### Session Info
- What was the goal this session?
- What decisions were made and why?
- What files were created/modified?
- What's the current task status?

### Git State
```bash
git branch --show-current 2>/dev/null || echo "not a git repo"
git status --short 2>/dev/null | head -20
git log --oneline -5 2>/dev/null
git diff --stat 2>/dev/null | tail -5
```

### Background Tasks
Check for running agents or background shells.

### Spec Files
Check for active implementation specs:
```bash
ls $SPECS_DIR/*.md 2>/dev/null
```
If found, read them. For each spec with `Status: in-progress`:
- Record the file path
- Extract the `>> Current Step` section (this is the compaction lifeline)
- Count completed vs total steps
- Before saving, update the spec's `>> Current Step` to reflect current state

</details>

## Step 2: Write Save File

<details>
<summary>Step 2: Write Save File</summary>

Create/update `$STATE_DIR/auto-context-save-{session-id}.md`:

```markdown
# Context Save - [DATE TIME]

## Goal
[Primary objective this session]

## Status
- [x] Completed items
- [ ] In progress
- [ ] Pending

## Decisions
| Decision | Reasoning |
|----------|-----------|
| [choice] | [why] |

## Key Files Modified
| Path | What changed |
|------|-------------|
| [path] | [change] |

## Git State
- Branch: [name]
- Uncommitted: [count] files
- Recent commits: [last 5 one-liners]

## Spec Files
| Path | Progress |
|------|----------|
| [spec path] | [X/Y complete] |

## Next Actions
1. [First priority]
2. [Second]
3. [Third]

## Critical Context
[Non-obvious things that would be bad to forget]
```

### Append JSONL Semantic Events

After writing the markdown save, append semantic events to `$STATE_DIR/session-events-{session-id}.jsonl`. These capture agent-level understanding that the PostToolUse hook cannot detect:

```bash
# Session ID = 8-char suffix from daily note filename
JSONL="$STATE_DIR/session-events-{session-id}.jsonl"
```

Append one JSON line per event using Bash `echo >>`:
- **Goal**: `{"type":"goal","ts":"ISO8601","sid":"...","text":"[session objective]"}`
- **Each decision**: `{"type":"decision","ts":"ISO8601","sid":"...","what":"[choice]","why":"[reasoning]"}`
- **Milestone**: `{"type":"milestone","ts":"ISO8601","sid":"...","text":"[status summary, e.g. Phase 1 complete, 3/7 steps done]"}`

Only append events that are NEW since the last /context-save. Check the existing JSONL for duplicate goals/decisions before appending.

### Quality Self-Check

After writing the save file, verify:
1. **Next Actions non-empty** - does it have at least 1 concrete action?
2. **Goal is specific** - does it describe the actual objective, not just "working on X"?
3. **Critical Context captured** - any non-obvious state that would be lost in compaction?
4. **Spec files listed** - if any exist, are they referenced with progress counts?
5. **JSONL events appended** - did you write goal + decisions + milestone to the event log?

</details>

## Step 3: Output

```
CONTEXT SAVED to $STATE_DIR/auto-context-save-{session-id}.md
Git: [branch] - [uncommitted count] files
Next: [top priority action]

Ready to compact.
```

Keep it brief.
