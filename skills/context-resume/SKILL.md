---
name: context-resume
version: 2.0.0
description: |
  Manual fallback for post-compaction context restoration. Primary recovery is now mechanical
  (session-post-compaction-restore.sh injects context via SessionStart stdout).
  Use this skill only when the automatic injection seems incomplete or missing.
  Auto-trigger: when post-compaction system-reminder seems incomplete or missing.
allowed-tools:
  - Read
  - Bash
  - Glob
---

# Context Resume

Manual fallback for restoring context after compaction. Primary recovery is now handled
automatically by `session-post-compaction-restore.sh` (SessionStart hook, sync stdout injection).
Use this skill when the automatic injection is missing or insufficient.

**Avoid these - they cause real problems:**
- **Don't start working before confidence >= 4** - working with partial context leads to re-doing work or contradicting decisions already made. Asking the user takes 30 seconds; re-doing work takes 30 minutes.
- **Don't skip spec files** - specs contain the authoritative implementation plan, settled decisions, and the exact step where work stopped. The auto-save often misses this detail because it's written by a hook before /end runs.
- **Don't assume the auto-save file is complete** - the PreCompact hook writes it before /end, so it may lack the session's final state, entity updates, and decisions made in the last few exchanges.
- **Don't ignore uncommitted git changes** - they usually represent in-progress work from before compaction. Overwriting or ignoring them loses real work.

## Step 1: Read Sources (in order)

<details>
<summary>Step 1: Read Sources (in order)</summary>

### 1a. JSONL Event Log (Primary - highest fidelity)
Append-only structured log of every significant action this session.
1. Find your session ID from the SessionStart hook output (8-char suffix of daily note filename)
2. Read `$STATE_DIR/session-events-{session-id}.jsonl`
3. Each line is a JSON object. Event types:
   - `edit` - file was modified (`file` field has the path)
   - `commit` - git commit was made (`msg` field has the message)
   - `compaction` - context was compacted (`window` field = compaction count)
   - `goal` - session objective (`text` field)
   - `decision` - a decision was made (`what` and `why` fields)
   - `milestone` - phase gate or status checkpoint (`text` field)
4. The most recent `compaction` event marks the boundary. Events after it are from the current context window. Events before it are from previous windows (still valuable for understanding full session history).
5. Reconstruct: which files were edited, what was committed, what decisions were made, how many compaction windows have passed.

### 1b. Auto-Save (Fallback)
Provides narrative context (Goal, Decisions, Next Actions) that the JSONL stream doesn't capture. If the JSONL log exists and has events, use it as primary source and treat the markdown saves as supplementary.

**Two save files may exist per session** (read both, they complement each other):
1. `$STATE_DIR/auto-context-save-{session-id}.md` — written by the `/context-save` skill. Holds rich semantic content the model composed: Goal, Critical Context, Decisions, Key Files. May be stale if the skill ran early in the session.
2. `$STATE_DIR/auto-context-save-{session-id}-hook.md` — written by the PreCompact hook just before each compaction. Holds fresh mechanical state: Active Specs `>> Current Step`, Git State, Today's Daily Notes. Always reflects the moment of compaction.

Use the skill file for **intent** (Goal/Decisions) and the hook file for **state** (git/specs/daily). If only one exists, use what you have. If neither session-specific file is found, fall back to the most recent matching files in `state/`.

### 1c. Today's Daily Note
Find latest file matching `$HOME/$KB_DIR/daily/[today]-*.json`
- Parse as JSON. Key fields: `summary`, `decisions`, `outputs`, `entities_touched`, `takeaway`

### 1d. Git State
```bash
git branch --show-current 2>/dev/null || echo "not a git repo"
git status --short 2>/dev/null | head -15
git log --oneline -3 2>/dev/null
```

### 1e. Spec Files (HIGHEST PRIORITY)
Check for active implementation specs:
```bash
ls $SPECS_DIR/*.md 2>/dev/null
```
If found, read ALL of them. Specs with `Status: in-progress` are critical - they contain the full implementation plan, decisions already made, and the `>> Current Step` section that tells you exactly where work left off. The spec is the source of truth for resuming mid-implementation tasks. Do NOT re-debate entries in the Decisions table - they were made with full context.

### 1f. Entity Context
If working in a known project, read its entity file:
- `$HOME/$KB_DIR/projects/[name]\summary.md`
- `$HOME/$KB_DIR/areas/[name]\summary.md`

</details>

## Step 2: Confidence Check

Rate understanding (1-5):
- 5: Crystal clear, ready to continue
- 4: Good understanding, minor gaps
- 3: General idea, need clarification
- 1-2: Confused, need user input

## Step 3: Output

<details>
<summary>Step 3: Output</summary>

### If Confidence >= 4:

```
CONTEXT RESTORED
================
Project: [name/path]
Goal: [what we're doing]
Status: [completed/pending counts]
Git: [branch] - [status]
Next: [immediate priority]

Resuming...
```

Then start on the next action.

### If Confidence <= 3:

```
PARTIAL RESTORE
===============
Found: [what was recovered]
Uncertain: [what's unclear]
Please clarify: [specific question]
```

Wait for user response.

</details>

## If No Save File Found

```
NO CONTEXT FOUND
Checked: $STATE_DIR/auto-context-save-{sid}.md (skill), auto-context-save-{sid}-hook.md (hook), daily notes, git state
What should I work on?
```
