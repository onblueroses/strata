<!-- keywords: life directory, entity, knowledge base, summary.md, items.json, knowledge management, daily note json, para structure -->
# Knowledge Management

Three-layer system at `$KB_DIR/`:

| Layer | Location | Purpose |
|-------|----------|---------|
| Knowledge Graph | `$KB_DIR/{projects,areas,resources}/` | Entity-centric state |
| Daily Notes | `$KB_DIR/daily/YYYY-MM-DD-{name}-{session-id}.json` | Session timeline (JSON) |
| Tacit Knowledge | `$KB_DIR/tacit.md` | User patterns, constraints |

## Quick Nav

| Task | Section |
|------|---------|
| Create or update an entity | Entity Structure |
| Decide where data belongs (summary vs items) | Source of Truth |
| Write a daily note JSON | Daily Note JSON Schema |
| Choose storage location for new info | Where to Store What |
| Add a person entity | People Pattern |

## Entity Structure

```
entity-name/
  summary.md    # State, decisions, links (authoritative for entity state)
  items.json    # Structured facts for queries (details not in summary.md)
```

### Entity Conventions

- **`last_verified`**: First line after `## Status` in every summary.md. Format: `last_verified: YYYY-MM-DD`. Updated by /end on every session that touches the entity. Used by /status for staleness alerts (7+ days = STALE, 14+ days = URGENT).

- **`## Recent Sessions`**: Table in summary.md before `## Links`. Capped at 10 rows (oldest removed). Each row: date, session name (session_id), one-line summary. This is the entity's reverse index to sessions - lets you answer "what happened to X?" without grepping daily notes. Updated by /end automatically.

- **`/trace`**: Skill for querying entity history. Reads Recent Sessions table, then scans daily notes for the full timeline.

- **`/reconcile`**: Periodic deep verification of all entities against VPS and local ground truth. Checks that documented claims (auth status, ports, versions, domains, etc.) match actual system state. Fixes clear-cut mismatches, flags ambiguous ones. Updates `last_verified` on all checked entities. Use when /status shows STALE entities or as a weekly review. Supports `--local` flag to skip VPS checks.

## Source of Truth

summary.md and items.json serve different purposes. Don't duplicate between them.

| What | Where | Example |
|------|-------|---------|
| Entity state, status, architecture | summary.md | "optimize-app.immo is live, password-protected" |
| Structured detail for lookup | items.json | specific port numbers, workflow IDs, credentials, gotchas |

**items.json entries must add detail that summary.md doesn't cover.** If summary.md already states a fact clearly, don't repeat it in items.json. Good items.json entries: version numbers, port bindings, credential references, workflow IDs, file paths for specific configs, gotchas, rules.

## Daily Note JSON Schema

```json
{
  "date": "YYYY-MM-DD",
  "session_id": "first 8 chars of CLAUDE_SESSION_ID",
  "session_name": "descriptive-name",
  "project_dir": "$HOME/Work/example",
  "started": "HH:mm",
  "ended": "HH:mm",
  "summary": "2-5 sentences",
  "decisions": ["choice made and why"],
  "outputs": ["files created or modified"],
  "entities_touched": ["$KB_DIR/projects/example"],
  "tags": ["cleanup", "hooks"],
  "takeaway": "One-sentence key learning"
}
```

**Normalization**: `entities_touched` entries must always be directory paths (e.g. `$KB_DIR/projects/myapp`), never file paths (`$KB_DIR/projects/myapp/summary.md`). /end step 3 enforces this by mapping modified paths to MEMORY.md's Entities table. /trace uses prefix matching when scanning older notes that may have the file-path format.

## Where to Store What

- Entity state (status, architecture, decisions) - **summary.md** (authoritative)
- Structured detail for lookup (specific values, IDs, gotchas) - **items.json** (no duplicates of summary.md)
- Existing fact changed - **update in place** (never append a duplicate)
- Session happened, what was done - **Daily note JSON** (at /end)
- User preference or constraint observed - **tacit.md** (keep under 20 lines)
- Technical paths, stack, decisions - **MEMORY.md** (auto-memory)

## People Pattern

`$KB_DIR/resources/people/` - Relationship context for recurring clients, collaborators, stakeholders. Same entity format (summary.md + items.json).

## Cross-linking

Use relative paths: `../projects/x/summary.md`
