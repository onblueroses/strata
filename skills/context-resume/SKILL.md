---
name: context-resume
description: |
  Restore a compacted session from save pointers, git state, owned specs, and canonical repo docs.
  Auto-trigger: when the post-compaction system-reminder seems incomplete or missing.
allowed-tools:
  - Read
  - Bash
  - Glob
  - Grep
---

# Context Resume

This skill now reconstructs a compacted session from save pointers, git state, owned specs,
and canonical repo docs. The post-compaction hook normally injects that map; use this fallback
when the injection is missing, truncated, or insufficient. Pipeline overview:
`$STRATA_HOME/reference/context-continuity.md`. Platform memory behavior lives in
`$STRATA_HOME/reference/knowledge-management.md`; this skill maintains no separate knowledge store.

**Outcome:**
- Goal: reconstruct the frame (north star, canonical docs, owned specs) AND the live session state (in-flight loop, ruled-out paths, next move) before doing any work.
- Success means: every save file that exists is read (the semantic save exists only if /context-save ran; the hook save alone is a valid starting point), every `Read On Resume` entry and owned spec opened, Frame docs opened by relevance, confidence ≥ 4.
- Stop when: confidence ≥ 4 and the next action is concrete and unblocked, OR confidence < 4 and a specific clarifying question is being asked.

Reach confidence ≥ 4 before working: partial context re-does work and contradicts settled decisions; asking costs 30 seconds, re-doing costs 30 minutes. Treat "Ruled out" entries as walls: they exist so dead ends are not re-tried. Treat uncommitted git changes as in-progress work to preserve, never to overwrite.

## Step 1: Read sources (in order)

**1a. Save files** — read every one that exists, at `$STATE_DIR/`:

1. `auto-context-save-{session-id}.md` — skill-written semantic save: Frame pointers (north star, station, canonical doc paths), Session Goal, Decisions, In-Flight, Read On Resume, Last Run Outputs, Session-Specific State.
2. `auto-context-save-{session-id}-hook.md` — hook-written mechanical snapshot + Frame map: canonical doc paths with line counts, git state, and owned specs' `>> Current Step`.

The saves are maps, not archives: open the files their `Read On Resume` and Frame blocks name, at the listed line ranges. In-Flight carries the loop ("Next move" is the default action); Last Run Outputs carries the actual error the previous instance was reacting to.

If the session ID is unknown, read it from the post-compaction system reminder or use the
newest matching files in the state directory only when their repo and branch match the current work.

**1b. JSONL event log** — `$STATE_DIR/session-events-{session-id}.jsonl`: mechanical edit/commit/compaction events. The most recent `compaction` event marks the boundary; events after it are the current window.

**1c. Git state**

```bash
git branch --show-current && git status --short | head -15 && git log --oneline -10
```

**1d. Owned specs (highest priority for in-progress implementation)** — for any spec at `$SPECS_DIR/` with header `Status: in-progress` or `planning` that this session owns (its `Session:` field matches, is absent, or the spec was edited here — the same filter the hooks apply): read it. `>> Current Step` says exactly where work stopped; the Decisions journal is settled (reopen an entry only when its `Re-examine when` trigger fires).

**1e. Frame from disk** — canonical repo docs live on disk untouched by compaction; the saves
only point. Open the load-bearing files the Frame names (THESIS/STRATEGY/ARCHITECTURE class);
the harness reloads the cwd CLAUDE.md chain natively.

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

Report which paths were checked (skill save, hook save, owned specs, git state of cwd) and ask: "What should I work on?"
