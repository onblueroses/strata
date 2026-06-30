---
description: |
  Load context for an entity. Reads summary, items, recent sessions, checks git, warns if stale.
  Manual: when starting work on a known entity and you need full context loaded quickly.
---

# Pickup

Load full context for an entity to start working on it. Reads documentation, checks git state, warns about staleness.

```
/pickup myapp          # Load entity context (resolved against your KB)
/pickup infra          # Common alias for the infrastructure area
```

Arguments via `$ARGUMENTS`.

## Skip Conditions

- **Skip if** no argument provided - ask the user which entity to load
- **Skip if** entity was already loaded this session (check if you've read its summary.md in recent context)

---

## Entity Resolution

The strata kernel does not ship a pre-pinned entity table. Resolve the input dynamically against your knowledge base:

1. Glob `$KB_DIR/{projects,areas}/*/summary.md` and try exact-name match against the directory name.
2. If no exact match, try prefix match against directory names.
3. If still no match, check the `Entities` table in `$KB_DIR/MEMORY.md` (if present) for aliases.
4. If multiple candidates remain, list them and ask the user.

Encourage users to maintain their own `MEMORY.md` entity table at `$KB_DIR/MEMORY.md` with `entity-name | aliases | entity-path | repos` columns. /pickup will read it if present.

---

## Steps

### 1. Read entity documentation

Read these in a single parallel tool call:
- `$KB_DIR/[entity-path]/summary.md`
- `$KB_DIR/[entity-path]/items.json`

### 2. Check staleness

Extract `last_verified: YYYY-MM-DD` from summary.md.

| Age | Action |
|-----|--------|
| 0-6 days | OK - mention date |
| 7-13 days | Warn: "Entity last verified [date] - consider running a ground-truth reconcile" |
| 14+ days | Warn urgently: "Entity STALE ([N] days) - run a ground-truth reconcile before making changes" |
| Missing | Warn: "No verification date found" |

### 3. Check git state (for entities with repos)

**Skip if** entity has no local repos (check the Repos column in the table above - entries marked "no local repo" or "VPS state").

For each repo in the entity's repo list, run in parallel:

```bash
git -C [repo-path] branch --show-current 2>/dev/null
git -C [repo-path] status --short 2>/dev/null
git -C [repo-path] log --oneline -3 2>/dev/null
```

Report: branch, uncommitted changes, last 3 commits.

### 4. Extract recent sessions

From the Recent Sessions table in summary.md, show the last 5 entries. These give quick context on what was done recently.

### 5. Output

```
PICKUP: [entity name]
=====================
Path: $KB_DIR/[entity-path]
Verified: YYYY-MM-DD ([N]d ago) [OK/STALE]

## Summary
[First 3-5 lines of summary.md - status and key facts]

## Recent Sessions
| Date | Session | Summary |
[Last 5 rows from Recent Sessions table]

## Git State
[repo-name]: [branch] - [N uncommitted] - last: [commit message]
[repo-name]: [branch] - clean - last: [commit message]

## Key Items
[Top 5 most recent items from items.json, if any]

[Staleness warnings if applicable]
Ready to work on [entity name].
```

---

## Quality Self-Check

After gathering context, verify:
1. **summary.md read successfully** - did you get actual content, not an error?
2. **Staleness checked** - did you extract and evaluate last_verified?
3. **All repos checked** - for multi-repo entities, did you check every repo listed?
4. **Recent sessions present** - did you include the session history for continuity?

## DO NOT

- Start working on the entity without reading its documentation first - that's the whole point
- Skip the staleness check - stale docs lead to wrong assumptions
- Read the full items.json if it's large - just show the 5 most recent items
- Modify any files during pickup - this is read-only context loading
- Report pickup as a "task completed" - it's setup, not work
