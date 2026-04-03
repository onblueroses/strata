# Overnight

Multi-hour unattended maintenance session. Scans the knowledge base for structural issues, stale specs, entity staleness, sparse documentation, and cross-entity inconsistencies. Builds a finite work manifest upfront, then processes items one by one with on-disk checkpointing.

Designed to survive compaction and prevent drift over hours of autonomous work.

## Usage

```
/overnight           # Full run (up to 6 hours)
/overnight --dry-run # Build manifest only, no fixes
```

Arguments via `$ARGUMENTS`.

## Safety

- **No SSH, no VPS** - local filesystem only
- **No file deletion** - move to `a trash/archive directory` per convention
- **No remote push** - only local commits
- **No source code modification** - reads project code for enrichment, writes only to `$STRATA_KB/`
- **No improvisation** - only processes items in the manifest. Discoveries become new manifest items.

## Resume Logic

Check for existing manifest at `$STRATA_STATE_DIR/overnight-manifest.json`:

- **Status `running`**: resume from first `pending` item. Do NOT rebuild the manifest.
- **Status `complete`**: warn "Previous overnight run completed. Start fresh?" and stop.
- **No manifest**: proceed to Phase 1 (build manifest).

After compaction: read the manifest. Find the first item with `status: "pending"`. Read `phases_completed` to know which phase you're in. Continue from there.

## Anti-Drift Rules

<details>
<summary>Anti-Drift Rules</summary>

The manifest is the entire anti-drift system:

1. **Build before execute.** Phase 1 builds the complete manifest. Phases 2-4 only consume it.
2. **One item at a time.** Pick the first `pending` item in the current phase. Do it. Mark it `done`. Move on.
3. **No improvisation.** If you discover something unexpected while working an item, append a new item to the manifest with `status: "pending"` - do NOT chase the discovery.
4. **Wall clock check.** Before each item, compare current time against `deadline`. If past deadline, mark all remaining items `skipped` with note "deadline exceeded" and proceed to final commit.
5. **Compaction recovery.** After compaction, read the manifest. The first `pending` item is your next task. The `phases_completed` array tells you which phase you're in.
6. **No phase skipping.** Phases execute in order. Phase N+1 does not start until Phase N's items are all `done` or `skipped`.
7. **Atomic updates.** After completing each item, immediately update its status in the manifest JSON. This is the checkpoint.

</details>

## Phase 1: Manifest Construction

<details>
<summary>Manifest Construction</summary>

This phase does NO fixes. It only scans and builds the work queue.

### 1.0 Setup

1. Parse `$ARGUMENTS` for `--dry-run` flag.
2. Record start time. Calculate deadline (start + 6 hours).
3. Create manifest JSON at `$STRATA_STATE_DIR/overnight-manifest.json` with skeleton:

```json
{
  "created": "ISO-timestamp",
  "session_id": "8-char-id",
  "deadline": "ISO-timestamp-6h-from-now",
  "status": "running",
  "phases_completed": [],
  "summary": { "total_items": 0, "done": 0, "skipped": 0, "deferred": 0, "wall_time_minutes": 0 },
  "items": []
}
```

4. Create follow-up file at `.claude/followup-{session-id}.md` per follow-up convention.

### 1.1 Scan: Structural Tidy

Run /tidy's 9 checks in **report mode** (no fixes). For each finding, append a manifest item:

```json
{ "id": "tidy-N", "category": "structural", "target": "[check name]", "description": "[finding]", "status": "pending", "phase": 2 }
```

### 1.2 Scan: Spec Graveyard

Read first 5 lines of all spec files in `$STRATA_STATE_DIR/specs/`. For each with `Status: in-progress` and `Last updated` older than 14 days, append:

```json
{ "id": "spec-N", "category": "spec-triage", "target": "specs/[filename]", "description": "in-progress since [date], last updated [date]", "status": "pending", "phase": 2 }
```

### 1.3 Scan: Entity Staleness

For each non-DELETED entity in MEMORY.md, read summary.md first 10 lines. Append one item per entity:

```json
{ "id": "stale-N", "category": "staleness-audit", "target": "entity/[name]", "description": "last_verified [date], age [N] days, summary [N] chars", "status": "pending", "phase": 3 }
```

### 1.4 Scan: Enrichment Candidates

From the entity list, identify where summary.md is under 500 chars (excluding frontmatter) or items.json is missing:

```json
{ "id": "enrich-N", "category": "enrichment", "target": "entity/[name]", "description": "[reason]", "status": "pending", "phase": 4 }
```

### 1.5 Scan: Cross-References

Read entities mentioning VPS, ports, domains, PM2 process names, or other entities by name. For each pair sharing infrastructure references:

```json
{ "id": "xref-N", "category": "cross-ref", "target": "entity/[name1] <-> entity/[name2]", "description": "shared ref: [what]", "status": "pending", "phase": 4 }
```

### 1.6 Summary

Update manifest `summary.total_items`. If `--dry-run`, print the manifest summary and stop.

</details>

## Phase 2: Structural Tidy + Spec Graveyard

<details>
<summary>Structural Tidy + Spec Graveyard</summary>

### 2.1 Execute Structural Items

Iterate manifest items where `category == "structural"` and `status == "pending"`. For each:

- Apply /tidy auto-fix rules (MEMORY.md table sync, INDEX.md sync, clear bad Local paths)
- For flag-only items (orphaned dirs, staleness warnings, capacity warnings): mark `done` with a note, add relevant ones to follow-up file
- Check wall clock before each item

### 2.2 Execute Spec Triage

Iterate `category == "spec-triage"` items. For each stale in-progress spec:

- Read Quick Start, Goal, Current Step (enough to understand what it was)
- Change `Status: in-progress` to `Status: abandoned`
- Add `Abandoned: [date] - stale, no activity for [N] days` below Status line
- Do NOT modify any other spec content
- Mark manifest item `done`
- Check wall clock before each item

### 2.3 Phase Commit

Commit: `"overnight: structural tidy + spec graveyard"`. Update manifest `phases_completed`.

</details>

## Phase 3: Entity Staleness Audit

<details>
<summary>Entity Staleness Audit</summary>

The longest phase. Each entity is one manifest item (~5-8 min each, ~23 entities).

### 3.1 Audit Each Entity

For each pending `staleness-audit` item:

1. Read entity's full summary.md and items.json
2. Check: (a) do file paths in summary.md exist on disk? (b) does architecture section match the actual project directory? (c) is roadmap status accurate given Recent Sessions?
3. If everything checks out: update `last_verified` to today, mark `done`
4. If something's wrong but fixable (wrong file path, outdated roadmap status): fix it, mark `done` with note
5. If needs human judgment: add to follow-up file, mark `done` with note "deferred"
6. Check wall clock before each entity

**Allowed modifications to summary.md:**
- `last_verified` date
- File paths that are verifiably wrong
- Roadmap status (in progress / done) based on Recent Sessions evidence
- Recent Sessions table entries

**NOT allowed:**
- Architecture prose rewrites
- Status changes (active/deprioritized/etc.)
- Adding new roadmap items

### 3.2 Phase Commit

Commit: `"overnight: entity staleness audit"`. Update manifest `phases_completed`.

</details>

## Phase 4: Enrichment + Cross-refs + Sweep

<details>
<summary>Enrichment + Cross-refs + Sweep</summary>

### 4.1 Enrich Sparse Entities

For each pending `enrichment` item:

- If summary is under 500 chars: read project source (README, package.json/Cargo.toml, src/ structure). Expand summary.md with accurate architecture, tech stack, and status.
- If items.json is missing: create minimal stub (`[]` or with basic entries from codebase)
- Respect source-of-truth rules: summary.md owns narrative, items.json owns structured details
- Check wall clock before each entity

### 4.2 Validate Cross-References

For each pending `cross-ref` item:

- Read both entities' summary.md and items.json
- Compare shared reference (port, domain, PM2 process name)
- If they agree: mark `done`
- If they disagree: trust the more recently verified entity. If unclear, add to follow-up file.
- Do NOT modify entity content without clear evidence of which side is correct

### 4.3 Sweep (get-to-work lenses)

Execute /get-to-work lenses 2, 3, 5, 7 (roadmap stalls, missing knowledge, follow-through, new opportunities) as a final sweep. Lenses 1, 4, 6 are already covered by Phases 2-3.

New findings: append to manifest as `category: "sweep"` items. Process immediately if under 10 min and before deadline. Otherwise mark `skipped`.

### 4.4 Final Commit

Commit: `"overnight: enrichment + cross-refs + sweep"`. Write completion summary to manifest. Set manifest status to `"complete"`.

</details>

## Completion

<details>
<summary>Completion</summary>

After all phases (or when deadline is reached):

1. Update manifest `summary` with final counts and wall time
2. Set manifest `status` to `"complete"` (or `"interrupted"` if deadline forced stop)
3. Final commit if uncommitted changes exist
4. Present summary:

```
OVERNIGHT - SUMMARY
===================
Duration: Xh Ym
Items: N total (M done, K skipped, J deferred)
Phases: [completed list]
Commits: [hashes]
Follow-up: .claude/followup-{session-id}.md (N items)

Done:
- [category]: [count] items processed
- ...

Deferred (needs your input):
- [entity/spec]: [what needs attention]
- ...
```

5. Run `/end` to close the session.

</details>

## Manifest Schema

<details>
<summary>Manifest Schema</summary>

```json
{
  "created": "2026-04-03T22:00:00Z",
  "session_id": "a1b2c3d4",
  "deadline": "2026-04-04T04:00:00Z",
  "status": "running",
  "phases_completed": [],
  "summary": {
    "total_items": 0,
    "done": 0,
    "skipped": 0,
    "deferred": 0,
    "wall_time_minutes": 0
  },
  "items": [
    {
      "id": "tidy-1",
      "category": "structural",
      "target": "MEMORY.md entity table",
      "description": "1 missing entity, 0 stale",
      "status": "pending",
      "phase": 2,
      "note": "",
      "completed_at": ""
    }
  ]
}
```

**Valid categories:** `structural`, `spec-triage`, `staleness-audit`, `enrichment`, `cross-ref`, `sweep`
**Valid statuses:** `pending`, `done`, `skipped`
**Valid manifest statuses:** `running`, `complete`, `interrupted`

</details>

## DO NOT

- SSH to VPS or check remote state
- Delete files - use `a trash/archive directory` convention
- Push to any remote
- Modify project source code (only read for enrichment)
- Chase discoveries - append to manifest instead
- Skip the wall clock check before each item
- Start a phase before the previous phase's items are all done/skipped
- Rewrite entity architecture prose - only update structural fields
- Run more than the defined phases - no ad-hoc extra work
