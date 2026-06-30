---
description: |
  Lightweight knowledge base hygiene. No SSH, no ground truth - just structural consistency.
  Manual: invoke standalone for full check + auto-fix. Not called by /end - run independently when needed.
---

# Tidy

Structural consistency check for the knowledge base. /tidy checks structure. a ground-truth reconcile checks truth. Don't overlap.

No SSH, no VPS, no ground truth verification. Just: are the indexes accurate, are the references valid, is anything orphaned or approaching limits?

## Usage

```
/tidy           # Full check + auto-fix
/tidy --report  # Report only, no fixes
```

Arguments via `$ARGUMENTS`.

## Checks

Run all 9 checks. Collect findings, then fix what's safe.

### 1. MEMORY.md entity table vs disk

Glob `$KB_DIR/{projects,areas}/*/summary.md`. Compare against the Entities table in MEMORY.md.

- **Missing from table**: entity dir exists on disk but not in MEMORY.md
- **Stale in table**: entity listed in MEMORY.md but no directory/summary.md on disk
- **Auto-fix**: add missing entries to table with blank Local/CLAUDE.md columns

### 2. Reference doc INDEX.md vs disk

Glob `$STRATA_HOME/reference/*.md` (excluding INDEX.md). Compare against entries in `$STRATA_HOME/reference/INDEX.md`.

- **Missing from INDEX**: file exists but no entry
- **Stale in INDEX**: entry exists but file doesn't
- **Auto-fix**: add missing entries with placeholder "Read when" value; remove stale entries

### 3. MEMORY.md reference table vs INDEX.md

Compare MEMORY.md's Reference Docs table against INDEX.md. INDEX.md is authoritative.

- **Out of sync**: entry in one but not the other, or descriptions differ
- **Auto-fix**: update MEMORY.md table to match INDEX.md

### 4. Orphaned entity directories

Find directories under `$KB_DIR/{projects,areas}/` that exist but have no `summary.md`.

- **Flag only** - may be intentional stubs or work in progress

### 5. Stale last_verified dates

Read first 10 lines of each entity's summary.md. Extract `last_verified:`.

- **7-13 days**: STALE
- **14+ days**: URGENT
- **Missing**: NO_DATE
- **Flag only** - content may still be accurate. Suggest a ground-truth reconcile for urgent ones.

### 6. Decision library capacity

Read `$KB_DIR/resources/decision-library.md`. Count entries (lines matching `^##` domain headers and their sub-entries).

- **40+ entries**: approaching 50-cap, warn
- **50+ entries**: at cap, suggest pruning
- **Flag only**

### 6b. Resources INDEX.md vs disk

Glob `$KB_DIR/resources/evaluations/*.md` and `$KB_DIR/resources/research/*.md`. Compare against entries in `$KB_DIR/resources/INDEX.md`.

- **Missing from INDEX**: file exists but no row in the table
- **Stale in INDEX**: row exists but file doesn't
- **Auto-fix**: add missing rows (read frontmatter for type/date/source/entities); remove stale rows

### 7. Unnamed daily notes

Glob `$KB_DIR/daily/[today]-*unnamed*.json`.

- **Flag**: list unnamed sessions from today that should be named
- **Flag only** - naming is subjective

### 8. Tacit.md line count

Read `$KB_DIR/tacit.md`. Count non-empty lines.

- **18+ lines**: approaching 20-line cap, warn
- **20+ lines**: at cap, suggest pruning
- **Flag only**

### 9. Entity Local path verification

For each entity in MEMORY.md that has a Local column value, check if that directory exists relative to `$HOME/`.

- **Path missing**: directory doesn't exist on disk
- **Auto-fix**: clear the Local value if the path is definitely wrong (not just unmounted)

## Output

```
TIDY REPORT
===========
| # | Check | Findings | Action |
|---|-------|----------|--------|
| 1 | Entity table | 1 missing, 0 stale | Auto-fixed |
| 2 | Ref INDEX.md | 0 issues | OK |
| 3 | Ref table sync | 1 out of sync | Auto-fixed |
| 4 | Orphaned dirs | 0 | OK |
| 5 | Staleness | 2 STALE, 1 URGENT | Flagged |
| 6 | Decision lib | 42/50 entries | Warning |
| 6b | Resources INDEX | 0 issues | OK |
| 7 | Unnamed notes | 1 today | Flagged |
| 8 | Tacit.md | 15/20 lines | OK |
| 9 | Local paths | 0 missing | OK |

Auto-fixed: N items
Flagged: M items (need manual attention)
```

After the report, list each flagged item with enough detail to act on it.

## Auto-fix Rules

| Check | Safe to fix | How |
|-------|------------|-----|
| 1 - Missing entity | Yes | Add row to MEMORY.md table |
| 1 - Stale entity | No | Flag - may have been moved |
| 2 - Missing INDEX entry | Yes | Add entry with placeholder |
| 2 - Stale INDEX entry | Yes | Remove entry |
| 3 - Table out of sync | Yes | Update MEMORY.md to match INDEX.md |
| 4-8 | No | Flag only |
| 6b - Missing INDEX row | Yes | Add row from frontmatter |
| 6b - Stale INDEX row | Yes | Remove row |
| 9 - Path missing | Conditional | Clear if obviously wrong, flag if unclear |

**If `--report`**: skip all auto-fixes. Report only.

## DO NOT

- SSH to VPS or check service state - that's a ground-truth reconcile
- Modify entity summary.md content beyond structural fields (last_verified dates, table entries)
- Delete any files - flag for manual review
- Run more than the 9 listed checks - keep this fast and focused
- Overlap with a ground-truth reconcile's ground-truth verification (steps 2-5 in reconcile)
