---
name: spec
description: "Create and manage implementation specs that survive compaction: the spec is a navigation chart, not a railroad. Frozen zone (Goal, Boundaries, Decisions, Trail), one live Frontier planned just-in-time, coarse Territory sketch beyond it. MANDATORY on plan-mode exit for work touching 3+ files. Triggers on: 'write a spec', 'spec this out', 'persist the plan', 'advance the frontier'. Skip for 1-2 files."
---

# Spec

Goal: Persist the destination, invariants, decisions, and live execution state of non-trivial work in one artifact that a fresh context can continue from.

Success means:
  - Specs live at `$SPECS_DIR/{name}.md` and serve as the single source of truth after compaction.
  - Detail concentrates where it is true: Goal/Boundaries/Decisions/Trail are authoritative, exactly one Frontier carries full detail, and Territory beyond it stays coarse and provisional.
  - Frontier-entry gates run at entry time: Harness/BoN criteria are authored when a frontier opens, PDMC passes before any `Harness: yes` implementation, and the mutex holds.

Stop when: The spec is created, advanced, updated, reported, or closed according to the requested `/spec` action, with `Last updated` refreshed and `>> Current Step` accurate.

## The model

A spec is a chart for territory that reveals itself on contact, held in three temperature zones:

- **Frozen** (collapsed past): Goal, Standing Rules, Boundaries, Decisions, Trail. Written when something actually settles; authoritative after compaction.
- **Live** (the frontier): one open Frontier, the next ~30-90 min, planned at entry with everything the Trail has taught. All step detail, criteria, and numbers live here.
- **Sketch** (uncollapsed future): Territory. Coarse bullets, free to redraw at every frontier boundary.

The plan-time job is small: fix the destination and the invariants, sketch the territory, detail only the first move. Each subsequent move is planned on contact, when the plan can be true. Numbers are hypotheses with a stated basis (measured, derived, or crash-and-halve), sized when the frontier reaches them: the resource-sizing rule applied to plans.

Criteria blocks are rubrics in the managed-agents sense (explicit, gradeable conditions); /harness grades them via Codex, /best-of-n via this session judging diffs. Authoring them at frontier entry, with contact-informed context, makes them sharper than plan-time fiction about unvisited phases.

## When to use

- Also triggers when a 3+ file implementation starts without plan mode.
- More trigger phrases: 'spec status', 'update the spec', 'close the spec', 'continue the spec', 'advance the frontier', 'next frontier'.
- Pairs with /grill and /recon (upstream, by judgment), /codex-review --plan (creation review at 3+ files; risky frontiers by judgment), /harness (`Harness: yes` frontiers), /best-of-n (`BoN: yes` frontiers), /verify (Full/Deep tiers check spec currency).

## Quick Nav

| Task | Jump to |
|------|---------|
| Create a new spec | Creating a Spec |
| Close a frontier and open the next | Advancing the Frontier |
| Resume/continue work | Guard Clause (checks existing) |
| Checkpoint progress mid-work | Updating a Spec |
| See what's active | Checking Status |
| Finish and verify a spec | Closing a Spec |
| Understand the template | Spec Format |
| Old-format specs | Existing Specs |
| Check output quality | Quality Self-Check |

## Usage

```
/spec [feature-name]              # Create new spec
/spec [feature-name] --no-codex   # Skip creation review (use sparingly)
/spec advance                     # Close the open frontier, open the next
/spec update                      # Update >> Current Step in active spec
/spec status                      # Show active specs and progress
/spec close                       # Mark active spec as complete
```

## Skip Conditions

- **Skip if** the task touches fewer than 3 files: just do the work directly.
- **Skip if** a spec already exists for this feature at `$SPECS_DIR/`: read it and continue from `>> Current Step`.
- **Skip if** this is a research/exploration task with no implementation output.

On plan-mode exit, a spec is mandatory for work touching 3+ files; below that threshold it is optional (same rule as the CLAUDE.md Planning constraint).

## Guard Clause

Check `$SPECS_DIR/` for existing specs before creating a new one.

- If a spec with Status: `in-progress` exists for a DIFFERENT feature, warn: "Active spec exists for [other feature]. Work on that first, or close it with `/spec close`?"
- If a spec exists for THIS feature, read it and resume from `>> Current Step` instead of creating a new one.

### Concurrency Guard

Concurrent sessions require ownership isolation. Give every active spec one clear owner.

- Every spec has a `Session:` field with the 8-char session ID of the instance working on it.
- **Before modifying a spec:** check its `Session:` field. If it contains a DIFFERENT session ID AND `Last updated` is within the last 2 hours, leave it unchanged because another instance is actively working on it. Run `date` in bash to get current time for comparison. Warn: "Spec [name] is owned by session [id], last updated [time]. Another instance is working on this."
- **When picking up a spec** (e.g., after compaction or starting a new session): update the `Session:` field to YOUR session ID.
- **Your session ID** is the 8-character suffix of your daily note filename (visible in the SessionStart hook output).

---

## Creating a Spec (`/spec [feature-name]`)

1. **Determine the feature slug.** Lowercase, hyphenated: `auth-refactor`, `quiz-redesign`.

2. **Gather what the chart needs.** The chart needs enough to fix the destination, the invariants, and the first move; the rest reveals itself on contact.
   - **Skip if** you just exited plan mode: use the exploration already in context.
   - Invoke `/recon {feature-slug}` when the codebase is outside working memory and the first frontier or the boundaries depend on facts you'd otherwise guess; direct Glob/Grep/Read covers obvious scopes faster.
   - Invoke `/grill` when user-provided intent is thin or the goal has unresolved decision branches (recon covers code facts; /grill covers intent).
   - Grep `$KB_DIR/resources/decision-library.md` for the feature domain; carry relevant past decisions into the Decisions seed.
   - Surface genuine forks via AskUserQuestion (load /ask-better first) BEFORE writing the chart.

3. **Draft the chart.** Write, in this order:
   - **North Star**: Goal (one sentence), Success means (checkable), Stop when.
   - **Standing Rules + Boundaries**: the 3-5 CLAUDE.md constraints that bind this work; Always / Ask first / Never tiers.
   - **Seed Decisions**: only choices actually being made now (architecture commitments needed to start), each with rationale, alternatives rejected, and a `Re-examine when` trigger (`—` for final).
   - **Territory sketch**: coarse bullets from here to the Goal. One line each. Steps, criteria, and numbers wait for their frontier.
   - **First frontier**: full detail per the template: intent, Needs (verified to exist NOW), steps with gradeable done-conditions, Gate, Harness/BoN decision with rationale, numbers with basis.

   Draft inline by default: this session holds the intent. Dispatch the strong-lane planner with `bin/strong` and `references/planner-instruction.md` when the first frontier is itself heavy architecture (wrapper reference: `reference/model-delegation.md`; pass `< /dev/null` when backgrounded).

4. **Adversarial creation review.** Freeze the draft to `/tmp/spec-draft-{feature-slug}.md`, then review it before writing the spec:
   - **Skip if** the work touches fewer than 3 files, or the user passed `--no-codex` (record "Codex plan review skipped per user request" as Decision #0).
   - **Procedural lens**: invoke `/codex-review --plan /tmp/spec-draft-{feature-slug}.md`. The review targets the North Star, Boundaries, Territory shape, and first frontier: claims that are checkable now.
   - **PDMC lens** (only when the FIRST frontier is `Harness: yes`): extract Frontier 1 from the frozen draft as the PDMC artifact and dispatch the PDMC pass per Advancing the Frontier, in parallel with the procedural lens (both lenses run in parallel against the same frozen snapshot, per CLAUDE.md; the procedural lens reads the whole chart, PDMC reads the frontier).
   - Merge findings into one rework brief and apply in a single revision pass: BLOCKING -> revise before writing; IMPORTANT -> address inline or record in Decisions with explicit "rejected because" rationale; ADVISORY -> apply when trivial, else note; PDMC FAIL -> hard gate, rework and rerun.
   - If the verdict is BLOCK twice: surface to the user via AskUserQuestion (load /ask-better; show plan and Codex stance side by side via `preview`). Options: revise scope, accept Codex's stance, proceed with documented rationale.
   - Record in Decisions: `Codex plan review: [N] BLOCKING, [N] IMPORTANT addressed; [N] ADVISORY noted.`

5. **Write the spec** at `$SPECS_DIR/[feature-slug].md` by copying `references/spec-format.md` verbatim and filling every placeholder. /harness, /best-of-n, and the compaction hooks grep the field names: keep `## >> Current Step`, `Harness:`, `BoN:`, `#### Harness Criteria`, `#### BoN Criteria`, `#### PDMC Methodological Review`, `Aggregate verdict:`, `## Read On Resume`, `Status:`, and `Session:` unchanged.

   Done when the file exists at the canonical path with `Status: in-progress`, `Session:` set, `>> Current Step` pointing at Frontier 1 Step 1.1, exactly one Frontier open, and Territory sketched.

6. **Surface frontier gates.** If Frontier 1 is `Harness: yes`: "Frontier 1 is Harness-gated: PDMC recorded, run `/harness --from-spec` before implementing." If `BoN: yes`: "Frontier 1 is BoN-gated: run `/best-of-n --from-spec`." If both: ABORT with "Spec malformed: Frontier 1 has both Harness and BoN tagged. Fix the spec."

Optionally run `/void --self` on the finished chart to surface the comfortable absence the plan satisfies on paper.

## Advancing the Frontier (`/spec advance`)

The core loop. Run when the open frontier's gate passes (or the frontier is explicitly abandoned).

1. **Close on a terminal state.**
   - Gate passes -> write the Trail entry (newest first): Built, Decisions made, Surprises (territory vs sketch), Redrawn, State proof, commit hash per Commit-Strategy. Collapse the closed frontier out of `## Frontier`: the Trail entry is its record.
   - Gate fails or `Blocked by` is set -> the frontier stays open; record the evidence in `>> Current Step`, keep working or surface the blocker. Advance only on a terminal state.
   - Frontier abandoned -> Trail entry marked `⛔ ABANDONED` with the reason and what state remains; claim no PASS.
   - Stop-when met -> open nothing; go to `/spec close`.
2. **Reread with fresh experience.** Trail, Territory, Decisions, Learnings. This accumulated contact is the planning context the waterfall never had.
3. **Redraw Territory** as the experience demands: reorder, merge, split, kill, add. Redrawing is free; it is sketch. Note significant redraws in the Trail entry just written. Killing a territory item follows forward expected value, never sunk cost.
4. **Open the next frontier.** Pick the move that best advances toward Stop-when given the Trail. Write Frontier N+1 per the template: heading, Needs (verify each exists NOW; a missing Need means the frontier is wrong or the territory shifted), steps with gradeable done-conditions, Gate, Numbers basis. Decide Harness/BoN with a one-line rationale each:
   - `Harness: yes` for high correctness stakes: security, data integrity, complex multi-file logic, public API contracts, probe/harness methodology.
   - `BoN: yes - [rationale] [N=K]` (default N=3, max 5) when multiple credible designs exist and picking wrong is costly.
   - Both `no` for scaffolding, config, docs, simple CRUD.
   - **MUTEX HARD-FAIL**: both `yes` on one frontier is malformed; stop and report to the user.

   Immediately update `>> Current Step`, `-> Next:` in Quick Start, and `Last updated`: /harness and /best-of-n locate the live frontier through the pointer, so it moves before any gate runs.
5. **Review risky frontiers** (judgment, not rule): irreversible actions, schema changes, security surface, money paths -> `/codex-review --plan` on the frontier text now, before any generation starts.
6. **Run entry gates before implementing.**
   - `Harness: yes` -> author `#### Harness Criteria` (gradeable observables in `C1: ... -> PASS if ..., FAIL if ...` format; when criteria feel hard to author, simulate a known-good implementation and derive criteria from the observable properties that make it good). Dispatch the PDMC pass: codex with the frontier text + `references/pdmc-checklist.md`, framed per `references/planner-instruction.md`, backgrounded with `< /dev/null`. Paste per-item verdicts and `Aggregate verdict: PASS` into `#### PDMC Methodological Review` before proceeding; any applicable FAIL blocks the frontier until reworked. Then invoke `/harness --from-spec`. Hard gate.
   - `BoN: yes` -> author `#### BoN Criteria` observable from a candidate's git diff alone, then invoke `/best-of-n --from-spec`. Hard gate.
7. **Size discipline.** Keep the active spec at or under ~300 lines: compress Trail entries to ~10 lines, move overflow detail to `{slug}-artifacts/`, keep exactly one frontier detailed.

## Updating a Spec (`/spec update`)

1. Read the active spec (`Status: in-progress`) from `$SPECS_DIR/`.
   - If zero specs are in-progress: report "No active spec" and stop.
   - If several are in-progress: pick the one matching the current project/entity; when ambiguous, ask via AskUserQuestion.
2. Update `>> Current Step` with current status and sync `-> Next:` in Quick Start to match.
3. Check off completed steps in the Frontier.
4. Update `Last updated` timestamp.

## Checking Status (`/spec status`)

List specs in the top level of `$SPECS_DIR/`; skip `archive/` and legacy `_archive/`.

```
Active Specs
============
[feature-slug] | in-progress | Frontier 3: [name] | Step 3.2 | Territory: 4 items | Updated: [time]

Completed Specs
===============
[feature-slug] | complete | [date]
```

## Closing a Spec (`/spec close`)

Resolve the active spec as in `/spec update` (zero in-progress: report and stop; several: match by project, else ask).

1. **Run conformance check.** Re-read Goal, Boundaries, Trail. Fill in `## Conformance`. Territory items still open are either waived with reason (intentional scope cut) or the spec stays open.
2. **Propagate learnings.** Generalizable discoveries go to the entity's `$KB_DIR/{entity}/summary.md` or `$KB_DIR/{entity}/items.json`.
3. Set Status to `complete` (or `abandoned` with reason in Learnings).
4. Update `Last updated`.
5. Move the closed file into `archive/` inside the specs directory (`archive/` is canonical; `_archive/` is legacy, add nothing to it), or leave it top-level while still referenced.

**VALID TRANSITIONS** (prevents premature closure after compaction):
```
planning -> in-progress   (requires: Frontier 1 populated, Quick Start filled)
in-progress -> complete   (requires: conformance done, Territory cleared or waived-with-reason)
in-progress -> abandoned  (requires: reason in Learnings)
planning -> abandoned     (ok, no requirements)
```

## Existing Specs (old format)

Specs on disk with phased Plans (Phase 1..N pre-written) execute as written: each carries its own embedded Execution Protocol, and that protocol is authoritative for it. At a phase boundary you may convert one to this format, fully or not at all: copy the new template and refill every section (embedded Execution Protocol, Decisions schema with `Re-examine when`, Success means / Stop when, both pointers); the current phase becomes the Frontier, remaining phases collapse into Territory bullets (pre-written detail moves to `{slug}-artifacts/` if worth keeping), Completed becomes the Trail. Validate the result against the Quality Self-Check before continuing. A spec runs its old embedded protocol or the new one; a hybrid is malformed. Convert only specs your session owns.

## Spec Format

The full template lives at `references/spec-format.md`; copy it verbatim and fill every placeholder. Sections: header, Quick Start, Execution Protocol, Goal (+ Success means / Stop when), Standing Rules, Boundaries, Decisions, Navigation Map, `>> Current Step`, Frontier (with Harness/BoN/PDMC blocks), Territory, Trail, Conformance, Learnings. Status values: `planning | in-progress | complete | abandoned`.

---

## Good vs Bad Specs

| Aspect | Bad | Good |
|--------|-----|------|
| Goal | "Improve the auth system" | "Replace session-based auth with JWT to enable stateless API scaling" |
| Territory | Phases 2-8 with steps, criteria, and PDMC blocks for unvisited ground | "- [ ] Refresh-token rotation (after middleware proves out); Open question: edge-cache TTL source" |
| Frontier step | "Update the database" | "Add `refresh_token` column to users table -> migration runs, column exists in schema" |
| Numbers | `workers=8` frozen at plan time | "workers=8: 8 physical cores, IO-light workload" in the frontier that uses it |
| Decision | "Use JWT" (written before contact) | "Use JWT over sessions: stateless for CDN edge caching" + Alternatives + `Re-examine when: session-affinity requirement appears` |
| Current Step | "Working on auth" | "Frontier 2, Step 2.1 - JWT validation middleware. Token parsing done, need expiry check." |
| Trail entry | Missing, or 80 lines of transcript | "Built: middleware + tests. Surprises: expiry lib off-by-one at DST. Redrawn: killed cookie fallback item. State proof: `npm test`" |
| Boundaries | (missing or flat list) | Three tiers: Always (run tests), Ask first (new deps), Never (touch auth middleware) |
| Criteria | "auth works" | "POST /login returns 200 with valid token; 401 with invalid" (gradeable, authored at frontier entry) |

**Concrete test:** Read Quick Start, `>> Current Step`, and the open Frontier only. Could a model that has never seen this conversation continue the work safely? If not, add detail there.

---

## Quality Self-Check

After creating or advancing a spec:

1. **Quick Start test**: files listed, `-> Next` matches `>> Current Step`, a fresh model starts in under 10 seconds?
2. **Zone integrity**: exactly one Frontier open; Territory is bullets only (steps, criteria, and numbers live in the Frontier alone); Decisions contains only choices actually made, each with rationale, alternatives, and a `Re-examine when` value?
3. **Frontier gradeable**: every step has a testable done-condition; every C1/C2 entry names a specific observable, not a vague restatement?
4. **Gates in order**: Harness/BoN tags carry rationales; `Harness: yes` has criteria + completed PDMC with `Aggregate verdict: PASS`; `BoN: yes` criteria are diff-observable; the mutex holds?
5. **Numbers have a basis**: every scalar in the Frontier names measured / derived / hypothesis-with-recovery?
6. **Trail current**: every closed frontier has a ~10-line entry with Surprises and State proof?
7. **Size**: active spec at or under ~300 lines, overflow archived?
8. **Literals intact**: `## >> Current Step`, `Harness:`, `BoN:`, `#### Harness Criteria`, `#### BoN Criteria`, `#### PDMC Methodological Review`, `Aggregate verdict:`, `## Read On Resume`, `Status:`, and `Session:` exactly as templated?
