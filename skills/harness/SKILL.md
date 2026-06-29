---
name: harness
description: "Adversarial generator-evaluator loop for high-stakes implementation tasks. A generator lane generates and a different-model-family evaluator lane evaluates — cross-model asymmetry breaks same-model systematic bias by construction. The evaluator never sees the task description or generator reasoning, only criteria and output files. Rotates adversarial framings (security-audit, specification-lawyer, production-load, maintainability, adversarial-user, dependency-skeptic, reality-declaration) across iterations to surface different blindspots. Termination is convergence-based: the loop runs until Stage A passes and Stage B has no CRITICAL findings, or a convergence signal (SPINNING, OSCILLATING, STRUCTURAL, DIMINISHING_RETURNS) fires twice and escalates to the user. No hard iteration cap — convergence detectors are the budget. Targeted rework with evaluator feedback on failure, fresh generation as fallback after structural-failure detection. Supports competitive mode (--competitive N) that spawns N generators with different strategies per iteration and picks the best candidate before evaluation. Costs scale with convergence rate; typical runs finish in 1-3 iterations. MANDATORY when an active spec's current phase has `Harness: yes` and implementation of that phase is about to begin — no confirmation, no asking, just run /harness --from-spec. Triggers on: 'run the harness', 'gen-eval loop', 'adversarial loop', 'iterative review', 'harness this', 'competitive mode', 'run N candidates', 'evaluator feedback', 'cross-model implementation review'. Also triggers when: /verify Deep tier finds criteria failures on a second pass; high-stakes implementation requires more than one-shot review; a /codex-review surfaced BLOCKING findings that need iterative correction; the user explicitly invokes the harness for ad-hoc work. Pairs with /codex-review (upstream one-shot review; harness adds the loop), /spec (reads phase tags for Harness: yes), /verify (downstream gate after harness completes), /best-of-n (mutex — a phase tagged both BoN:yes and Harness:yes is malformed). Manual invocation supported for ad-hoc use outside spec phases."
---

# Harness

Goal: Run an adversarial generator-evaluator loop that turns high-stakes implementation tasks into criteria-checked, convergence-driven code changes.

Success means:
  - The generator lane produces implementation candidates and a different-family evaluator lane evaluates them through isolated Stage A and Stage B passes.
  - The evaluator reads the criteria, the output files, and prior-round snapshot directories used for convergence detection; the evaluator never sees the task description or generator reasoning.
  - Rotating adversarial framings cover `security-audit`, `specification-lawyer`, `production-load`, `maintainability`, `adversarial-user`, `dependency-skeptic`, and `reality-declaration`.
  - The loop terminates only through DONE, convergence-detector escalation, user choice, or unrecoverable error.

Stop when: Stage A passes and Stage B meets the selected `done_bar`, or a convergence detector fires twice and the loop escalates to the user.

Run an adversarial generator-evaluator loop. Use a generator lane for generation and a different-model-family evaluator lane for evaluation (strata dispatches the evaluator through `bin/strong`/`bin/grader`; see `commands/harness.md`), cross-model asymmetry for bias-breaking, rotating adversarial framings for coverage, and convergence detectors for termination.

## Conceptual Lineage

Map `/harness` onto the managed-agents outcome+rubric+grader+iteration pattern; see https://platform.claude.com/docs/en/managed-agents/define-outcomes. **Grader is the evaluation role: in /harness the grader is a cross-model reviewer dispatched via the `strong`/`grader` lane (bound to a different model family than the generator so the asymmetry holds); in /best-of-n the grader is the orchestrator itself, judging candidate diffs against the BoN rubric.** Use the vocabulary table below to translate /harness's internal terms into the managed-agents canon — they describe the same machine, in different words.

| Harness vocab | Managed-agents vocab |
|---|---|
| acceptance criteria | rubric |
| criterion | gradeable criterion |
| evaluator | grader |
| iteration | iteration |
| convergence detectors (SPINNING/OSCILLATING/STRUCTURAL/DIMINISHING_RETURNS) | max_iterations |
| Stage A ALL_PASS + Stage B no-CRITICAL | result: satisfied |
| Stage A HAS_FAILURES | result: needs_revision |
| convergence detector 2nd strike | result: max_iterations_reached |
| user abort during escalation | result: failed or interrupted |

```
/harness [task description]           # Run with task inline
/harness --from-spec                  # Derive criteria from active spec
/harness --framing security-audit     # Force a specific evaluator framing
/harness --competitive 3              # Spawn 3 generators per iteration, pick best
/harness --models strong,fast,grader  # Per-slot lane override (use with --competitive)
/harness --strictness strict          # Evaluator strictness: strict|standard|lenient (default: standard)
/harness --done-bar critical-only     # Definition of done: critical-only (default) | no-warnings | stage-a-only
/harness --cost-warn 500000           # Soft warning when cumulative tokens exceed this (default 500000)
```

Arguments via `$ARGUMENTS`.

## Skip Conditions

Use these entry gates before setup; run harness when the task has enough risk, implementation output, and binary criteria to justify the loop.

- **Trivial scope**: handle single-file changes under 20 lines directly because harness overhead exceeds value
- **Criteria unavailable**: ask for or derive clear acceptance criteria first because the evaluator needs binary gates
- **Research-only work**: use the research workflow when the task produces no implementation output

## Auto-Trigger Logic

Invoke harness automatically when any of these conditions matches:

- **Spec-driven (MANDATORY)**: Active spec's current phase has `Harness: yes` (per-phase tag). Invoke with `--from-spec` when entering that phase, but only after the phase's `#### PDMC Methodological Review` subsection records PDMC items 1-15 and aggregate `PASS`. When the spec says `Harness: yes`, you MUST run `/harness --from-spec` before implementing that phase. Ask the user for an explicit skip when you believe harness adds no value for the phase.
- **Verify-escalation**: `/verify` fails twice in the same session on the same files. On the second failure, suggest harness as an alternative to continued manual fixing: "Two verify failures on the same files. Consider `/harness` to break the loop."
- **Domain keywords**: Spec or task description contains "auth", "payment", "encryption", "migration", or "public API", and `Harness: no` is absent. Recommend harness before implementation begins.

Treat spec-driven triggers as mandatory. Present verify-escalation and domain-keyword triggers as recommendations so the user can choose direct implementation.

## Guard Clauses

Run these checks before setup so resume state, specs, and prerequisites are explicit.

- **Check for active harness state.** State files are session-specific: `$STATE_DIR/harness-state-{session-id}.json` (where `{session-id}` is the 8-char suffix of today's daily note filename). If your own session's state file exists with `status: "running"`, offer to resume. Multiple sessions can run /harness concurrently; each writes its own state file, and artifact directories are already session-isolated via `run_id`. As a courtesy check for file conflicts only: glob `harness-state-*.json` for *other* sessions with `status: "running"` and `last_updated` within 2 hours; if any of their `target_files` overlap with yours, warn the user that two harness runs will be editing the same files. Continue after the soft warning; reserve user escalation for the mid-run conflict path (see Error Recovery).
- **Check for active spec.** If `--from-spec` is passed, verify a spec exists at `$SPECS_DIR/` with Status: `in-progress`. When no active spec exists, abort with: "No active spec found. Create one with `/spec [name]` first, or pass the task inline."
- **PDMC prerequisite for spec-driven harness.** If `--from-spec` is passed and the active/current phase has `Harness: yes`, verify that the same phase contains a completed `#### PDMC Methodological Review` subsection with PDMC items 1-15 marked `PASS`, `FAIL`, or `N/A` and `Aggregate verdict: PASS`. When this prerequisite check fails, abort exactly with: "PDMC review required before harness. Run /spec PDMC review first."

## Instructions

Execute the phases in order and keep every state transition visible in the state file and artifact directory.

### Phase 0: Setup

<details>
<summary>Phase 0: Setup</summary>

Prepare the harness run by parsing inputs, deriving criteria, selecting the first framing, creating artifacts, and initializing state.

1. **Parse arguments.** Extract task description (inline or from spec), forced framing (optional), competitive mode (`--competitive N`, default: off/linear), strictness (`--strictness strict|standard|lenient`, default: `standard`), definition of done (`--done-bar critical-only|no-warnings|stage-a-only`, default: `critical-only`), and cost soft warning threshold (`--cost-warn N`, default: `500000` cumulative tokens). If `--competitive N` is set with N > 1, set `mode: "competitive"` and `candidates_per_round: N`. Valid range for N: 2-5. Load the strictness text block from `references/strictness-blocks.md`; `standard` maps to empty string.

   **Definition of done (`done_bar`)** — what counts as a successful terminal state:
   - `critical-only` (default): Stage A `ALL_PASS` + Stage B has zero `CRITICAL` findings. WARNINGs surface while completion proceeds.
   - `no-warnings`: Stage A `ALL_PASS` + Stage B has zero findings of any severity. Stricter; uses more iterations.
   - `stage-a-only`: Stage A `ALL_PASS`. Stage B is skipped entirely. Use this for tasks where spec compliance is the only relevant gate (e.g. pure refactor with full test coverage). This stops Stage B nit-drift before it starts.

   Expose no `max_iterations` argument. Drive termination through convergence detectors in Phase 1 Step 3, not a fixed iteration count.

   **Per-slot model overrides (`--models`):** If `--competitive N` is also set, parse `--models <tierA>,<tierB>,<tierC>` (host model tiers) into `slot_models: ["<tierA>", "<tierB>", "<tierC>"]`. Resolve each slot's model as `slot_models[K % len(slot_models)]`. Build `slot_configs`: an array of N objects `{index: K, model: <resolved model>, strategy: <strategy hint K>}` where strategy hints are assigned using the same round-robin order already defined for strategy hints. If `--models` is absent, all slots use `"inherit"` and `slot_configs` is `[]` (empty). `--models` without `--competitive` is ignored with a warning.

2. **Derive acceptance criteria.** Use binary PASS/FAIL gates exclusively; leave scores and "mostly works" outside the rubric. The criteria below form a **rubric in the managed-agents sense** — explicit, gradeable conditions the grader evaluates against (see Conceptual Lineage callout above). When a rubric is unavailable, give Claude an example of a known-good artifact and ask it to derive what makes that content good; turn that analysis into a rubric. This middle-ground approach often produces tighter criteria than first-principles authoring.

   **From spec (`--from-spec`):**
   - Read the active spec at `$SPECS_DIR/`
   - Identify the current phase from `>> Current Step` and the phase heading. If that phase has `Harness: yes`, perform the PDMC prerequisite check before deriving criteria. Missing or non-PASS PDMC blocks setup with: "PDMC review required before harness. Run /spec PDMC review first."
   - Look for the `#### Harness Criteria` subsection in the current phase. If it exists, use those pre-written criteria directly - they are already in `C1: ... -> PASS if ..., FAIL if ...` format and were authored by the Plan subagent at spec creation time with full architectural context.
   - **Fallback only:** If the current phase has `Harness: yes` but no `#### Harness Criteria` subsection (older spec format), derive criteria from the phase's step acceptance criteria (the `-> [acceptance criteria]` part after each step). Each criterion becomes one evaluation gate.
   - In both cases, add the spec's Validation section checks as additional gates

   **From inline task:**
   - Break the task description into discrete, testable requirements
   - Each requirement becomes one PASS/FAIL criterion
   - When the task is vague, derive 3-5 criteria that a correct implementation satisfies
   - Present criteria to the user for confirmation before proceeding

   **Criteria format:**
   ```
   C1: [specific observable requirement] -> PASS if [condition], FAIL if [condition]
   C2: [specific observable requirement] -> PASS if [condition], FAIL if [condition]
   ```

3. **Identify target files.** List all files the generator will need to read or modify. Include:
   - Files to create or edit (the implementation targets)
   - Files to read for context (interfaces, types, existing patterns)
   - Test files to run for validation

4. **Select initial evaluator framing.** Read `references/evaluator-framings.md`. If `--framing` was passed, use that. Otherwise, check framing effectiveness memory first:

   **Framing memory (`$STATE_DIR/harness-memory.json` - bootstrapped empty):**
   - Read the memory file. It tracks which framings caught real issues across past runs.
   - If the current task type has prior data, prefer framings with higher `findings_rate` for that task type.
   - When fewer than 3 matching runs exist for this task type, fall back to heuristics below.
   - Preserve the legacy auto-tuning compatibility rule when reading older memory entries: 3 budget-exhausted runs -> +1 max_iterations, cap 6. Current live termination remains convergence-based.

   **Framing set:** `security-audit`, `specification-lawyer`, `production-load`, `maintainability`, `adversarial-user`, `dependency-skeptic`, `reality-declaration`.

   **Heuristic fallback:**
   - API/backend work -> `security-audit` or `adversarial-user`
   - Library/framework code -> `specification-lawyer` or `dependency-skeptic`
   - UI/frontend -> `adversarial-user` or `maintainability`
   - Performance-critical -> `production-load`
   - Default when unsure -> `specification-lawyer` (catches the most general class of bugs)

   **Rotation order:** Start with the memory-selected or heuristic-selected framing. For later iterations, follow `specification-lawyer`, `security-audit`, `reality-declaration`, `adversarial-user`, `production-load`, `dependency-skeptic`, `maintainability`; skip the most recently used framing and cycle back after every framing has been used. Count a framing as successful when it produces a FAIL verdict or CRITICAL finding with evidence that either changes the next generator attempt or remains a valid user-facing concern at wrap-up.

4b. **Load skill-cache context.** Read `.claude/skill-cache.json`. If any patterns are relevant to the current task type (match by domain keywords), include them in the generator's PROJECT CONSTRAINTS section as additional context.

4c. **Create artifact directory.** Generate run-id as `{YYYY-MM-DD}-{session-id}` (e.g., `2026-03-31-8cd8dd4b`). Create `$STATE_DIR/harness-runs/{run-id}/`. Treat each round directory as `{artifact_dir}/round-{N}/`; recognize `.claude/harness-runs/{run-id}/round-{N}/` as the legacy shorthand when reading older harness notes. Write `run-meta.json` with run-id, session-id, task-summary, criteria count, definition_of_done, cost_warn_threshold, and created timestamp. See `references/artifact-structure.md` for the full layout.

4d. **Clean up old runs.** List directories in `$STATE_DIR/harness-runs/`. Sort by date prefix. Keep the 3 most recent. Move older ones to `~/to-delete/` with manifest entries (format: `dirname | $STATE_DIR/harness-runs/ | date | harness run cleanup`).

5. **Initialize state.** Write `$STATE_DIR/harness-state-{session-id}.json` per the schema in `references/state-schema.md`. The state file is session-specific so concurrent harness runs in different sessions never clobber each other. Set `status: "running"`, `iteration: 0`, `rework_fail_counts: {}`, record criteria, selected framing, `run_id`, `artifact_dir`, `mode` (`"linear"` or `"competitive"`), `candidates_per_round` (1 for linear, N for competitive), `slot_configs` (array of `{index, model, strategy}` per slot from Step 1 parsing, or `[]` if `--models` was not passed), `definition_of_done` (the parsed `done_bar`), `cost_warn_threshold` (token count from `--cost-warn`), and `convergence_state: {failing_set_history: [], fix_count_history: [], spinning_strikes: 0, oscillating_strikes: 0, structural_strikes: 0, diminishing_strikes: 0, cumulative_tokens: 0}`.

6. **Report plan.** Tell the user:
   - **Linear mode:** "{N} criteria derived. Definition of done: {done_bar}. Starting with {framing} evaluator. Termination is convergence-based (no hard iteration cap); typical runs finish in 1-3 iterations. Soft cost warning at {cost_warn_threshold} tokens. Artifacts at $STATE_DIR/harness-runs/{run-id}/."
   - **Competitive mode:** "{N} criteria derived. Definition of done: {done_bar}. {K} candidates per iteration. Starting with {framing} evaluator. Termination is convergence-based (no hard iteration cap); soft cost warning at {cost_warn_threshold} tokens. Note that competitive mode multiplies generator cost by {K}x per iteration. Artifacts at $STATE_DIR/harness-runs/{run-id}/."

</details>

### Phase 1: Generator-Evaluator Loop

Iterate until a termination condition fires (see Step 3 for the full ladder). Each pass through Steps 1 -> 2 -> 3 is one iteration. The loop has no hard iteration cap; convergence detectors are the budget.

#### Step 1: Generate

<details>
<summary>Step 1: Generate</summary>

Spawn a general-purpose subagent with `model: "inherit"`. The generator gets a fresh context window each iteration - no inherited bias from previous attempts.

**Generator prompt template:**

```
Goal: Implement the requested feature and write the required generator artifact.

Success means:
  - Code satisfies every item under ACCEPTANCE CRITERIA.
  - Files listed under FILES TO CREATE/EDIT are created or edited using PROJECT CONSTRAINTS.
  - generator-approach.md records the approach and implementation notes.

Stop when: The code is written, relevant validation has run where available, and the required artifact exists.

## ARTIFACTS
WRITE (required):      {artifact_dir}/round-{N}/generator-approach.md

TASK:
{original task description or spec goal}

ACCEPTANCE CRITERIA:
{C1, C2, ... CN - the binary gates from Phase 0}

FILES TO READ FIRST:
{context files - interfaces, types, existing patterns}

FILES TO CREATE/EDIT:
{target file paths}

PROJECT CONSTRAINTS:
{relevant CLAUDE.md rules, e.g., code style, no deletions, etc.}

EVALUATION HANDOFF:
Leave review, scoring, and verdicts to the harness evaluator.
```

Use this as the base template for every iteration. For iteration > 1, append one of the two blocks below (rework or fresh). For iteration 1, use the base template as-is because prior artifacts are absent.

**If iteration > 1, determine retry mode and build the appropriate prompt block:**

Check `rework_fail_counts` in `harness-state.json`:
- When all criteria have count < 2: Use **rework mode** (targeted fix).
- When any criterion has count >= 2 (failed in 2 consecutive rework attempts): Switch to **fresh mode** (full rewrite). Treat that criterion as structurally unfixable by patching.

**Rework mode prompt (default for iteration > 1):**

```
Goal: Repair the reviewed implementation by applying targeted fixes for the evaluator findings.

Success means:
  - Each listed FAILED criterion and CRITICAL finding is addressed in code.
  - Behavior that already passed review remains intact.
  - generator-approach.md explains any evaluator evidence you contest and the implementation you chose.

Stop when: The reported failures have targeted code changes and the implementation is ready for the next evaluator pass.

EVALUATOR FEEDBACK FROM ROUND {N-1}:
The previous implementation was reviewed. Limit this pass to the reported issues below.
Preserve reviewed code that already passed and preserve passing behavior.

{for each FAIL criterion from Stage A:}
FAILED: {criterion ID} - {criterion description}
EVIDENCE: {evaluator's specific evidence - file:line, what's wrong vs expected}

{for each CRITICAL finding from Stage B, if it ran:}
CRITICAL: {finding description}
EVIDENCE: {file:line reference from evaluator}

PRIOR IMPLEMENTATION:
The files from the previous round are still on disk. Read them, understand
what the evaluator flagged, and make targeted fixes. The evaluator's evidence
sections are factual observations from reading the actual code.

ARTIFACT REFERENCE (for deeper context if needed):
- {artifact_dir}/round-{N-1}/evaluator-verdict.md - full evaluator output
- {artifact_dir}/round-{N-1}/generator-approach.md - previous approach reasoning

RULES:
- Apply targeted fixes to the specific failures listed above.
- For a criterion that PASSED, leave the code that satisfies it unchanged.
- If you believe the evaluator's evidence is wrong, explain why in your
  generator-approach.md, then implement what you think is correct.
```

**Fresh mode prompt (fallback after 2 rework failures):**

```
Goal: Produce a fresh implementation that resolves persistent failures with a new approach.

Success means:
  - Persistent failures listed below are addressed with a materially different structure or strategy.
  - Prior artifacts are used selectively to understand evidence and previous attempts.
  - generator-approach.md records the new approach and why it differs from prior rounds.

Stop when: A fresh implementation is written and ready for evaluation.

PRIOR ROUNDS (inspect selectively):
Artifact directory: {artifact_dir}
Use the prior artifacts needed to understand failures and previous attempts:
- round-{N-1}/evaluator-verdict.md has evidence of what failed
- round-{N-1}/generator-approach.md describes what the previous attempt tried
- round-{N-1}/snapshots/ has the files as they were after that attempt

REWORK RESULT - SWITCHING TO FRESH GENERATION:
Two targeted rework attempts failed to resolve the same criteria. The previous
approach has a structural issue that requires a new implementation.

PERSISTENT FAILURES:
{for each criterion that failed across both rework attempts: ID, description, and
the evaluator evidence from the most recent attempt}

Write a fresh implementation from scratch. Choose a materially different structure
and strategy. Use the artifact directory to understand what was tried and move to a
different approach.
```

Inject evaluator feedback directly in rework mode so the generator knows exactly what to fix before filesystem navigation. Use fresh mode as the escape hatch when targeted fixes keep missing the issue.

**Artifact requirement:** Append this to every generator prompt:

```
Write all reasoning and outputs to files in {artifact_dir}/round-{N}/.
```

**Key rules:**
- Give the generator the full task description, criteria, and artifact directory path
- Keep the evaluator's framing, reasoning, and role out of the generator prompt
- On iteration > 1 in rework mode, inject evaluator feedback directly into the prompt; artifact navigation is available for deeper context. In fresh mode, the generator navigates prior artifacts selectively via Read/Grep
- Let the generator write files directly (Edit/Write tools)
- Have the generator run tests when test commands are available

**Before spawning the generator**, the orchestrator creates `{artifact_dir}/round-{N}/` so the directory exists for both the generator's approach file and the post-generator artifact writes.

**After the generator completes** (linear mode), the orchestrator:
1. Updates `harness-state.json`: increment iteration, record generator's files changed
2. Writes `{artifact_dir}/round-{N}/files-changed.json` listing files touched with action type
3. Copies each target file to `{artifact_dir}/round-{N}/snapshots/` preserving project-relative paths

**Competitive mode (`--competitive N`):**

**Rework iterations in competitive mode:** When `retry_mode` is `"rework"`, competitive mode drops to a single generator for that iteration. Multiple candidates reworking the same code produce near-identical fixes with little added diversity. The single rework generator uses the inherited host model (ignoring `slot_configs`). If rework fails and the next iteration switches to fresh mode, competitive mode resumes with N candidates. Record `candidates_evaluated: 1` and `winning_candidate: null` for rework iterations in the state file.

**Fresh iterations** (iteration 1, or after rework fallback): Step 1 spawns N generator subagents in parallel instead of 1. Each uses the model from its `slot_configs` entry (resolved in Phase 0 Step 1). If `slot_configs` is empty, all slots use `"inherit"`. Each receives the same prompt template but with a different `STRATEGY HINT` appended, and the ARTIFACTS paths use the candidate subdirectory:

```
Goal: Produce this competitive candidate with the assigned model and strategy while writing candidate-scoped artifacts.

[Candidate {K}] Model: {model from slot_configs[K-1]} | Strategy: {strategy from slot_configs[K-1]}

## ARTIFACTS
READ  (prior context for later rounds): {artifact_dir}/round-{N-1}/candidate-{K}/generator-approach.md
                                       {artifact_dir}/round-{N-1}/evaluator-verdict.md
      (round 1 starts from task context; evaluator-verdict.md is at the round root, not per-candidate)
WRITE (required):      {artifact_dir}/round-{N}/candidate-{K}/generator-approach.md

STRATEGY HINT:
{one of the strategy hints below - a different one per candidate}
```

**Default strategy hints** (assigned round-robin to candidates):
1. "Prioritize correctness - verify every criterion before moving on. Prefer explicit over clever."
2. "Prioritize simplicity - fewest lines, clearest logic. Remove anything not required by criteria."
3. "Prioritize robustness - handle every edge case and failure mode, even ones not in criteria."

If N > 3, cycle back through the hints. If N == 2, use hints 1 and 2.

Each candidate writes to `{artifact_dir}/round-{N}/candidate-{K}/` (K = 1..N) instead of the round root. The `generator-approach.md` file goes inside each candidate directory.

After all N generators complete, the orchestrator proceeds to Step 1.5b (Quick Comparison) instead of Step 1.5.

</details>

#### Step 1.5: Quick Gate (parent, no subagent)

<details>
<summary>Step 1.5: Quick Gate</summary>

Run a fast parent-context sanity check on the generator's output before spending an evaluator call. This catches obviously broken generations while saving evaluator tokens.

1. **Verify files exist.** Glob each target file path. If any file the generator was supposed to create is missing, skip evaluation - log `no_output` and retry.

2. **Run tests if available.** If the project has a test runner (`npm test`, `cargo test`, etc.), run it. If tests fail, skip evaluation - log the failure and go directly to the next generator iteration with the test failure as a constraint.

3. **Syntax check.** For TypeScript: `tsc --noEmit`. For Rust: `cargo check`. For Python: `python -m py_compile`. If syntax is broken, skip evaluation.

Keep quick-gate failures outside framing rotation because the evaluator never ran. Give the generator another attempt with the failure evidence.

**Artifact trail on failure:** Write a minimal `{artifact_dir}/round-{N}/generator-approach.md` noting the quick gate failure reason (e.g., "Quick gate: test failure in auth.test.ts - TypeError at line 42"). This keeps the artifact trail complete even for failed rounds, so future generators can see what was tried.

**Competitive mode:** In competitive mode, run the Quick Gate on each candidate separately. Track which candidates pass and which fail. Then proceed to Step 1.5b.

</details>

#### Step 1.5b: Quick Comparison (competitive mode only, parent, no subagent)

<details>
<summary>Step 1.5b: Quick Comparison</summary>

Select the best candidate from the N generators when `mode: "competitive"` and advance that candidate to evaluation.

1. **Tally Quick Gate results.** Count how many candidates passed Step 1.5.

2. **Zero pass:** Pick the candidate that got furthest - most target files created, fewest test failures. This candidate proceeds to Step 2 so the evaluator still gets something to review (it will likely fail, but the failure evidence helps the next iteration).

3. **Exactly one passes:** That candidate wins. Skip to promotion.

4. **Multiple pass:** The parent reads each passing candidate's `generator-approach.md` and the key output files (first 100 lines of each target file). Then selects the best using this inline prompt (no subagent - this is a lightweight decision):

   ```
   Goal: Select the best candidate from {K} implementation candidates that passed basic quality gates.

   Success means:
     - The winner is the candidate with strongest criterion coverage and simplest acceptable risk profile.
     - The response uses exactly the WINNER and REASON lines below.
     - The reason is concise and evidence-based.

   Stop when: One candidate is selected and the required response lines are complete.

   ACCEPTANCE CRITERIA:
   {C1, C2, ... CN}

   CANDIDATE {K1}:
   Model: {model from slot_configs[K1-1]}
   Strategy: {from generator-approach.md}
   Key files: {first 100 lines of each target file}

   CANDIDATE {K2}:
   ...

   Reply with: WINNER: {candidate number}
   REASON: {2 sentences max}
   ```

5. **Promote winner.** Copy the winning candidate's files from `candidate-{K}/` to the round root (`{artifact_dir}/round-{N}/`). Copy `generator-approach.md`, `files-changed.json`, and `snapshots/`. Losers' directories remain for reference.

6. **Update state.** Record `winning_candidate: K` and `candidates_evaluated: N` in the current iteration entry of `harness-state.json`.

</details>

#### Step 1.7: Fixer (only after Stage A failures)

<details>
<summary>Step 1.7: Fixer</summary>

Run the fixer only when Stage A returns `HAS_FAILURES`. On `ALL_PASS`, skip directly to Stage B. The fixer is a lighter-tier subagent that applies targeted fixes based on evaluator evidence, writing corrected files to a separate directory for arbitration.

**When to run:** Run after Stage A completes with `HAS_FAILURES` and identifies specific failures.

**Fixer prompt template:**

```
Goal: Apply minimal targeted fixes for the Stage A failures into the fixer output directory.

Success means:
  - Each listed FAIL verdict receives the smallest code change that resolves the evaluator evidence.
  - Fixed files are written under OUTPUT DIRECTORY with project-relative paths preserved.
  - Issues that require architectural redesign are recorded with a short note explaining why they were skipped.

Stop when: Every listed issue has either a fixed file in fixer-output/ or a note explaining why it was skipped.

You are a code fixer. Specialist reviewers have identified issues in the implementation.
Apply minimal, targeted fixes for each issue.

ISSUES TO FIX (from evaluator evidence):
{for each FAIL verdict from Stage A:}
CRITERION: {criterion ID} - {criterion description}
EVIDENCE: {evaluator's staged/fix/rationale from the XML verdict}
FILE: {file path from evidence}

FILES TO READ AND FIX:
{list of file paths with FAIL verdicts}

OUTPUT DIRECTORY: {artifact_dir}/round-{N}/fixer-output/

INSTRUCTIONS:
1. Read each affected file from the project directory.
2. Apply the minimal fix described in the evaluator's evidence.
3. Write the fixed version to {artifact_dir}/round-{N}/fixer-output/{relative-path}
   (preserving project-relative paths, same as snapshots/).
4. If an issue's fix description is unclear or would require fundamentally changing
   the architecture, record it as skipped and note why.
5. Keep fixes minimal - change the code needed to resolve each issue.

CONSTRAINTS:
- Do NOT run `git add` or `git commit`
- Do NOT modify files in the project directory - write ONLY to fixer-output/
- Keep refactors and improvements outside the listed issue scope.
- Leave files that have PASS verdicts unchanged.
- Apply fixes in priority order: address all FAIL criteria
```

**After the fixer completes**, the orchestrator:
1. Lists files in `{artifact_dir}/round-{N}/fixer-output/`
2. Records `fixer_ran: true` and `fixer_files: [list of paths]` in the iteration state
3. Proceeds to Step 1.8 (Arbitration)

**If the fixer fails or produces no output:** Proceed through the existing rework/fresh retry logic in Step 3. Record `fixer_ran: false`.

**Model:** Use a lighter tier for the fixer; it applies prescribed fixes as mechanical work while heavier model budget stays reserved for evaluation.

</details>

#### Step 1.8: Arbitration (only when fixer ran)

<details>
<summary>Step 1.8: Arbitration</summary>

Compare the generator's original files (in `snapshots/`) against the fixer's corrected files (in `fixer-output/`) and produce per-file accept/reject verdicts. This replaces binary "regenerate everything" with granular file-level arbitration.

**When to run:** Run only when Step 1.7 ran and `fixer_ran: true`; otherwise route to Step 3 (Parse and Decide) with the original Stage A results.

Perform arbitration in the orchestrator parent context:

1. **List fixer output.** Glob `{artifact_dir}/round-{N}/fixer-output/` to get all fixed files.

2. **For each fixed file**, read both versions:
   - Original: `{artifact_dir}/round-{N}/snapshots/{relative-path}`
   - Fixed: `{artifact_dir}/round-{N}/fixer-output/{relative-path}`

3. **Compare and decide.** For each file, apply the strict improvement criteria from `references/evidence-schema.md`:
   - **Accept** if the fix addresses a specific FAIL criterion, preserves intent, and is minimal in scope.
   - **Reject** if the fix alters design decisions, removes functionality, or goes beyond the identified issue.

4. **Promote accepted files.** For each accepted file, copy it from `fixer-output/` to the project directory (overwriting the generator's version). Rejected files keep the generator's original.

5. **Record verdicts.** Write `arbitration_verdicts` to the iteration state: a map of `{filepath: "accept" | "reject", reason: "one line"}`.

6. **Re-evaluate.** After promoting accepted files, re-run Stage A on the updated files. The re-evaluation determines whether the fixes resolved the failing criteria. This re-evaluation counts as the same iteration.

If arbitration accepts fixes that resolve all Stage A failures, the re-evaluation returns `ALL_PASS` and proceeds to Stage B. If failures remain, proceed to Step 3 with `HAS_FAILURES` (the remaining failures feed into the next iteration's rework/fresh logic).

</details>

#### Step 2: Evaluate (Two-Stage Sequential Review)

Run evaluation in two sequential stages. Stage A (spec compliance) must pass before Stage B (code quality) runs. This preserves correctness before quality review begins.

##### Stage A: Spec Compliance (Codex)

<details>
<summary>Stage A: Spec Compliance (Codex)</summary>

Use Stage A as **the grader for spec-compliance** in the managed-agents sense. Its separate Codex context window structurally mirrors the managed-agents grader's isolation property and keeps generator bias out of the review.

Invoke the evaluator via the codex-companion runtime (strata: `bin/strong`/`bin/grader`). This reviewer checks ONLY whether the implementation matches what was asked for. Binding the evaluator to a different model family than the generator provides cross-model adversarial diversity by construction, so Stage A gets bias-breaking from model isolation.

**Before invoking Stage A**, the orchestrator:
1. Writes the evaluation prompt to `{artifact_dir}/round-{N}/stage-a-prompt.md` (Codex reads files more reliably than receiving long inline prompts)
2. Builds a Candidate Summary from the just-completed generator(s) and Quick Gate results

Candidate Summary format (prepended to the prompt file):

```
## Candidate Summary
### Candidate 1 — PASSED Quick Gate | Model: {model} | Strategy: {strategy}
Files changed: {files from files-changed.json}

### Candidate 2 — FAILED Quick Gate | {failure reason, e.g. tsc error: Property 'x' does not exist}
[failed candidate listed for context only]
```

**Build this summary from Quick Gate status, model/strategy metadata, and files changed.** The evaluator must not see generator reasoning; evaluator never sees the task description or generator reasoning. The evaluator reads actual code files from disk for the real review.

Send only the winning candidate (in competitive mode) to criteria evaluation. List failed candidates for context while keeping them outside the review target.

**Spec compliance prompt (written to stage-a-prompt.md):**

```
<task>
Goal: Verify whether the evaluated code satisfies each acceptance criterion using direct file evidence.

Success means:
  - Every file listed in FILES TO EVALUATE is read from disk.
  - Every criterion receives PASS or FAIL with specific file:line evidence.
  - The response includes the required XML verdict block plus OVERALL, STATUS, CONCERNS, and SPINNING_REASON lines.

Stop when: Each criterion has a structured verdict, tests have run when present, and all required status lines are present.

Use the acceptance criteria and actual code as the review source. The task description
and generator reasoning are intentionally outside this context. Treat implementer
summaries as unverified leads and verify each claim against code.
</task>

<grounding_rules>
- Read every file listed in FILES TO EVALUATE from disk and cite observed code.
- Treat any summary or report from the implementer as unverified until actual code confirms it.
- Scope this pass to criterion satisfaction. Leave code quality, style, and elegance to Stage B.
- For each criterion, produce a verdict: PASS or FAIL.
- For FAIL verdicts: provide specific evidence (file path, line number, what's
  wrong vs what was expected).
- If tests exist, run them. Test failures are automatic FAIL for related criteria.
</grounding_rules>

<recon_dispatch>
Ground-truth recon for this harness run is owned upstream by the `/recon` skill (the
orchestrator invokes it before kicking off the harness when criteria depend on
repository-wide claims). If a recon brief path appears in FILES TO EVALUATE (typically
`/tmp/recon-{slug}.md`), treat it as validated context and cite it like any other
file:line evidence.

Read the explicit files in FILES TO EVALUATE yourself. For any criterion whose verdict
hinges on a repository-wide fact (caller graphs, feature/flag references, edge-case
handling across modules, test results) that is not covered by FILES TO EVALUATE or the
recon brief, mark the criterion FAIL with EVIDENCE: "unverified — recon coverage
missing" rather than guessing PASS.
</recon_dispatch>

ACCEPTANCE CRITERIA:
{C1, C2, ... CN - identical to what the generator received}

FILES TO EVALUATE:
{list of file paths the generator created/modified}

ITERATION CONTEXT:
Retry mode: {retry_mode - "fresh" or "rework"}
{if rework: "Prior failure evidence that was sent to the generator:" followed by
the criterion IDs and file:line references from the evaluator_feedback}

SPINNING CHECK:
{if iteration > 1: "Compare this implementation against the prior round's snapshot
at {artifact_dir}/round-{N-1}/snapshots/. If the logic is substantively identical
(same structure and unchanged logic), return SPINNING with cited locations. In
rework mode, return SPINNING when the specific lines/functions cited in the prior
round's failure evidence are unchanged; otherwise evaluate criteria."}

<structured_output_contract>
For EVERY criterion, produce a structured XML verdict.
All 5 child elements (staged, fix, rationale, if-accepted, if-rejected) are REQUIRED
on every verdict - both PASS and FAIL. A valid response includes every element.

<verdicts>
  <verdict criterion="C1" result="PASS|FAIL">
    <staged>What the implementation actually does for this criterion (cite file:line)</staged>
    <fix>What needs to change (FAIL) or why no change needed (PASS)</fix>
    <rationale>Objective reason for the verdict</rationale>
    <if-accepted>Consequence if this implementation ships as-is</if-accepted>
    <if-rejected>Consequence if sent back for rework</if-rejected>
  </verdict>
  ...
</verdicts>

OVERALL: ALL_PASS | HAS_FAILURES

STATUS: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT | SPINNING
CONCERNS: [only if DONE_WITH_CONCERNS - specific issues that passed criteria but seem wrong]
SPINNING_REASON: [only if SPINNING - what's identical vs the prior round and where]
</structured_output_contract>
```

**Codex invocation:**

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" task \
  --effort xhigh \
  "Read the evaluation prompt at {artifact_dir}/round-{N}/stage-a-prompt.md. \
   Follow it exactly. Read every file listed in FILES TO EVALUATE from disk. \
   Return your verdicts in the XML format specified in the prompt."
```

Use Bash tool with `timeout: 600000` (10 minutes). Capture stdout as the Stage A output.

**After Stage A completes:** Capture the full Codex output (verbatim) for the artifact file. Hold it in memory until Stage B completes or is skipped.

**If Stage A returns `HAS_FAILURES` or `BLOCKED`:** Skip Stage B entirely. Write `{artifact_dir}/round-{N}/evaluator-verdict.md` with the Stage A output and a note that Stage B was skipped.

**If Stage A returns `NEEDS_CONTEXT`:** Provide the missing context (appends to stage-a-prompt.md) and re-run Stage A (counts as the same iteration).

**If Codex is unavailable or errors:** Fall back to spawning a general-purpose subagent with `model: "inherit"` for this stage. Log "Codex: unavailable, fell back to the inherited model" in the iteration state. Treat this as degraded mode because the loop continues with the cross-model benefit lost.

</details>

##### Stage A.5: Removed

Keep Stage A.5 as removed terminology. Stage A itself now runs on Codex, so a separate Codex pass would be redundant. The cross-model adversarial benefit that Stage A.5 previously provided is now structural: Codex evaluates everything the Claude generator produces.

##### Stage B: Code Quality (Codex, only if Stage A passes)

<details>
<summary>Stage B: Code Quality (Codex)</summary>

Use Stage B as **a second-pass adversarial grader for quality**, applied after the spec-compliance grader passes. Keep the same isolation property as Stage A (Codex, separate context window from the generator) and rotate framing each iteration so the two passes catch different failure classes.

Invoke Codex via the codex-companion runtime. This reviewer applies the adversarial framing and checks code quality independently. It never sees Stage A's output.

**Before invoking Stage B**, the orchestrator writes the evaluation prompt to `{artifact_dir}/round-{N}/stage-b-prompt.md`.

**Code quality prompt (written to stage-b-prompt.md):**

```
<task>
Goal: Identify code-quality risks in the evaluated files after spec compliance has passed.

Success means:
  - Every file listed in FILES TO EVALUATE is read from disk.
  - Findings are grounded in bugs, security issues, race conditions, error handling gaps, project-constraint violations, maintainability problems, or edge cases.
  - Each finding has a CRITICAL or WARNING severity and specific file:line evidence.
  - The response includes OVERALL, NOTES, and STATUS lines using the vocabulary below.

Stop when: All evaluated files have been reviewed for quality risks and the structured output is complete.

{adversarial framing preamble from references/evaluator-framings.md}
{{strictness}}

Review code quality. The code has already passed a spec-compliance review and satisfies
the acceptance criteria. Find bugs outside the spec coverage, security holes,
maintainability problems, and edge cases.

Use direct code evidence. The task description and implementation rationale are
intentionally outside this review context.
</task>

<grounding_rules>
- Read every file listed in FILES TO EVALUATE from disk and cite observed code.
- Trace bugs, security issues, race conditions, missing error handling,
  violations of project constraints, maintainability problems, and edge cases.
- For each finding, provide specific evidence (file path, line number, what's wrong).
- Categorize findings as CRITICAL (must fix) or WARNING (should fix).
- CRITICAL findings result in FAIL. WARNING-only results in PASS with notes.
</grounding_rules>

<recon_dispatch>
Ground-truth recon for this harness run is owned upstream by the `/recon` skill (the
orchestrator invokes it before kicking off the harness when findings depend on
repository-wide claims). If a recon brief path appears in FILES TO EVALUATE (typically
`/tmp/recon-{slug}.md`), treat it as validated context and cite it like any other
file:line evidence.

Read the explicit files in FILES TO EVALUATE yourself. For any finding whose severity
hinges on a repository-wide fact (call-site error handling, pattern reuse across the
repo, linter/typechecker output, dependency initialization) that is not covered by
FILES TO EVALUATE or the recon brief, downgrade to WARNING with EVIDENCE: "severity
unverified — recon coverage missing" rather than escalating to CRITICAL on assumption.
</recon_dispatch>

ACCEPTANCE CRITERIA (for reference only - spec compliance already verified):
{C1, C2, ... CN}

FILES TO EVALUATE:
{list of file paths the generator created/modified}

<structured_output_contract>
FINDING: [description]
SEVERITY: CRITICAL | WARNING
EVIDENCE: [file:line reference]

...

OVERALL: ALL_PASS | HAS_FAILURES
NOTES: [optional observations]

STATUS: DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT
</structured_output_contract>
```

**Codex invocation:**

```bash
node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" task \
  --effort xhigh \
  "Read the evaluation prompt at {artifact_dir}/round-{N}/stage-b-prompt.md. \
   Follow it exactly. Read every file listed in FILES TO EVALUATE from disk. \
   Return your findings in the format specified in the prompt."
```

Use Bash tool with `timeout: 600000` (10 minutes). Capture stdout as the Stage B output.

**After Stage B completes:** Write `{artifact_dir}/round-{N}/evaluator-verdict.md` containing both Stage A and Stage B output (concatenated, verbatim). The evaluator never sees the artifact directory; the orchestrator writes this file.

**Key rules:**
- Give Stage B criteria and files only; evaluator never sees the task description
- Give Stage B the adversarial framing preamble (rotated per iteration)
- Keep Stage A output, generator reasoning, harness state, and artifact directory outside Stage B context
- Treat CRITICAL findings as FAIL. Surface WARNINGs while allowing completion under `critical-only`.

**If Codex is unavailable or errors:** Fall back to spawning a general-purpose subagent with `model: "inherit"` for this stage. Log "Codex: unavailable, fell back to the inherited model" in the iteration state.

</details>

##### Status Vocabulary

Route subagent results through the four-state status vocabulary, and treat `SPINNING` as a convergence signal from Stage A.

| Status | Orchestrator action |
|--------|-------------------|
| `DONE` | Proceed to next stage or complete |
| `DONE_WITH_CONCERNS` | Proceed but surface concerns to user |
| `BLOCKED` | Escalate to user - something prevents evaluation |
| `NEEDS_CONTEXT` | Provide missing context and re-run this stage |

Handle `SPINNING` through the convergence detector path: force framing change and inject a different-approach hint. Route on the status keyword alone.

#### Step 3: Parse and Decide

<details>
<summary>Step 3: Parse and Decide</summary>

Parse Stage A and, if it ran, Stage B output in the parent orchestrator context; then run convergence detection to pick the next action.

1. **Parse Stage A.** Extract per-criterion verdicts from `<verdicts>` XML block. For each `<verdict>` element, extract: `criterion` attribute, `result` attribute (PASS/FAIL), and all 5 child elements (staged, fix, rationale, if-accepted, if-rejected). If any verdict is missing child elements, re-prompt the evaluator with: "Verdict for {criterion} is missing required evidence fields. Resubmit with all 5 fields per references/evidence-schema.md."

   - If Stage A `OVERALL: HAS_FAILURES` or `STATUS: BLOCKED`: Run Step 1.7 (Fixer) if FAIL verdicts have actionable evidence. If fixer is not applicable (e.g., BLOCKED), skip fixer and collect failure evidence for the next generator iteration. Stage B does not run.
   - If Stage A `STATUS: NEEDS_CONTEXT`: provide context and re-run Stage A (same iteration).
   - If Stage A `STATUS: SPINNING`: treat as HAS_FAILURES; the convergence detector below handles spinning escalation.
   - If Stage A `OVERALL: ALL_PASS`: skip fixer (Step 1.7). If `done_bar == "stage-a-only"`, skip Stage B and treat the iteration as DONE. Otherwise proceed to Stage B.

2. **Parse Stage B** (only if Stage A passed and `done_bar != "stage-a-only"`). Extract findings with CRITICAL/WARNING severity.

   - `done_bar == "critical-only"` (default): CRITICAL findings -> `HAS_FAILURES`. WARNING-only -> `ALL_PASS`.
   - `done_bar == "no-warnings"`: any finding (CRITICAL or WARNING) -> `HAS_FAILURES`. Only zero findings -> `ALL_PASS`.

3. **Compute the failing set and fix count for this iteration.**
   - `failing_set` = the set of criterion IDs that returned FAIL in Stage A this iteration, plus any Stage B findings that count as failures under the current `done_bar` (identified by their evidence file:line as a stable key).
   - `fix_count` = number of items removed from the failing set since the previous iteration (i.e., `prev_failing_set \ current_failing_set`, length of the difference). For iteration 1, `fix_count = null` (no baseline).
   - Append both to `convergence_state.failing_set_history` and `convergence_state.fix_count_history` in `harness-state.json`. Also accumulate token usage from Stage A + Stage B + generator into `convergence_state.cumulative_tokens` (estimate from response sizes if exact counts are not available).

4. **Update state file.** Add iteration result to `harness-state.json`:
   ```json
   {
     "iteration": N,
     "framing_used": "security-audit",
     "stage_a": { "verdicts": { "C1": "PASS", "C2": "FAIL" }, "status": "DONE" },
     "stage_b": { "findings": [...], "status": "DONE_WITH_CONCERNS" },
     "overall": "HAS_FAILURES",
     "failing_set": ["C2", "stage-b:src/api.ts:42"],
     "fix_count": 1
   }
   ```
   If Stage B didn't run (Stage A failed or `stage-a-only`), set `"stage_b": null`.

5. **Run convergence detectors and decide next action.** Evaluate in order; the first match wins.

   **(a) DONE — Stage A `ALL_PASS` AND Stage B meets `done_bar`:**
   Set `status: "complete"`, `termination_reason: "done"`. Break to Phase 2.

   **(b) Cost soft warning — `cumulative_tokens > cost_warn_threshold`:**
   Print one warning to the user: "Soft cost cap exceeded ({cumulative} tokens > {threshold}). Continuing - run will keep iterating until convergence or escalation. Re-run with `--cost-warn N` to adjust." Print this warning at most once per run (set `cost_warning_emitted: true` in state). Then continue with the rest of the detectors. Use detectors and user escalation for termination after the warning.

   **(c) SPINNING — failing set unchanged for 2 consecutive iterations** (i.e. iteration N's `failing_set` equals iteration N-1's, set-equal as multisets):
   - First strike (`spinning_strikes == 0`): increment `spinning_strikes` to 1. Force-rotate Stage B framing to the next unused framing for this run (cycle back if all are used, but skip the framing used most recently). Prepend to the next generator prompt: "Take a substantially different approach because the prior attempt made no meaningful progress on the same failing criteria. Use a different structure and strategy." Continue loop with `retry_mode: "fresh"`.
   - Second strike (`spinning_strikes == 1`): set `spinning_strikes` to 2 and escalate to user (see Step 6).

   **(d) OSCILLATING — failing set grew vs the previous iteration** (`|current_failing_set| > |prev_failing_set|`, i.e. the fix introduced new failures):
   - First strike (`oscillating_strikes == 0`): increment to 1. Set `retry_mode: "fresh"` for the next iteration. The targeted fix is breaking other passing behavior; a clean rewrite is more likely to converge than continued patching. Continue loop.
   - Second strike (`oscillating_strikes == 1`): escalate to user.

   **(e) STRUCTURAL — same criterion in failing set for 3 consecutive iterations** (per-criterion persistence, computed by intersecting the last 3 entries of `failing_set_history`):
   - First strike (`structural_strikes == 0`): increment to 1. Set `retry_mode: "fresh"`. The same criterion has resisted both rework and any prior fresh attempts, indicating a structural mismatch between approach and criterion. Continue loop.
   - Second strike (`structural_strikes == 1`): escalate to user.

   **(f) DIMINISHING_RETURNS — `fix_count` strictly decreased over the last 3 iterations** (e.g., 5, 3, 1) AND iteration count >= 4:
   - First strike (`diminishing_strikes == 0`): increment to 1. Continue loop with `retry_mode: "fresh"`. Marginal-progress runs sometimes break free with a rewrite.
   - Second strike (`diminishing_strikes == 1`): escalate to user.

   **(g) Default — none of the above match, `HAS_FAILURES`:** Prepare the next iteration:
   - Extract structured feedback from evaluator output: for each FAIL criterion, capture the criterion ID, description, and the evaluator's specific evidence (file:line, what's wrong vs expected). For CRITICAL Stage B findings, capture finding description and evidence.
   - **Update per-criterion rework counters:** For each failing criterion ID, check `rework_fail_counts` in state. If this criterion also failed in the previous rework iteration, increment its count. If it passed or this is the first rework iteration, reset its count to 0. Criteria that passed are removed from the map.
   - **Determine retry mode:** If any criterion in `rework_fail_counts` has count >= 2, set next iteration's `retry_mode: "fresh"`. Otherwise, set `retry_mode: "rework"`. (This is a fast structural-failure check that can fire before STRUCTURAL kicks in at iteration 3.)
   - Store `evaluator_feedback` in the iteration entry (structured array of `{criterion_id, description, evidence}` for Stage A failures + `{finding, severity, evidence}` for Stage B criticals). This is what gets injected into the next generator's prompt.
   - Rotate Stage B's adversarial framing for the next iteration. Pick the next framing from `references/evaluator-framings.md` that has the earliest unused position in the rotation order.
   - Leave implementation fixes to the next generator.

6. **User escalation (when a detector reaches its second strike).**
   Set `status: "escalated"` and write `termination_reason: "spinning" | "oscillating" | "structural" | "diminishing_returns"` to state. When any convergence detector fires twice, the loop MUST escalate to the user. Pause the loop and present a structured summary to the user via AskUserQuestion (load the `ask-better` skill first):
   - Current `failing_set` with each item's most recent evaluator evidence
   - `fix_count_history` to show the trajectory
   - Cumulative token usage
   - Which detector fired, twice
   - Options: (i) Continue loop (resets the firing detector's strike counter to 0, all others stay), (ii) Abort and ship partial state, (iii) Refine criteria and restart Phase 0 with the new criteria (preserves artifact directory).

   Apply the user's choice to resume or terminate the loop. Escalation is the safety boundary after a second strike.

7. **Report iteration result.** Brief status: "Iteration {N} ({retry_mode}, {framing} framing): Stage A {passed}/{total} criteria. Stage B: {result or skipped}. Failing set: {N items} (was {M last iteration}). {Next action}."

</details>

### Phase 2: Wrap-up

<details>
<summary>Phase 2: Wrap-up</summary>

Close the run by reporting cost, final state, iteration history, next steps, insights, and artifact location.

1. **Cost report.** Report actual usage from `convergence_state.cumulative_tokens` and the iteration count:
   - **Linear mode:**
     - Generator calls: {iteration_count} generator subagent spawns
     - Stage A (spec compliance) calls: {iteration_count} Codex task invocations
     - Stage B (code quality) calls: {stage_b_count} Codex task invocations (skipped when Stage A fails or `done_bar == "stage-a-only"`)
     - Cumulative tokens: {cumulative_tokens} ({"exceeded soft cap of " + cost_warn_threshold if exceeded else "under soft cap of " + cost_warn_threshold})
   - **Competitive mode:**
     - Generator calls: {iteration_count * candidates_per_round - rework_iteration_count * (candidates_per_round - 1)} generator subagent spawns (rework iterations drop to 1 candidate)
     - Stage A + Stage B: same as linear (only the winning candidate is evaluated)
     - Cumulative tokens: as above

2. **Update state file.** Set `status` to `"complete"` (DONE), `"escalated"` (user paused via convergence detector), `"aborted"` (user chose abort during escalation), or `"error"`. Record `termination_reason`. Record final verdicts.

3. **Summary table:**
   ```
   Iteration | Mode    | Candidates | Stage A    | Stage B (framing)           | Failing | Fix# | Overall
   1         | fresh   | 1          | 3/5 FAIL   | skipped                     | 2       | -    | HAS_FAILURES
   2         | rework  | 1          | 5/5 PASS   | 1 CRITICAL (spec-lawyer)    | 1       | 1    | HAS_FAILURES
   3         | rework  | 1          | 5/5 PASS   | 0 findings (security-audit) | 0       | 1    | ALL_PASS
   ```

4. **Suggest next steps:**
   - If `complete`: "Run `/verify` to confirm, then commit."
   - If `escalated`: "Convergence detector {reason} fired twice. Failing set: {list}. The user chose to pause - resume with the same `/harness` command, or refine criteria and restart."
   - If `aborted`: "User aborted at iteration {N}. Partial state preserved at {artifact_dir}."
   - If a spec is active: "Update spec's `>> Current Step` and check completed boxes."

5. **Extract insights.** Review the iteration history and extract patterns:
   - Which criteria failed most often? (recurring weakness in generation)
   - Which framing caught issues the others missed? (framing effectiveness signal)
   - What failure patterns appeared across iterations? (e.g., "generator consistently misses input validation")
   - Write a 2-3 sentence `insights` field in the state file summarizing what this run revealed.

6. **Update framing memory.** Append this run's framing effectiveness data to `$STATE_DIR/harness-memory.json` (create if missing). See `references/evaluator-framings.md` for the memory schema. This accumulates across runs so future framing selection gets smarter.

   For each framing used in this run, record:
   - `task_type`: derived from the task (api, library, frontend, performance, general)
   - `framing`: which framing was used
   - `findings_count`: number of FAIL verdicts this framing produced
   - `unique_findings`: findings this framing caught that others in the same run didn't
   - `timestamp`: when the run happened

7. **Clean up.** The state file and artifact directory stay on disk for reference and debugging. Report the artifact directory location: "Artifacts at {artifact_dir}/". Old runs are cleaned up at Phase 0 of the next `/harness` invocation (not now), keeping the last 3 runs.

</details>

## State Recovery

<details>
<summary>State Recovery</summary>

Recover active harness state after compaction or session resume:

1. **Determine your session ID.** It's the 8-char suffix of your daily note filename (from SessionStart hook output).

2. **Read `$STATE_DIR/harness-state-{session-id}.json`.** If it exists and `status` is `running`:
   - This is your own state file - resume directly. Keep other sessions' state files (different `{session-id}` suffix) untouched.
   - Read `iteration` to know where you are.
   - Read `artifact_dir` from the state file. Verify the directory exists.
   - The artifact directory is the ground truth for what happened in prior rounds. The state file's `iterations` array is a summary index.
   - Resume logic: if the last round has `evaluator-verdict.md` in its artifact directory, start the next generator iteration. If it has `generator-approach.md` but no verdict, run evaluation. If neither, re-run the generator.

3. **If state file is missing or `status` is not `running`:** Treat the session as having no active harness. Start fresh if the user re-invokes.

</details>

## Error Recovery

<details>
<summary>Error Recovery</summary>

Recover from tool, generator, evaluator, and concurrency failures with explicit state updates.

| Failure | Recovery |
|---------|----------|
| Generator hits turn limit (not quality failure) | Capture current target files as `completedDiff` snapshot to `{artifact_dir}/round-{N}/snapshots/`. Retry same iteration with `CONTINUATION CONTEXT` block prepended to generator prompt: "This is a continuation - the previous run was interrupted by turn limit. Progress so far: [snapshot ref]. Pick up where it left off and continue from completed work." Cap at 1 continuation per iteration. If continuation also hits turn limit, proceed to evaluation with whatever exists. |
| Generator subagent fails/crashes | Log iteration as `error`, retry once. If second failure, abort with state saved |
| Evaluator subagent fails/crashes | Log iteration as `error`, retry with same files. If second failure, skip evaluation and ask user |
| Evaluator output unparseable | Retry evaluator once with stricter format instructions. If still unparseable, treat as ALL_FAIL |
| Generator produces no file changes | Log as `no_output`, retry once. If second time, abort - task may be unclear |
| All framings consumed in a rotation cycle without DONE | Cycle back to the most relevant framing. Record the cycle completion in state. |
| Concurrent harness in another session edits the same files | State files are session-isolated and separate by construction. The guard clause warns at start when target_files overlap. If a mid-run conflict surfaces (Quick Gate sees unexpected changes), pause and ask the user how to proceed |

</details>

## Core Invariants

Keep these structural properties intact throughout the run.

- **Evaluator asymmetry:** Give the evaluator criteria and output files only; evaluator never sees the task description or generator reasoning. The evaluator judges criteria against code, not intent against code. This asymmetry is the core mechanism for preventing "did they try to do the task" rubber-stamping.
- **Generator asymmetry:** Give the generator concrete failure evidence, while keeping evaluator framing and reasoning outside the generator context.
- **Rework-first retry:** Use targeted rework with evaluator feedback as the default retry. Use fresh generation after any criterion fails in 2 consecutive rework attempts.
- **Binary rubric:** Use PASS/FAIL criteria and leave scores or partial credit out of the loop. Binary gates force specific, testable criteria and block "close enough" rationalizations.
- **Framing rotation:** Rotate evaluator framings on consecutive iterations to break systematic bias. Different framings catch different failure classes.
- **Convergence termination:** Keep termination convergence-based by design: DONE, SPINNING, OSCILLATING, STRUCTURAL, DIMINISHING_RETURNS, plus user escalation on second strike. A fixed iteration count is a weaker signal than convergence detection because it can terminate correct loops too early and give bad ones false legitimacy.
- **Second-strike escalation:** When any convergence detector fires twice, the loop MUST escalate to the user via AskUserQuestion. Escalation preserves the safety design.
- **Cost signal:** When `cumulative_tokens > cost_warn_threshold`, print the warning once so the user can intervene before more tokens burn.
- **Criteria stability:** Freeze criteria at Phase 0. When criteria are wrong, escalate and restart with better criteria; the "refine criteria and restart" branch in Step 6 is the supported path.
- **Cross-model evaluation:** Run evaluators through the evaluator lane (codex-companion runtime; strata `bin/strong`/`bin/grader`), bound to a different model family than the generator. The cross-model asymmetry is the core mechanism; a model evaluating its own family's output loses the adversarial benefit. Use a same-family fallback only when the cross-family evaluator is unavailable (degraded mode).
- **Competitive cost:** Monitor the cost soft warning closely in `--competitive` mode. N candidates per iteration multiply generator cost. Lower the `--cost-warn` threshold for competitive runs (e.g. `--cost-warn 250000`) so the warning fires earlier and the user can intervene before runaway spend.
- **File-based evaluator prompt:** Write the evaluation prompt to a file and tell Codex to read it. File-based prompting is more reliable for structured output than truncated inline prompt content in Codex task commands.
- **Evaluator filesystem scope:** Write all context into the prompt file. Keep the artifact directory path out of the Codex task command so Codex navigates only the files it is evaluating, not harness internals.

## Quality Self-Check

Verify these properties after the loop completes:

1. **Cross-model asymmetry maintained** - generators and evaluators run on different-model-family lanes (evaluators via the codex-companion runtime / `bin/grader`). Evaluator prompt files contain zero task description text and zero generator reasoning. The only artifact-directory paths permitted in evaluator prompts are the prior-round `snapshots/` references that drive the SPINNING convergence check. Generator prompts contain zero framing preamble.
2. **Framing rotated** - consecutive iterations used different evaluator framings unless the run completed in 1 iteration
3. **Rework/fresh mode correct** - rework iterations inject evaluator feedback directly; fresh mode only activates when any criterion in `rework_fail_counts` reaches 2; competitive mode drops to single generator during rework iterations
4. **State file valid** - `$STATE_DIR/harness-state-{session-id}.json` has all required fields per `references/state-schema.md` including `run_id`, `artifact_dir`, `definition_of_done`, and `convergence_state` with populated `failing_set_history` and `fix_count_history`. The session-suffixed filename is what allows concurrent harness runs in different sessions
4a. **Convergence detection ran** - every iteration after the first updated `failing_set_history`, `fix_count_history`, and the four strike counters (`spinning_strikes`, `oscillating_strikes`, `structural_strikes`, `diminishing_strikes`). If any detector reached its second strike, `status` is `"escalated"` (or `"aborted"` if user chose abort) and `termination_reason` is set; escalation occurred before any further loop continuation
4b. **Convergence-driven termination** - the skill references `max_iterations` only as managed-agents vocabulary or legacy memory compatibility. Termination is convergence-driven; the loop ends through a detector signal, completion, or user escalation choice
5. **All criteria addressed** - every criterion has a verdict in the final iteration and every criterion remains present through final review
6. **Artifacts complete** - every completed round has `generator-approach.md`, `files-changed.json`, `evaluator-verdict.md`, `stage-a-prompt.md`, `stage-b-prompt.md` (if Stage B ran), and `snapshots/` in its `round-{N}/` directory
7. **Competitive artifacts complete** (competitive mode only) - each round has N `candidate-{K}/` directories, Quick Comparison verdict documented, winning candidate's files promoted to round root
8. **Fixer keeps git state untouched** - fixer prompt contains explicit denial of `git add` and `git commit`; fixer writes only to `fixer-output/` directory and keeps the project directory unchanged
9. **Arbitration reads both directories** - arbitration step compares `snapshots/` (originals) against `fixer-output/` (fixes) per-file; only accepted files get promoted to the project directory
10. **Evidence XML has all 5 fields in every verdict** - every `<verdict>` in Codex output contains `<staged>`, `<fix>`, `<rationale>`, `<if-accepted>`, `<if-rejected>` per `references/evidence-schema.md`
11. **Codex invocation correct** - every Codex call uses `node "${CLAUDE_PLUGIN_ROOT}/scripts/codex-companion.mjs" task --effort xhigh` with `timeout: 600000`, prompt content is in a file rather than inline, and evaluators omit `--write`
12. **Rubric vocabulary present** - `grep -c "rubric\|grader\|gradeable" SKILL.md` returns >= 8 lines with matches across the file, anchoring the skill to the managed-agents conceptual canon. (Note: `grep -c` counts matching lines, not occurrences; total occurrences via `grep -oE "rubric|grader|gradeable" | wc -l` is substantially higher and need not be checked separately.)
13. **Vocab mapping table present** - `grep -c "| evaluator | grader |" SKILL.md` returns >= 1, confirming the Conceptual Lineage callout's mapping table is intact and discoverable
