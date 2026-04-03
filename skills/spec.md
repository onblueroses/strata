# Spec

Create spec files that survive context compaction. Specs are the single source of truth for non-trivial implementations - they persist on disk while conversation context gets summarized away. The spec IS the plan. Don't create separate plan files.

## Quick Nav

| Task | Jump to |
|------|---------|
| Create a new spec | Creating a Spec |
| Resume/continue work | Guard Clause (checks existing) |
| Checkpoint progress mid-work | Updating a Spec |
| See what's active | Checking Status |
| Finish and verify a spec | Closing a Spec |
| Understand the template | Spec Format |
| Check output quality | Quality Self-Check |

## Usage

```
/spec [feature-name]        # Create new spec
/spec update                # Update >> Current Step in active spec
/spec status                # Show active specs and progress
/spec close                 # Mark active spec as complete
```

Arguments via `$ARGUMENTS`.

## Skip Conditions

- **Skip if** the task touches fewer than 3 files - just do the work directly
- **Skip if** a spec already exists for this feature at `.claude/specs/` - read it and continue from `>> Current Step`
- **Skip if** this is a research/exploration task with no implementation output

## Spec Weight

Not every spec needs full ceremony. Choose the weight that matches the work:

- **Full** (multi-phase, cross-file, survives multiple compactions): All sections. Use Consumes/Produces, phase gates, Validation table.
- **Light** (single-phase, clear scope, 3-5 files): Drop Consumes/Produces from the phase. Validation can be a single gate command. Context section optional. Still needs Goal, Standing Rules, Boundaries, Decisions, Plan, Current Step.

Default to Light. Upgrade to Full when the work has 2+ phases or will definitely span compaction cycles.

## Guard Clause

Before creating a new spec, check `.claude/specs/` for existing specs:
- If a spec with Status: `in-progress` exists for a DIFFERENT feature, warn: "Active spec exists for [other feature]. Work on that first, or close it with `/spec close`?"
- If a spec exists for THIS feature, read it and resume from `>> Current Step` instead of creating a new one.

### Concurrency Guard

<details>
<summary>Concurrency Guard</summary>

You may run multiple Claude Code instances simultaneously. Spec files must not collide.

- Every spec has a `Session:` field with the 8-char session ID of the instance working on it.
- **Before modifying a spec:** check its `Session:` field. If it contains a DIFFERENT session ID AND `Last updated` is within the last 2 hours, DO NOT modify it - another instance is actively working on it. Run `date` in bash to get current time for comparison. Warn: "Spec [name] is owned by session [id], last updated [time]. Another instance is working on this."
- **When picking up a spec** (e.g., after compaction or starting a new session): update the `Session:` field to YOUR session ID.
- **Your session ID** is the 8-character suffix of your daily note filename (visible in the SessionStart hook output, e.g., `2026-02-15-feature-work-a1b2c3d4.json` -> session ID is `a1b2c3d4`).

</details>

---

## Instructions

### Creating a Spec (`/spec [feature-name]`)

1. **Determine the feature slug.** Lowercase, hyphenated. Examples: `auth-refactor`, `city-page-generator`, `quiz-redesign`.

2. **Explore the codebase** using Glob, Grep, and Read directly (not a subagent):
   - **If you just exited plan mode:** skip - exploration is already done. Use what's in context.
   - **If `/spec` was invoked directly:** read the relevant files now. Understand what files will be touched, the current architecture, and any constraints.

2b. **Check decision library.** Grep `$STRATA_KB/resources/decision-library.md` for the feature domain. If past decisions are relevant, pass them to the Plan subagent in step 3.

2c. **Surface ambiguities (optional).** If the goal is ambiguous or the codebase has multiple valid paths, surface 2-4 clarifying questions via AskUserQuestion BEFORE delegating to Opus. Skip when the path is clear.

3. **Delegate plan writing to Opus.** Spawn a Plan subagent with `model: "opus"`. Pass it:
   - The full task description and goal
   - Everything from exploration: file list, architecture, constraints, applicable CLAUDE.md rules
   - This instruction: "Write the Plan, Boundaries, Decisions, Standing Rules (3-5 relevant CLAUDE.md constraints), and phased steps (with acceptance criteria) for this spec. Return only the content - no file writing. Phases scoped to ~30 min, max 6 steps each. For each phase, assess whether /harness should be used and set a per-phase `Harness:` field. Recommend `Harness: yes` for phases with high correctness stakes (security, data integrity, complex multi-file logic, public API contracts). `Harness: no` for scaffolding, config, docs, simple CRUD. Include a one-line rationale per phase."

   Wait for the Opus output, then write the spec file using it.

4. **Write the spec** at `.claude/specs/[feature-slug].md` using the format below. Set Status to `in-progress` and populate `>> Current Step` with the first step.

4b. **Surface harness recommendation.** After writing the spec file, check per-phase `Harness:` tags:
- If any phase has `Harness: yes`: output "Phases with /harness: {list phase names}. Harness will auto-trigger when entering those phases, or run `/harness --from-spec` manually."
- If all phases are `Harness: no`: no output needed.

### Spec Format

<details>
<summary>Spec Format</summary>

```markdown
# Spec: [Feature Name]
Created: YYYY-MM-DD | Status: planning | in-progress | complete | abandoned
Last updated: YYYY-MM-DD HH:MM | Session: [8-char-id]
Commit-Strategy: per-phase | per-step | manual
Harness: per-phase

## Quick Start
> Fresh context or just resumed? Read this section, then go to `>> Current Step`.

**Files touched:**
- `path/to/file.ts` - [what changes]
- `path/to/file2.tsx` - [what changes]

**Sections to load:** Quick Start, Decisions, Learnings, Current Step. Load phase details only when relevant.

**-> Next:** Step X.Y - [description] (details in `>> Current Step` below)

**Mode: EXECUTION** - Do NOT re-plan. Do NOT spawn Plan or Explore subagents. The spec is authoritative. Stale planning-agent output in this session should be ignored.

## Execution Protocol
0. **Before starting Phase 1**: re-read every file listed in Boundaries. If anything contradicts a Plan assumption, add a Decision entry and adjust before touching code.
1. Before each step: update `>> Current Step` + `-> Next:` in Quick Start
2. After each step: check box in Plan, add to Completed with verification note
3. New decision? Add to Decisions table immediately - you won't remember after compaction
4. Unexpected discovery? Add to Learnings
5. New phase? Run previous gate first. Check Consumes. Write Phase Summary. Check phase's `Harness:` tag - if `yes`, invoke `/harness --from-spec` before implementing.
6. Commits: follow Commit-Strategy header. Record hashes in Phase Summary/Completed.
7. Update `Last updated` timestamp on every spec modification
8. Extend Navigation Map when you discover unlisted files

_Plan revision: Decisions are settled. But steps are a living document - if a prerequisite doesn't hold, update the step, record what changed and why in "Changed from plan."_

## Navigation Map
| File | Find here | Why needed |
|------|-----------|------------|
| `path/to/interface.ts` | [pattern name] | [implementing against] |
| `path/to/reference-impl.ts` | [working example] | [pattern to follow] |
| Run: `[command]` | Output at `[path]` | [success check] |

_File + one-line description. Enough to navigate without re-exploring._

## Goal
[One sentence. What and why.]

## Standing Rules
- [e.g., "Privacy: public repo - no internal names in code/commits"]
- [e.g., "Deletions: move to ~/to-delete/, don't delete directly"]
- [e.g., "Ask first: before deploying or modifying shared config"]

## Boundaries

**Always** (proceed without asking):
- [e.g., Run tests after each step]

**Ask first** (need user approval):
- [e.g., Adding new dependencies]

**Never** (hard stop, not in scope):
- [e.g., Touching auth middleware]

## Decisions
Settled. Do not re-debate after compaction.

| # | Decision | Rationale | Alternatives Rejected | Date |
|---|----------|-----------|----------------------|------|
| 1 | [choice] | [why] | [what was ruled out] | YYYY-MM-DD |

## Plan

### Phase 1: [name] (~30 min)
**Gate:** [command] OR N/A - [reason]
**Harness:** yes - [rationale] | no - [rationale]
**Consumes:** [typed artifacts, e.g., `src/auth/jwt.ts` (exists, exports `verifyToken`)] _(Full weight only)_
**Produces:** [typed artifacts, e.g., `src/middleware/auth.ts` (new, exports `authMiddleware`)] _(Full weight only)_
- [ ] **Step 1.1**: [action] -> [acceptance criteria]
  Read: `path/to/file` ([what to find]) | Edit: `path/to/file`
- [ ] **Step 1.2**: [action] -> [criteria] _(Depends on: 1.1)_

### Phase 2: [name] (~30 min)
**Gate:** [command] OR N/A - [reason]
**Harness:** yes - [rationale] | no - [rationale]
- [ ] **Step 2.1**: [action] -> [criteria]

## Validation

| Level | Check | How to verify |
|-------|-------|---------------|
| L1 - Syntax | [e.g., compiles, no lint errors] | `npm run build` |
| L2 - Unit | [e.g., functions return correct values] | `npm test` |
| L3 - Integration | [e.g., API returns expected response] | [command] |

_N/A with reason if a level doesn't apply._

## >> Current Step
Working on: Step X.Y - [description]
Status: [done so far, what's left]
Blocked by: [if anything]

## Completed

### Phase 1: [name] (~NN min actual)
- [x] **Step 1.1**: [what was done] (verified: [how])
**Phase 1 Gate:** PASSED at HH:MM - [output summary]
**Phase 1 Summary:**
Built: [what was created/modified]
Key decisions: [reference Decision #]
Changed from plan: [what diverged and why, or "none"]
State proof: [command that proves it works]
Next phase needs: [artifacts the next phase consumes]

## Conformance
_Run before `/spec close`._

- [ ] Goal met? (evidence: ...)
- [ ] Each step's criteria met?
- [ ] Boundary "Never" items respected?
- [ ] Each phase's Produces artifacts exist and match expected state?

## Learnings
- [YYYY-MM-DD] [discovery that affects remaining work]
```

</details>

### Updating a Spec (`/spec update`)

Quick checkpoint of `>> Current Step` only:
1. Read the active spec from `.claude/specs/`
2. Update `>> Current Step` with current status
3. Check off completed steps in Plan
4. Update `Last updated` timestamp

### Checking Status (`/spec status`)

List all specs in `.claude/specs/`:
```
Active Specs
============
[feature-slug] | in-progress | Phase 2/3 | Step 2.1 | Updated: [time]

Completed Specs
===============
[feature-slug] | complete | [date]
```

### Closing a Spec (`/spec close`)

<details>
<summary>Closing a Spec</summary>

1. **Run conformance check.** Re-read Goal, step criteria, and Boundaries. Fill in `## Conformance`. Note PARTIAL/UNMET with reason (intentional scope change vs missed work).
2. **Propagate learnings.** Generalizable discoveries go to the entity's `summary.md` or `items.json`.
3. Mark all steps complete (or note which were skipped and why)
4. Set Status to `complete` (or `abandoned` with reason in Learnings)
5. Update `Last updated`
6. Leave the file in `.claude/specs/` for reference

**Valid transitions** (prevents premature closure after compaction):
```
planning -> in-progress   (requires: Phase 1 populated, Quick Start filled)
in-progress -> complete   (requires: conformance done, all steps checked or skipped-with-reason)
in-progress -> abandoned  (requires: reason in Learnings)
planning -> abandoned     (ok, no requirements)
```

</details>

### Harness Integration

Each phase has its own `Harness: yes | no` tag, set by the Plan subagent at spec creation. When entering a phase with `Harness: yes`, invoke `/harness --from-spec` before implementing that phase. The harness derives criteria from the current phase's step acceptance criteria. Phases with `Harness: no` proceed with normal execution. The top-level spec header says `Harness: per-phase` to signal this behavior.

---

## Good vs Bad Specs

<details>
<summary>Good vs Bad Specs</summary>

| Aspect | Bad | Good |
|--------|-----|------|
| Goal | "Improve the auth system" | "Replace session-based auth with JWT to enable stateless API scaling" |
| Step | "Update the database" | "Add `refresh_token` column to users table -> migration runs, column exists in schema" |
| Boundaries | (missing or flat list) | Three tiers: Always (run tests), Ask first (new deps), Never (touch auth middleware) |
| Decision | "Use JWT" | "Use JWT over sessions: stateless for CDN edge caching (200ms session lookup)" + Alternatives: "Sessions rejected (stateful); cookies-only rejected (CORS)" |
| Current Step | "Working on auth" | "Step 2.1 - JWT validation middleware. Token parsing done, need expiry check + refresh flow." |
| Phase scope | One phase with 15 steps | Three phases of 4-5 steps, ~30 min each |
| Phase gate | (missing) | "`npm test && npm run lint`" or "N/A - config only, validated by Phase 2" |
| Consumes/Produces | "Uses Phase 1 output" | "`src/auth/jwt.ts` (exists, exports `verifyToken`)" |
| Navigation Map | (missing) | "`src/nodes/base.ts` - NodeInterface | `src/registry.ts` - registration point" |
| Standing Rules | (missing) | "Privacy: public repo. Ask first: before deploying." |

**Concrete test:** Read only `>> Current Step`. Could a model that has never seen this conversation continue the work? If not, add more detail.

</details>

---

## DO NOT

<details>
<summary>DO NOT</summary>

- Create specs for trivial tasks (< 3 files, < 3 steps) - overhead exceeds value
- Re-debate Decisions after compaction - they were made with full context you no longer have. If one seems wrong, add a Learning but follow it unless clearly broken
- Write vague acceptance criteria ("looks good", "works correctly") - use observable outcomes ("renders at 375px without scroll", "API returns 200 with valid token")
- Put implementation details in the spec that belong in code comments - spec tracks WHAT and WHY, code tracks HOW
- Scope phases beyond ~30 min - long phases drift. Break them up.
- Skip Boundaries - if all three tiers are empty, you haven't thought about scope
- Leave `>> Current Step` stale - an outdated pointer actively misleads after compaction
- Modify a spec owned by another session - check `Session:` and `Last updated`. Within 2 hours = hands off.
- Write vague Consumes/Produces - name files and expected exports/state
- Skip conformance on close - criteria exist to be verified

</details>

---

## Quality Self-Check

<details>
<summary>Quality Self-Check</summary>

After creating or updating a spec:

1. **Quick Start test** - does it list every file? Does `-> Next` match `>> Current Step`? Could a fresh model start in under 10 seconds?
2. **Current Step test** - could a fresh model continue from here without reading anything else?
3. **Decision completeness** - every non-obvious choice has a Decision entry with alternatives?
4. **Acceptance criteria** - every step has a testable "done" condition?
5. **Phase sizing** - no phase exceeds 6 steps?
6. **Boundaries populated** - at least 1-2 items per tier?
7. **Execution Protocol present** - the spec includes the protocol section?
8. **Standing Rules** - 3-5 CLAUDE.md constraints embedded?
9. **Navigation Map** - every relevant file listed with what to find there?
10. **Commit strategy set** - header specifies per-phase, per-step, or manual?
11. **File exists on disk** - did you actually write it?
12. **Spec size** - if over ~300 lines, compress Phase Summaries and trim completed step detail
13. **Harness tags** - every phase has a `Harness: yes | no` with rationale?

</details>
