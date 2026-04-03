# Pickup

Load full context for an entity to start working on it. Reads documentation, checks git state, warns about staleness.

```
/pickup my-project      # Load a project's context
/pickup infra           # Load infrastructure context
```

Arguments via `$ARGUMENTS`.

## Skip Conditions

- **Skip if** no argument provided - ask the user which entity to load
- **Skip if** entity was already loaded this session (check if you've read its summary.md in recent context)

---

## Entity Resolution

Build the entity table from your MEMORY.md Entities section. Each entity has:
- A name (directory name under `life/projects/` or `life/areas/`)
- Aliases (short names users might type)
- Repos (local directory paths, or "no local repo" for VPS-only or no-code entities)

Example pattern:
```
| Input      | Aliases        | Entity path            | Repos                    |
|------------|----------------|------------------------|--------------------------|
| my-project | proj, mp       | life/projects/my-project | projects/my-project/    |
| my-site    | site, frontend | life/projects/my-site  | projects/my-site/        |
| infra      | vps, server    | life/areas/infra       | (VPS state, no local repo) |
```

If input doesn't match any alias, glob `life/{projects,areas}/*/summary.md` and try prefix match. If still no match, list available entities and ask.

---

## Steps

### 1. Read entity documentation

Read these in a single parallel tool call:
- `~/life/[entity-path]/summary.md`
- `~/life/[entity-path]/items.json`

### 2. Check staleness

Extract `last_verified: YYYY-MM-DD` from summary.md.

| Age | Action |
|-----|--------|
| 0-6 days | OK - mention date |
| 7-13 days | Warn: "Entity last verified [date] - consider running /reconcile" |
| 14+ days | Warn urgently: "Entity STALE ([N] days) - run /reconcile before making changes" |
| Missing | Warn: "No verification date found" |

### 3. Check git state (for entities with repos)

**Skip if** entity has no local repos (check the Repos column in the entity table - entries marked "no local repo" or "VPS state").

For each repo in the entity's repo list, run in parallel:

```bash
git -C [repo-path] branch --show-current 2>/dev/null
git -C [repo-path] status --short 2>/dev/null
git -C [repo-path] log --oneline -3 2>/dev/null
```

Report: branch, uncommitted changes, last 3 commits.

### 4. Check mycelium agent notes (for entities with repos)

**Skip if** entity has no local repos or `mycelium.sh` is not installed.

For each repo in the entity's repo list, check for agent notes:

```bash
cd [repo-path] && mycelium.sh find warning 2>/dev/null
cd [repo-path] && mycelium.sh find context 2>/dev/null
cd [repo-path] && mycelium.sh find constraint 2>/dev/null
```

If notes exist, include them in the output under `## Agent Notes`. Show kind, body, and source slot (session). Flag notes older than 7 days as `[stale]`. If no notes exist, show "No agent notes."

### 5. Extract recent sessions

From the Recent Sessions table in summary.md, show the last 5 entries. These give quick context on what was done recently.

### 6. Output

```
PICKUP: [entity name]
=====================
Path: life/[entity-path]
Verified: YYYY-MM-DD ([N]d ago) [OK/STALE]

## Summary
[First 3-5 lines of summary.md - status and key facts]

## Recent Sessions
| Date | Session | Summary |
[Last 5 rows from Recent Sessions table]

## Git State
[repo-name]: [branch] - [N uncommitted] - last: [commit message]
[repo-name]: [branch] - clean - last: [commit message]

## Agent Notes
[warning] Rate limiter bypassed on retry path (session: a1b2c3d4, 2d ago)
[context] Refactored to use new node API (session: e5f6g7h8, 5d ago)
--- or ---
No agent notes.

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
3. **All repos checked** - for multi-repo entities, did you check all of them?
4. **Recent sessions present** - did you include the session history for continuity?

## DO NOT

- Start working on the entity without reading its documentation first - that's the whole point
- Skip the staleness check - stale docs lead to wrong assumptions
- Read the full items.json if it's large - just show the 5 most recent items
- Modify any files during pickup - this is read-only context loading
- Report pickup as a "task completed" - it's setup, not work
