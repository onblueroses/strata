# Trace

Show chronological history of an entity across sessions.

## Usage

```
/trace <entity> [period]
/trace my-project 7d          # last 7 days (default)
/trace my-site 14d            # last 14 days
/trace infrastructure 2026-02-11..2026-02-13  # date range
```

Arguments via `$ARGUMENTS`. First arg is entity name, second is optional period.

## Entity Name Resolution

Build the entity list dynamically from your MEMORY.md Entities table. Each entity has a name (directory under `$STRATA_KB/projects/` or `$STRATA_KB/areas/`) and optional aliases. Match the user's input against these directory names (exact match first, then prefix match).

Example pattern:
```
| Name       | Path                   | Aliases             |
|------------|------------------------|---------------------|
| my-project | $STRATA_KB/projects/my-project | proj, mp           |
| my-site    | $STRATA_KB/projects/my-site  | site, frontend      |
| infra      | $STRATA_KB/areas/infra       | vps, server         |
```

If no match found in MEMORY.md, glob `$STRATA_KB/{projects,areas}/*/summary.md` and try prefix matching against the directory names. If still no match, list available entities and ask.

## Instructions

**DO NOT:**
- Scan ALL daily notes if the entity isn't found - ask the user first
- Show raw JSON in the output - format it as readable timeline
- Include sessions where the entity was only tangentially mentioned (not in entities_touched)
- Truncate decision text - decisions with reasoning are the most valuable part of a trace

### 1. Resolve entity

Glob for `$STRATA_KB/projects/*/summary.md` and `$STRATA_KB/areas/*/summary.md`. Extract directory names from the results. Match the user's input against these directory names (exact match first, then prefix match).

If no match, tell the user which entities exist and ask them to clarify.

### 2. Read Recent Sessions table

Read the entity's `summary.md` and extract the `## Recent Sessions` table. This gives the quick overview.

### 3. Scan daily notes

Parse the period argument:
- `Nd` = last N days (default: `7d`)
- `YYYY-MM-DD..YYYY-MM-DD` = explicit date range

Glob daily notes matching `$STRATA_KB/daily/YYYY-MM-DD-*.json` for each date in range. Parse each JSON file and filter by `entities_touched` - match if any entry starts with the entity path (prefix match handles both `$STRATA_KB/projects/my-project` and `$STRATA_KB/projects/my-project/summary.md`).

For each matching note, extract: date, session_name, session_id, summary, decisions.

### 4. VPS log check (optional)

If the entity is infrastructure-related or the `--vps` flag is present, SSH to the VPS and check relevant logs. Replace `ENTITY_NAME` with the resolved entity directory name:

```bash
ssh root@<your-vps-ip> 'grep -ri "ENTITY_NAME" /var/log/ 2>/dev/null | tail -20'
```

Skip silently if SSH fails or returns nothing useful.

### 5. Output

```
TRACE: [entity name]
Period: [start] to [end]
=====================================

## Quick View (from Recent Sessions)
[Table from summary.md]

## Timeline
[Date] session-name (session_id)
  Summary: ...
  Decisions: ...

[Date] session-name (session_id)
  Summary: ...
  ...

## Stats
Sessions: N in period
Last verified: YYYY-MM-DD
```

If no sessions found in the period, say so and suggest expanding the range.
