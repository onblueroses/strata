# Get to Work

Scan all entities for knowledge debt and autonomously fix what you can. Single pass by default. Use `--cycle` for repeated passes until hard-blocked.

## Usage

```
/get-to-work              # Single pass
/get-to-work --cycle      # Loop until hard-blocked
/get-to-work --dry-run    # Report only, no changes
```

Arguments via `$ARGUMENTS`.

## Safety

- **No SSH, no VPS** - local filesystem only. Use /reconcile for ground-truth verification.
- **No file deletion** - move to ~/to-delete/ per convention.
- **No remote push** - only local commits.
- Create a follow-up file (`.claude/followup-{session-id}.md`). Record uncertain decisions there instead of stopping.

## Instructions

### 0. Setup

1. Parse `$ARGUMENTS` for `--cycle`, `--dry-run` flags.
2. Create the follow-up file at `.claude/followup-{session-id}.md` with required sections.
3. Glob `$STRATA_KB/{projects,areas}/*/summary.md` to build the entity list.
4. Read MEMORY.md entity table for cross-reference.

### 1. Scan (7 lenses)

Run all 7 lenses. Each produces candidate work items with a severity and lens tag.

<details>
<summary>Lens details</summary>

#### Lens 1: Entity staleness (priority: highest)

Read the first 10 lines of each entity's summary.md. Extract `last_verified: YYYY-MM-DD`. Calculate age.

- **7-13 days**: STALE - needs /reconcile
- **14+ days**: URGENT - needs /reconcile immediately
- **Missing date**: flag as NO_DATE

#### Lens 2: Roadmap stalls

For entities with `## Roadmap` tables, check if any "in progress" items have no matching entry in `## Recent Sessions` within the last 14 days. A roadmap item with no recent session activity is stalled.

#### Lens 3: Missing knowledge

- Entities without `items.json` -> flag
- Entities where summary.md is under 200 characters (excluding frontmatter) -> flag as sparse
- Entity dirs that exist in `$STRATA_KB/{projects,areas}/` but aren't in MEMORY.md entity table -> flag as untracked

#### Lens 4: Cross-entity consistency

Read entities that share infrastructure (check for VPS references, shared domains, PM2 process names). Flag when two entities document the same fact differently (port numbers, auth status, versions).

**Skip if** `--dry-run` or fewer than 3 entities loaded.

#### Lens 5: Follow-through from recent sessions

Read today's and yesterday's daily notes from `$STRATA_KB/daily/`. Extract `decisions` and `outputs`. Check if any mention "TODO", "next step", "follow up", or "deferred". Cross-reference against entity backlogs and roadmaps - flag items that were deferred but not tracked.

#### Lens 6: MEMORY.md accuracy

- Entity table vs disk (same as /tidy check 1)
- Reference doc table vs INDEX.md (same as /tidy check 2-3)
- Entity Local paths exist on disk (same as /tidy check 9)

#### Lens 7: New opportunities

Entities with active roadmap items but no sessions in the last 7 days. These are projects with planned work that nobody is touching. Report them as candidates for attention.

</details>

### 2. Prioritize

Sort all findings by priority: staleness > consistency > missing knowledge > stalls > follow-through > accuracy > opportunities.

Group by entity. Present a summary table:

```
SCAN RESULTS
============
| Entity     | Issues | Top Priority |
|------------|--------|-------------|
| my-project | 2      | STALE (12d) |
| ...        | ...    | ...         |

Total: N issues across M entities
```

**If `--dry-run`**: stop here. Present findings and exit.

### 3. Execute

Work through issues in priority order. For each:

1. **Staleness/accuracy fixes** (lenses 1, 3, 6): Update MEMORY.md tables, add missing last_verified dates, create missing items.json stubs. These are safe auto-fixes.
2. **Cross-entity consistency** (lens 4): If ground truth is clear from one entity's more-recent session, fix the stale side. Otherwise, record in follow-up file.
3. **Knowledge gaps** (lens 3): Create minimal items.json for entities missing them. Don't fabricate content - just create the empty `[]` stub.
4. **Stalled roadmaps** (lens 2): Record in follow-up file under "User Input Needed" - these need human judgment about whether to continue, deprioritize, or drop.
5. **Follow-through** (lens 5): Add untracked deferred items to follow-up file under "Skipped Items".
6. **New opportunities** (lens 7): Record in follow-up file under "Borderline Insights".

After each entity's fixes, commit if changes were made: `"get-to-work: [entity-name] maintenance"`.

### 4. Loop or Stop

**If `--cycle`**: return to step 1 with a "follow-through" scan (only lenses 1, 5, 6 - the ones that might have changed). Stop when:
- A full scan produces zero new fixable issues
- All remaining issues are in the follow-up file (need human input)
- 5 cycles completed (safety cap)

**If single pass** (default): proceed to step 5.

### 5. Summary

Present:

```
GET TO WORK - SUMMARY
=====================
Entities scanned: N
Issues found: N (M fixed, K deferred to follow-up)
Commits: [list of hashes]
Follow-up items: N (at .claude/followup-{session-id}.md)

Fixed:
- [entity]: [what was fixed]
- ...

Deferred (needs your input):
- [entity]: [what needs attention]
- ...
```

## DO NOT

- SSH to VPS or check remote state - that's /reconcile's job
- Modify entity summaries beyond structural fixes (missing dates, table entries) - content changes need /reconcile with ground truth
- Delete the follow-up file - /end handles cleanup
- Run more than 5 cycles in --cycle mode
- Spend time on entities marked as DEPRECATED in their summary
