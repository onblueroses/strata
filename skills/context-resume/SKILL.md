---
name: context-resume
version: 4.0.0
description: |
  Manual fallback for post-compaction context restoration. Primary recovery is mechanical
  (session-post-compaction-restore.sh injects the recovery map via SessionStart and arms a
  read-gate). Use this skill when the automatic injection is missing, truncated, or seems incomplete.
  Auto-trigger: when the post-compaction system-reminder seems incomplete or missing.
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
---

# Context Resume

Manual fallback for restoring context after compaction. The post-compaction hook already injects the recovery map and points at the save files. This skill walks the full reconstruction when that injection is missing, truncated, or insufficient. Pipeline overview: `$STRATA_HOME/reference/context-continuity.md`.

**Outcome:**
- Goal: reconstruct the frame (north star, canonical docs, entity KB) AND the live session state (in-flight loop, ruled-out paths, next move) before doing any work.
- Success means: every save file that exists is read (the semantic save exists only if /context-save ran; the hook save alone is a valid starting point), every `Read On Resume` entry and owned spec opened, Frame docs opened by relevance, confidence ≥ 4.
- Stop when: confidence ≥ 4 and the next action is concrete and unblocked, OR confidence < 4 and a specific clarifying question is being asked.

Reach confidence ≥ 4 before working: partial context re-does work and contradicts settled decisions; asking costs 30 seconds, re-doing costs 30 minutes. Treat "Ruled out" entries as walls: they exist so dead ends are not re-tried. Treat uncommitted git changes as in-progress work to preserve, never to overwrite.

## Step 1: Read sources (in order)

**1a. Save files** — read every one that exists, at `$STATE_DIR/`:

1. `auto-context-save-{session-id}.md` — skill-written semantic save: Frame pointers (north star, station, canonical doc paths), Session Goal, Decisions, In-Flight, Read On Resume, Last Run Outputs, Session-Specific State.
2. `auto-context-save-{session-id}-hook.md` — hook-written mechanical snapshot + Frame map: canonical doc paths with line counts, entity KB paths, git state, owned specs' `>> Current Step`, daily-note summaries.

The saves are maps, not archives: open the files their `Read On Resume` and Frame blocks name, at the listed line ranges. In-Flight carries the loop ("Next move" is the default action); Last Run Outputs carries the actual error the previous instance was reacting to.

If the session ID is unknown, take the 8-char suffix of today's daily-note filename from SessionStart hook output, or read the newest matching files in the state directory.

**1b. JSONL event log** — `$STATE_DIR/session-events-{session-id}.jsonl`: mechanical edit/commit/compaction events. The most recent `compaction` event marks the boundary; events after it are the current window.

**1c. This session's daily note** — the file whose name ends in `-{session-id}.json` under `$KB_DIR/daily/` (search all dates; a sibling session's newest note is contamination). Key fields: `summary`, `decisions`, `outputs`, `entities_touched`.

**1d. Git state**

```bash
git branch --show-current && git status --short | head -15 && git log --oneline -10
```

**1e. Owned specs (highest priority for in-progress implementation)** — for any spec at `$SPECS_DIR/` with header `Status: in-progress` or `planning` that this session owns (its `Session:` field matches, is absent, or the spec was edited here — the same filter the hooks apply): read it. `>> Current Step` says exactly where work stopped; the Decisions journal is settled (reopen an entry only when its `Re-examine when` trigger fires).

**1f. Frame from disk** — canonical docs and entity KB live on disk untouched by compaction; the saves only point. Open the load-bearing ones the Frame names (THESIS/STRATEGY/ARCHITECTURE class, entity `summary.md`/`items.json`); the harness reloads the cwd CLAUDE.md chain natively.

## Step 2: Confidence check

Rate understanding 1-5:
- 5: crystal clear — frame inherited, loop state known, next action concrete.
- 4: good, minor gaps — proceed and flag what's uncertain.
- 3: general idea — one specific clarification needed.
- 1-2: multiple gaps — need user input.

## Step 3: Output

Confidence ≥ 4:

```
CONTEXT RESTORED
================
Repo: [name] (north star: [one-line])
Session goal: [what we're doing]
Status: [completed/pending counts]
Git: [branch] - [status]
Next: [immediate priority]

Resuming...
```

Then start on the next action.

Confidence ≤ 3:

```
PARTIAL RESTORE
===============
Found: [what was recovered]
Uncertain: [what's unclear]
Please clarify: [specific question]
```

Wait for the user's response.

## If no save file found

Report which paths were checked (skill save, hook save, daily notes, git state of cwd) and ask: "What should I work on?"
