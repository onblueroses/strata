---
name: spec
description: "Create and manage implementation spec files that survive context compaction — the spec is the plan AND the execution state, one artifact, persisted on disk at $SPECS_DIR/. Records: phases (~30 min scope each, max 6 steps), per-step acceptance criteria, Decisions table (why every non-obvious call was made — load-bearing after compaction), >> Current Step pointer, Completed log. Survives compaction by being on disk: after compaction, read the spec, trust the Decisions, continue from >> Current Step without re-debating. MANDATORY when using EnterPlanMode or exiting plan mode (no exceptions — every plan-mode session produces a spec). Triggers on: 'write a spec', 'create a spec', 'spec this out', 'multi-file work', 'multi-phase implementation', 'plan this', 'turn this into a spec', 'persist the plan', 'spec status', 'list active specs', 'close the spec', 'update the spec', 'where did we leave off', 'continue the spec', 'execute the plan'. Also triggers when: a multi-file implementation (3+ files) is about to start even without plan mode; a non-trivial design needs to survive into future sessions; the user is about to commit to an approach that touches multiple seams. Skip only for single-file or 2-file changes. Pairs with /recon (upstream — verified knowledge brief feeds spec), /codex-review --plan (MANDATORY downstream after spec writes 3+ files or 3+ phases), /harness (downstream — phase tagged Harness:yes triggers harness), /best-of-n (downstream — phase tagged BoN:yes triggers BoN), /verify (Stop hook checks spec is current). Manual: /spec [feature-name] (create), /spec update (checkpoint), /spec status (list), /spec close (finalize)."
---

# Spec

Goal: Create and manage implementation spec files that persist the plan, execution state, and recovery path for non-trivial work.

Success means:
  - Specs live at `$SPECS_DIR/{name}.md` and serve as the single source of truth after compaction.
  - Each active spec captures Goal, Standing Rules, Boundaries, Decisions, Plan, Validation, `>> Current Step`, Completed work, Conformance, and Learnings.
  - The workflow runs `/codex-review` after plans touching 3+ files or 3+ phases, runs `/harness` for `Harness: yes` phases, and records phase summaries before moving forward.

Stop when: The spec is created, updated, reported, or closed according to the requested `/spec` action, with `Last updated` refreshed and the current execution pointer accurate.

Create spec files that survive context compaction. Treat specs as the single source of truth for non-trivial implementations: they persist on disk while conversation context gets summarized away. Use the spec as the plan and execution state in one artifact.

## Conceptual Lineage

Map `/spec` artifacts onto the outcome+rubric+grader+iteration pattern described at https://platform.claude.com/docs/en/managed-agents/define-outcomes. **Grader is the evaluation role: in /harness the grader is a cross-model reviewer dispatched via the `strong`/`grader` lane (bind it to a different model family than the generator so the asymmetry holds); in /best-of-n the grader is the orchestrator itself, judging candidate diffs against the `#### BoN Criteria` rubric.** Treat the `#### Harness Criteria` and `#### BoN Criteria` blocks each spec phase carries as *rubrics* in the managed-agents sense: explicit, gradeable conditions the grader evaluates against. Keep the field-name strings (`Harness:`, `BoN:`, `#### Harness Criteria`, `#### BoN Criteria`, `#### PDMC Methodological Review`) unchanged; /harness and /best-of-n grep these load-bearing literals.

## Quick Nav

Use this table to jump to the section that matches the requested `/spec` action.

| Task | Jump to |
|------|---------|
| Create a new spec | Creating a Spec |
| Resume/continue work | Guard Clause (checks existing) |
| Checkpoint progress mid-work | Updating a Spec |
| See what's active | Checking Status |
| Finish and verify a spec | Closing a Spec |
| Understand the template | Spec Format |
| Check output quality | Quality Self-Check |

## When to Invoke

Invoke `/spec` at the boundaries where durable execution state matters.

- Use `/spec` when entering or exiting plan mode.
- Use `/spec` for non-trivial implementation work touching 3+ files, even without explicit plan mode.
- Use `/spec update` to checkpoint progress, `/spec status` to list active specs, and `/spec close` to finalize.
- Skip only for single-file or 2-file changes, or for research/exploration tasks with no implementation output.
- Treat a `Harness: yes` phase with no PDMC review pass as incomplete. Block PROCEED until PDMC runs.

## Usage

Call the command in one of these forms.

```
/spec [feature-name]              # Create new spec
/spec [feature-name] --no-codex   # Skip mandatory Codex plan review (use sparingly)
/spec update                      # Update >> Current Step in active spec
/spec status                      # Show active specs and progress
/spec close                       # Mark active spec as complete
```

Pass arguments via `$ARGUMENTS`.

## Skip Conditions

Apply these skip conditions before starting the spec workflow.

- **Skip if** the task touches fewer than 3 files - just do the work directly
- **Skip if** a spec already exists for this feature at `$SPECS_DIR/` - read it and continue from `>> Current Step`
- **Skip if** this is a research/exploration task with no implementation output

## Spec Weight

Choose the spec weight that matches the work.

- **Full** (multi-phase, cross-file, survives multiple compactions): All sections. Use Consumes/Produces, phase gates, Validation table.
- **Light** (single-phase, clear scope, 3-5 files): Drop Consumes/Produces from the phase. Validation can be a single gate command. Context section optional. Still needs Goal, Standing Rules, Boundaries, Decisions, Plan, Current Step.

Default to Light. Upgrade to Full when the work has 2+ phases or will definitely span compaction cycles.

## Guard Clause

Check `$SPECS_DIR/` for existing specs before creating a new one.

- If a spec with Status: `in-progress` exists for a DIFFERENT feature, warn: "Active spec exists for [other feature]. Work on that first, or close it with `/spec close`?"
- If a spec exists for THIS feature, read it and resume from `>> Current Step` instead of creating a new one.

### Concurrency Guard

Protect concurrent Claude Code sessions by honoring spec ownership before edits.

<details>
<summary>Concurrency Guard</summary>

You may run 4-10 Claude Code instances simultaneously. Give every active spec one clear owner.

- Every spec has a `Session:` field with the 8-char session ID of the instance working on it.
- **Before modifying a spec:** check its `Session:` field. If it contains a DIFFERENT session ID AND `Last updated` is within the last 2 hours, leave it unchanged because another instance is actively working on it. Run `date` in bash to get current time for comparison. Warn: "Spec [name] is owned by session [id], last updated [time]. Another instance is working on this."
- **When picking up a spec** (e.g., after compaction or starting a new session): update the `Session:` field to YOUR session ID.
- **Your session ID** is the 8-character suffix of your daily note filename (visible in the SessionStart hook output, e.g., `2026-02-15-feature-work-a1b2c3d4.json` -> session ID is `a1b2c3d4`).

</details>

---

## Instructions

Follow these workflows for creating, updating, reporting, and closing specs.

### Creating a Spec (`/spec [feature-name]`)

Create each spec through recon, plan review, methodological review when needed, and a final write to the canonical path.

1. **Determine the feature slug.** Lowercase, hyphenated. Examples: `auth-refactor`, `city-page-generator`, `quiz-redesign`.

2. **Run recon before planning.** Planning quality is bounded by information quality. Invoke `/recon {feature-slug}` and pass the merged brief path into Step 3.
   - **If you just exited plan mode:** use the exploration already in context; skip the `/recon` invocation.
   - **If `/spec` was invoked directly and scope is Full-weight (3+ files, multi-phase):** invoke `/recon {feature-slug}` and wait for the validated brief at the exact session-scoped path recon reports (`/tmp/recon-{slug}-{sid}.md`). Pass that path to the strong-lane planner in Step 3.
   - **Skip recon entirely** for Light-weight specs (single-phase, 3-5 files, obvious scope) — direct Glob/Grep/Read is faster. The recon protocol earns its latency on Full-weight specs.

   `/recon` runs the canonical three-wave reconnaissance — Wave 1 fans fast sparks across architecture/constraints/prior-art/gotchas/tests; Wave 2 verifies load-bearing claims and tests seams via fast (or strong for auth/concurrency/data-integrity seams); Wave 3 syntheses two strong instances under "name what's missing" and "name what's wrong" framings; merges deterministically; runs a citation-spot-check validation gate before returning the path. Full protocol details, escalation rules, output schema, and failure modes live in `$STRATA_HOME/skills/recon/SKILL.md`. Treat that file as the single source of truth — update it there, not here.

2a. **Sharpen thin input by asking clarifying questions.** When user-provided context is thin OR the goal has multiple unresolved decision branches, ask 2-4 focused questions before delegating to the strong-lane planner. Anchor each question to nearby docs (CLAUDE.md, $KB_DIR/, project ADRs/CONTEXT.md). Pass the sharpened brief into Step 3.
   - **Skip clarification** when the user already provided a concrete brief covering scope, constraints, and the design choice.
   - **Ask** for Light specs that skip recon when the design intent itself needs clarifying (recon covers code facts; clarification covers user intent).
   - **Skip clarification** when the work is mechanical (renames, dependency bumps, simple CRUD).

2b. **Check decision library.** Grep `$KB_DIR/resources/decision-library.md` for the feature domain. If past decisions are relevant, pass them to the strong-lane planner in step 3.

2c. **Surface ambiguities (optional).** If the goal is ambiguous or the codebase has multiple valid paths, surface 2-4 clarifying questions via AskUserQuestion BEFORE delegating to the strong-lane planner. Proceed directly when the path is clear.

3. **Delegate plan writing to the strong lane.** Dispatch a `bin/strong` call (wrapper reference: `reference/model-delegation.md`). The orchestrator reviews; the planner role never runs on a Claude subagent. Pass it:
   - The full task description and goal
   - Everything from exploration: file list, architecture, constraints, applicable CLAUDE.md rules
   - This instruction: "Write the Plan, Boundaries, Decisions, Standing Rules (3-5 relevant CLAUDE.md constraints), and phased steps (with acceptance criteria) for this spec. Return only the content and leave file writing to the caller. Scope phases to ~30 min with max 6 steps each. Assess every phase for `/harness` and set one per-phase `Harness:` field. Use `Harness: yes` for phases with high correctness stakes (security, data integrity, complex multi-file logic, public API contracts, or probe/harness methodology). Use `Harness: no` for scaffolding, config, docs, and simple CRUD. Include a one-line rationale per phase. Write a `#### Harness Criteria` subsection for every phase with `Harness: yes`; derive binary PASS/FAIL gates from that phase's step acceptance criteria. Use the `C1/C2/...` criterion identifier format: `C1: [specific observable requirement] -> PASS if [condition], FAIL if [condition]`. Make criteria concrete, testable, and tied to specific files or behaviors. Write a `#### PDMC Methodological Review` subsection for every `Harness: yes` phase. List PDMC items 1-15 from `references/pdmc-checklist.md` with `PASS`, `FAIL`, or `N/A` results and an aggregate verdict. Fill PDMC results after the separate PDMC pass in Step 3.6. Use Harness Criteria as the harness loop input at execution time; use PDMC as the methodology gate before the spec can PROCEED. Require aggregate PASS before PROCEED. Assess every phase for `/best-of-n` and set one per-phase `BoN:` field. Use `BoN: yes - <rationale> [N=K]` (default N=3, max N=5) for phases where multiple credible designs/strategies exist (UI direction unclear, public-facing API name choice, prompt engineering with measurable success). Use `BoN: no - <rationale>` for phases with a single defensible structure (file moves, dependency bumps, mechanical refactors). Write a `#### BoN Criteria` subsection for every `BoN: yes` phase with binary PASS/FAIL gates in the same format as Harness Criteria. Make BoN criteria observable from the candidate's git diff alone; treat the git diff plus the criteria as the complete verifier context. Enforce **MUTEX HARD-FAIL**: treat any phase tagged with both `Harness: yes` and `BoN: yes` as malformed. Assign at most one `yes` across `Harness:` and `BoN:` for each phase. Treat them as sibling gates. Keep v1 composition-free; reserve ordering for v2. Treat each `#### Harness Criteria` and `#### BoN Criteria` block as a rubric in the managed-agents sense (https://platform.claude.com/docs/en/managed-agents/define-outcomes): criteria must be explicit and gradeable. Distinguish rubrics from validation by writing gradeable observations such as 'CSV contains a price column with numeric values' over vague judgments such as 'data looks good'. Simulate a known-good implementation when criteria feel hard to author, then derive criteria from the observable properties that make it good. For each binary acceptance criterion, mark whether it is satisfiable by pure implementation or needs an architectural primitive (a satisfiability + design-contract pre-check); for empirical or experimental phases, add a statistical-validity pre-check (free-parameter headline, denominator adequacy) to run before any compute spend, per the Pre-Check Gate in reference/load-bearing-iteration.md."

   Wait for the strong-lane output. Read the plan critically yourself before Step 3.5: check phase scoping, Decisions coverage, criteria quality, and fidelity to the user's intent against your own context of the task; fix small gaps inline, and re-dispatch with sharper direction when the plan misses intent. Codex review supplements your judgment; it does not replace it. Then review through Steps 3.5 and 3.6 before writing the spec.

3.5. **Codex plan review (MUST run for plans with 3+ files OR 3+ phases).** Operationalizes CLAUDE.md "Codex plan review" rule. Skip ONLY when:
   - Plan touches fewer than 3 files AND has fewer than 3 phases, OR
   - User invoked /spec with `--no-codex` (note "Codex plan review skipped per user request" as Decision #0)

   Otherwise:
   1. Write the planner-generated plan content verbatim to `/tmp/spec-draft-{feature-slug}.md`
   2. Invoke `/codex-review --plan /tmp/spec-draft-{feature-slug}.md` and wait for the verdict
   3. Apply findings:
      - **BLOCKING**: revise the plan to address before writing the spec. If fundamental, re-run the strong-lane planner with the BLOCKING evidence appended to the original instruction.
      - **IMPORTANT**: address inline OR record in the Decisions table with explicit "rejected because" rationale (Codex flagged X; we keep current approach because Y).
      - **ADVISORY**: apply when trivially fixable; otherwise record as noted.
      - **AGREE notes**: treat as signal that the review was substantive, not action items.
   4. If verdict is BLOCK and a second pass also returns BLOCK: surface to user via AskUserQuestion (load /ask-better first). Options: revise scope, accept Codex's stance, or proceed against Codex's recommendation with a documented rationale.
   5. Record in Decisions table: `Codex plan review: [framing] - [N] BLOCKING, [N] IMPORTANT addressed; [N] ADVISORY noted.`

3.6. **PDMC methodological review (required for `Harness: yes` phases).** After `/codex-review --plan` returns, inspect the draft for any phase tagged `Harness: yes`. If none exist, skip this step and record `PDMC methodological review: N/A - no Harness: yes phases.`

   If any `Harness: yes` phase exists, invoke a separate codex pass with the draft plan and `references/pdmc-checklist.md` using this framing:

   > Act as a methodological reviewer focused on PDMC methodology. Leave procedural plan review to `/codex-review --plan`. Apply PDMC items 1-15 from the PDMC checklist to this plan. Classify each item as PASS, FAIL, or N/A with evidence. Return a PASS/FAIL verdict per item plus an aggregate verdict.

   Apply the result as a hard gate:
   1. If any applicable PDMC item fails, the plan is BLOCKED until revision. Rework the plan, then rerun the separate PDMC pass. Run methodological review as a SEPARATE gate from procedural `/codex-review --plan`.
   2. If the aggregate verdict is PASS, paste the per-item PDMC verdicts into each `Harness: yes` phase's `#### PDMC Methodological Review` subsection before writing the spec.
   3. Record in Decisions table: `PDMC methodological review: [aggregate verdict] - [N] FAIL addressed; [N] N/A; separate from Codex plan review.`

4. **Write the spec** at `$SPECS_DIR/[feature-slug].md` using the format below. Set Status to `in-progress` and populate `>> Current Step` with the first step.

4b. **Surface harness and BoN recommendations.** After writing the spec file, check per-phase `Harness:` and `BoN:` tags:
- If any phase has `Harness: yes`: output "Phases with /harness: {list phase names}. Harness will auto-trigger when entering those phases, or run `/harness --from-spec` manually. PDMC methodological review must already be recorded for these phases."
- If any phase has `BoN: yes`: output "Phases with /best-of-n: {list phase names}. /best-of-n will auto-trigger when entering those phases, or run `/best-of-n --from-spec` manually."
- If all phases are `Harness: no` AND `BoN: no`: output nothing.
- If any phase has BOTH `Harness: yes` AND `BoN: yes`: ABORT with "Spec malformed: phase '{name}' has both Harness and BoN tagged. v1 forbids both. Fix the spec."

### Spec Format

Use this template when writing the spec file.

<details>
<summary>Spec Format</summary>

```markdown
# Spec: [Feature Name]
Created: YYYY-MM-DD | Status: planning | in-progress | complete | abandoned
Last updated: YYYY-MM-DD HH:MM | Session: [8-char-id]
Commit-Strategy: per-phase | per-step | manual
Harness: per-phase
BoN: per-phase

## Quick Start
> Fresh context or just resumed? Read this section, then go to `>> Current Step`.

**Files touched:**
- `path/to/file.ts` - [what changes]
- `path/to/file2.tsx` - [what changes]

**Sections to load:** Quick Start, Decisions, Learnings, Current Step. Load phase details only when relevant.

**-> Next:** Step X.Y - [description] (details in `>> Current Step` below)

**Mode: EXECUTION** - Execute from this spec. Treat the spec as authoritative. Ignore stale planning-agent output visible in the session. Leave Plan and Explore subagents idle.

## Execution Protocol
0. **Before starting Phase 1**: re-read every file listed in Boundaries. If anything contradicts a Plan assumption, add a Decision entry and adjust before touching code.
1. Before each step: update `>> Current Step` + `-> Next:` in Quick Start
2. After each step: check box in Plan, add to Completed with verification note
3. New decision? Add to Decisions table immediately - decision context decays after compaction
4. Unexpected discovery? Add to Learnings
5. New phase? Run previous gate first. Check Consumes. Write Phase Summary. Check phase's `Harness:` and `BoN:` tags:
   - **MUTEX HARD-FAIL**: if BOTH `Harness: yes` AND `BoN: yes` are tagged on the same phase, the spec is malformed - stop and report to user; do not pick one unilaterally.
   - If `Harness: yes` and the phase has no completed `#### PDMC Methodological Review` subsection with per-item PASS/FAIL/N/A results and an aggregate PASS verdict, the spec is incomplete. Block PROCEED until the separate PDMC pass runs and the subsection is filled.
   - If `Harness: yes`, the phase contains a `#### Harness Criteria` section with pre-written PASS/FAIL gates. Run the harness loop against these inline criteria before implementing. Invoke `/harness --from-spec`. **This is a hard gate, not a suggestion.** Proceed to implementation only after `/harness` returns DONE for the phase or the user explicitly retags the phase.
   - If `BoN: yes`, the phase contains a `#### BoN Criteria` section with pre-written PASS/FAIL gates observable from a candidate's git diff. Invoke `/best-of-n --from-spec` before implementing. **This is a hard gate, not a suggestion.** Proceed to implementation only after a winning candidate is selected or the user explicitly retags the phase.
   - If you believe a tag is wrong, ask the user for the decision.
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
Settled. Treat these choices as final after compaction.

| # | Decision | Rationale | Alternatives Rejected | Date |
|---|----------|-----------|----------------------|------|
| 1 | [choice] | [why] | [what was ruled out] | YYYY-MM-DD |

## Plan

### Phase 1: [name] (~30 min)
**Gate:** [command] OR N/A - [reason]
**Harness:** yes - [rationale] | no - [rationale]
**BoN:** yes - [rationale] [N=K] | no - [rationale]    _(MUTUALLY EXCLUSIVE with Harness in v1: never both `yes`)_
**Consumes:** [typed artifacts, e.g., `src/auth/jwt.ts` (exists, exports `verifyToken`)] _(Full weight only)_
**Produces:** [typed artifacts, e.g., `src/middleware/auth.ts` (new, exports `authMiddleware`)] _(Full weight only)_
**Deepening:** _(optional; required for structural-rework phases; skip for additive phases)_
Before: [current shape and what it leaks]
After: [new shape and how it stops the leak]
- [ ] **Step 1.1**: [action] -> [acceptance criteria]
  Read: `path/to/file` ([what to find]) | Edit: `path/to/file`
- [ ] **Step 1.2**: [action] -> [criteria] _(Depends on: 1.1)_

#### Harness Criteria _(only if Harness: yes)_
```
C1: [specific observable requirement] -> PASS if [condition], FAIL if [condition]
C2: [specific observable requirement] -> PASS if [condition], FAIL if [condition]
```

#### PDMC Methodological Review _(mandatory if Harness: yes; must be completed before PROCEED)_
```
1. Comparator-vs-baseline distinction: PASS | FAIL | N/A - [evidence or fix]
2. Comparator label-blindness: PASS | FAIL | N/A - [evidence or fix]
3. Selection rule pre-registration: PASS | FAIL | N/A - [evidence or fix]
4. Selection effect bound: PASS | FAIL | N/A - [evidence or fix]
5. Bootstrap clustering: PASS | FAIL | N/A - [evidence or fix]
6. Per-fold AND aggregate gate definitions: PASS | FAIL | N/A - [evidence or fix]
7. Sentinel discipline: PASS | FAIL | N/A - [evidence or fix]
8. Decision-grade vs validation-grade explicit: PASS | FAIL | N/A - [evidence or fix]
9. Cross-probe input schema: PASS | FAIL | N/A - [evidence or fix]
10. Held-out family/lexicon contract: PASS | FAIL | N/A - [evidence or fix]
11. Calibration-vs-eval overlap audit: PASS | FAIL | N/A - [evidence or fix]
12. Trial JSON schema completeness: PASS | FAIL | N/A - [evidence or fix]
13. Pivot rule unambiguity: PASS | FAIL | N/A - [evidence or fix]
14. Power calculation per fold: PASS | FAIL | N/A - [evidence or fix]
15. Empirical adversarial check: PASS | FAIL | N/A - [evidence or fix]
Aggregate verdict: PASS | BLOCKED
```

#### BoN Criteria _(only if BoN: yes; criteria must be observable from candidate's git diff alone)_
```
C1: [observable from diff] -> PASS if [condition in diff], FAIL if [condition in diff]
C2: [observable from diff] -> PASS if [condition in diff], FAIL if [condition in diff]
```

### Phase 2: [name] (~30 min)
**Gate:** [command] OR N/A - [reason]
**Harness:** yes - [rationale] | no - [rationale]
**BoN:** yes - [rationale] [N=K] | no - [rationale]    _(MUTUALLY EXCLUSIVE with Harness in v1)_
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

Checkpoint the active spec by refreshing `>> Current Step` and completion state.

1. Read the active spec from `$SPECS_DIR/`
2. Update `>> Current Step` with current status
3. Check off completed steps in Plan
4. Update `Last updated` timestamp

### Checking Status (`/spec status`)

List all specs in `$SPECS_DIR/`.

```
Active Specs
============
[feature-slug] | in-progress | Phase 2/3 | Step 2.1 | Updated: [time]

Completed Specs
===============
[feature-slug] | complete | [date]
```

### Closing a Spec (`/spec close`)

Close specs through conformance, learning propagation, and valid status transitions.

<details>
<summary>Closing a Spec</summary>

1. **Run conformance check.** Re-read Goal, step criteria, and Boundaries. Fill in `## Conformance`. Note PARTIAL/UNMET with reason (intentional scope change vs missed work).
2. **Propagate learnings.** Generalizable discoveries go to the entity's `summary.md` or `items.json`.
3. Mark all steps complete (or note which were skipped and why)
4. Set Status to `complete` (or `abandoned` with reason in Learnings)
5. Update `Last updated`
6. Leave the file in `$SPECS_DIR/` for reference

**VALID TRANSITIONS** (prevents premature closure after compaction):
```
planning -> in-progress   (requires: Phase 1 populated, Quick Start filled)
in-progress -> complete   (requires: conformance done, all steps checked or skipped-with-reason)
in-progress -> abandoned  (requires: reason in Learnings)
planning -> abandoned     (ok, no requirements)
```

</details>

### Harness Integration

Run harness integration from the per-phase `Harness: yes | no` tags.

Each phase has its own `Harness: yes | no` tag, set by the strong-lane planner at spec creation. Phases with `Harness: yes` include a `#### Harness Criteria` subsection with pre-written binary PASS/FAIL gates. The strong-lane planner generates these criteria at spec creation time.

Require a completed `#### PDMC Methodological Review` subsection before a `Harness: yes` phase can PROCEED. Run PDMC as a separate methodological review pass using `references/pdmc-checklist.md`; `/codex-review --plan` covers procedural review only.

When entering a phase with `Harness: yes`, invoke `/harness --from-spec`. The harness reads the inline criteria directly from the spec. This keeps the criteria visible in the spec text and preserved through compaction, making the harness invocation a natural part of reading the spec.

Phases with `Harness: no` proceed with normal execution. The top-level spec header says `Harness: per-phase` to signal this behavior.

---

## Good vs Bad Specs

Compare specs against these examples to sharpen Goal, Decisions, Boundaries, and criteria.

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
| Criteria | "auth works" | "POST /login returns 200 with valid token; returns 401 with invalid; refresh token has expiry set" (gradeable, per-line testable) |

**Concrete test:** Read only `>> Current Step`. Could a model that has never seen this conversation continue the work? If not, add more detail.

</details>

---

## Spec Rules

Apply these rules to keep specs useful after compaction.

<details>
<summary>Spec Rules</summary>

- Create specs for non-trivial tasks (3+ files, 3+ steps) where persistence beats overhead.
- Treat Decisions as settled after compaction. If one seems wrong, add a Learning but follow it unless clearly broken.
- Write observable acceptance criteria ("renders at 375px without scroll", "API returns 200 with valid token") instead of vague criteria ("looks good", "works correctly").
- Put WHAT and WHY in the spec; put HOW in code comments.
- Scope phases to ~30 min. Break up longer phases.
- Populate all three Boundaries tiers with scope decisions.
- Keep `>> Current Step` fresh so the pointer guides recovery after compaction.
- Respect spec ownership. Check `Session:` and `Last updated`; within 2 hours = hands off.
- Write concrete Consumes/Produces entries with files and expected exports/state.
- Run conformance on close and verify the criteria.

</details>

---

## Quality Self-Check

Check the completed or updated spec against this list before handing it back.

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
14. **Harness criteria inline** - every `Harness: yes` phase has a `#### Harness Criteria` subsection with concrete C1/C2/... PASS/FAIL gates?
15. **PDMC review inline** - every `Harness: yes` phase has a `#### PDMC Methodological Review` subsection with PDMC items 1-15, per-item PASS/FAIL/N/A verdicts, and aggregate PASS before PROCEED?
16. **BoN tags** - every phase has a `BoN: yes | no` with rationale?
17. **BoN criteria inline** - every `BoN: yes` phase has a `#### BoN Criteria` subsection with concrete C1/C2/... PASS/FAIL gates observable from a candidate's git diff?
18. **Harness/BoN mutex respected** - no phase has both `Harness: yes` AND `BoN: yes` (mutually exclusive in v1)?
19. **Criteria are gradeable** - every `C1/C2/...` entry in any `#### Harness Criteria` or `#### BoN Criteria` block names a specific observable, not a vague restatement of the goal? Criteria are *rubrics* in the managed-agents sense (see Conceptual Lineage callout).
20. **Deepening present for structural rework** - every phase that reshapes existing structure (interface change, module boundary move, refactor) carries a `**Deepening:**` block with Before/After lines? Additive phases (pure new feature, scaffolding) may skip Deepening.

</details>
