---
name: best-of-n
description: "Run N parallel candidate implementations via dmux worktrees (default N=3, hard cap N=5) for high-stakes spec phases, then select via criteria-driven DeepSeek swarm gauntlet and tournament (grader + breadth mix) with Codex escalation on canonical triggers. Cross-model asymmetry: Claude generates, DeepSeek/Codex evaluates; per-criterion truth table gates the swarm verdict, mechanical smallest-diff tie-break is final fallback. MANDATORY auto-fire when active spec phase is tagged `BoN: yes`. Triggers on: 'run best-of-n', 'try N parallel', 'generate N candidates and pick', 'parallel candidates', 'best of N implementation', 'spawn parallel implementations', 'compete N approaches', 'BoN this phase'. Also triggers when: active spec's current phase is tagged `BoN: yes` (mandatory, no skip); user faces multiple defensible designs / novel algorithms / irreversible migrations and explicitly wants competition; verify has failed 3 consecutive times on the same files (advisory — surface BoN as alternative). Pairs with /spec (upstream — `BoN: yes` phase tag is the trigger; mantra is 'best-of-N is downstream of better specs'), /harness (HARD MUTEX — a phase tagged both `Harness: yes` AND `BoN: yes` is malformed; fail loud), /dispatch (substrate — dmux dispatch is the parallelism mechanism), /collect (substrate — used to inspect candidate worktree status and clean up losers), /codex-review (escalation evaluator on canonical triggers a-e). Manual: /best-of-n --from-spec [--n K] [--feature-slug SLUG] [--timeout-min N] [--escalate-codex] [--swarm-mix flash,flash,pro]."
tier: core
cost_hint: medium
parallelizable: false
when_to_use: "When entering a spec phase tagged `BoN: yes`, or when an implementation task has multiple credible designs and the cost of picking wrong is high."
---

# /best-of-n

Parallel candidate generation via dmux dispatch with criteria-driven DeepSeek swarm gauntlet and tournament; Codex escalation on canonical triggers. Selection bottleneck mantra: best-of-N is downstream of better specs.

## Conceptual Lineage

`/best-of-n` predates the managed-agents API doc but implements the same outcome+rubric+grader+iteration pattern; see https://platform.claude.com/docs/en/managed-agents/define-outcomes.

**Grader is the evaluation role; the concrete grader in /harness is Codex via the codex-companion runtime; in /best-of-n it is a DeepSeek swarm (grader + breadth) with Codex escalation.** In managed-agents vocabulary: grader is the evaluation role.

In managed-agents terms: the `#### BoN Criteria` block in a spec phase is the *rubric* — a set of explicit, gradeable conditions. The swarm is the *grader* that evaluates each candidate diff against that rubric. Each gauntlet + tournament cycle is one *iteration* toward selecting the best *outcome* (the winning implementation). The cross-model asymmetry (Claude generates, non-Claude evaluates) is the key invariant: neither DeepSeek nor Codex share the generator's training objective, which is the whole point.

## Quick Nav

| Task | Jump to |
|------|---------|
| Run from a spec phase | Auto-Trigger Logic + Phase 0 |
| Choose N candidates | Phase 0 cost confirmation |
| Understand selection | Phase 2: Gauntlet -> Routing -> Tournament |
| Read state schemas | State Schemas section |
| Failure modes | Failure Modes table |

## Usage

```
/best-of-n --from-spec                           # Read criteria from active spec phase
/best-of-n --from-spec --n 5                     # Override default N (max 5 without --force-n)
/best-of-n --from-spec --feature-slug auth-fix   # Override feature slug for run-id collision
/best-of-n --from-spec --timeout-min 45          # Override 30-min wall-clock default
/best-of-n --from-spec --force-n 7               # Override hard cap (cost discipline override)
```

## Skip Conditions

- **Skip if** task is trivial (single file, < 30 lines changed) - parallel candidates have no value
- **Skip if** no `#### BoN Criteria` section exists in the active spec phase AND no inline criteria can be derived
- **Skip if** dmux is not installed (`which dmux` fails) or no dmux tmux session exists
- **Skip if** `/harness` is currently running on the same files (concurrent harness conflict - they evaluate differently)

## Prerequisites

Verify before proceeding:
1. `which dmux-dispatch.sh` returns a path
2. `tmux list-sessions -F '#{session_name}' | grep '^dmux'` finds a session
3. Current directory is a git repo
4. Active spec exists at `$SPECS_DIR/` with current phase tagged `BoN: yes` (when `--from-spec`)

If any fail, tell the user what's missing and how to fix it. Do NOT silently fall back to inline implementation - that defeats the purpose.

## Auto-Trigger Logic

Three conditions that fire /best-of-n:

- **Spec-driven (MANDATORY)**: Active spec's current phase has `BoN: yes`. Invoke with `--from-spec` when entering that phase. This is NOT optional. If you believe BoN is genuinely unnecessary for this phase, ask the user for an explicit skip - do not decide unilaterally.
- **Explicit user request**: User says "run best-of-n", "try N parallel", "generate N candidates and pick".
- **Verify-escalation (advisory)**: After 3 consecutive `/verify` failures on the same files, recommend `/best-of-n` as an alternative to continued iterative fixing.

Mutex with /harness: a phase tagged BOTH `Harness: yes` AND `BoN: yes` is malformed. Stop and report to user; do not pick one unilaterally.

## Guard Clauses

- **Active BoN run check**: If `$STATE_DIR/bon-runs/*/dispatched.json` exists with `status: running` and `session_id` matches yours, offer to resume. If `session_id` differs and `started_at` is within 2 hours, abort: "Another session is running /best-of-n on this feature. Concurrent runs collide."
- **Active spec check**: If `--from-spec`, verify a spec at `$SPECS_DIR/` has `Status: in-progress` and current phase has `BoN: yes`. If not, abort with: "No active spec phase tagged `BoN: yes`. Tag the phase first via /spec, or pass criteria inline."

---

## Phase 0: Setup

### Step 0.1: Parse arguments

Extract:
- `--from-spec` (boolean): read criteria from active spec
- `--n N` (default 3, max 5 without `--force-n`)
- `--feature-slug SLUG` (default: derive from active spec phase name)
- `--timeout-min N` (default 30)
- `--force-n N` (override hard cap)
- `--escalate-codex` (boolean, default false): force ALL gauntlet and tournament decisions through Codex instead of the DeepSeek swarm. Corresponds to escalation trigger (a) in Decision #5.
- `--swarm-mix` (string, default `"flash,flash,pro"`): 3-element comma-separated combination of `flash` and `pro` specifying which ds variant fills each swarm slot. Valid values: any 3-element sequence of `flash`/`pro` (e.g. `"pro,pro,pro"`, `"flash,pro,flash"`).

Reject N < 2 (no diversity) or N > 5 without `--force-n`. Reject `--swarm-mix` values that don't parse as exactly 3 comma-separated elements of `flash`/`pro`.

**Canonical escalation triggers (Decision #5) — reproduced verbatim; apply throughout Phase 2:**

- **(a)** `--escalate-codex` flag passed
- **(b)** N >= 4 AND gauntlet has `p == f` (PASS count equals FAIL count) on any criterion
- **(c)** swarm has `count(TIE+INVALID) >= 2` on any criterion (regardless of N)
- **(d)** tournament has 2 consecutive pairs hit mechanical tie-break
- **(e)** 2+ slots in any single decision exit with code 3 (quota)

### Step 0.2: Active-spec detection and Harness/BoN mutex assertion

If `--from-spec`:
1. Read active spec at `$SPECS_DIR/`. Identify current phase via `>> Current Step`.
2. **Mutex check**: if current phase has `Harness: yes` AND `BoN: yes`, abort with: "Spec malformed: phase '{name}' is tagged both `Harness: yes` and `BoN: yes`. v1 forbids both. Fix the spec by removing one tag, then re-run."
3. Read the phase's `#### BoN Criteria` subsection. If absent, fall back to step acceptance criteria with explicit warning: "WARNING: phase has no `#### BoN Criteria` rubric block. Falling back to step acceptance criteria - they may be too coarse for binary PASS/FAIL gating. Consider adding inline rubric criteria first."

### Step 0.3: Compute run-id and preflight collision check

Run-id format: `{YYYY-MM-DD-HHMMSS}-{session-id-suffix}` (e.g., `2026-04-26-002629-33304782`). Per-second timestamp ensures uniqueness even when same session re-runs same feature within a day.

Slug format: `bon-{feature-slug}-{run-id}-{K}` for K=1..N. Example: `bon-auth-fix-2026-04-26-002629-33304782-1`.

**Preflight collision check** (mandatory; NO bypass flag):
1. Glob existing worktrees at `{project}/.dmux/worktrees/bon-{feature-slug}-*-*`.
2. List git branches matching `bon-{feature-slug}-*-*` via `git branch --list 'bon-{feature-slug}-*-*'`.
3. For each match, check if merged into branch_from: `git branch --merged branch_from | grep -E 'bon-{feature-slug}-*-*'`.
4. If any unmerged matches found, ABORT with informative error:
   ```
   /best-of-n collision detected: unmerged branches/worktrees from prior run(s):
   - bon-auth-fix-2026-04-25-220000-33304782-1 (worktree exists, branch unmerged)
   - bon-auth-fix-2026-04-25-220000-33304782-2 (branch unmerged)

   Remediation:
   - Run /collect to inspect prior run results and decide merge or abort
   - OR manually clean up via `git worktree remove` and `git branch -D` (after confirming no needed work)

   /best-of-n requires a clean slate. No --allow-collision bypass exists in v1.
   ```

### Step 0.4: Cost estimate from history

Read `$STATE_DIR/bon-runs/*/cost.json`. Filter to entries with `source: "measured"`. If 3+ measured runs exist, compute mean wall-clock and (if non-null) mean tokens; surface as "approx (last 3 runs avg): {wall_clock_min} min, {tokens_or 'unavailable'} tokens". If <3 measured runs, surface: "no estimate - first/early run; observe and record".

### Step 0.5: Cost confirmation gate (load /ask-better first)

**Load `/ask-better`** before calling AskUserQuestion. Apply 4-gate filter and Confidence Check.

Then ask:
```
/best-of-n configuration:
- N = {N} candidates ({N} parallel Claude generators in dmux worktrees)
- Evaluator: 3-agent DeepSeek swarm (swarm mix: {swarm_mix})
- Codex escalation auto-fires per Decision #5 triggers (a)-(e); adds Codex-tier cost per escalated decision
  {if --escalate-codex: "  ** --escalate-codex flag set: ALL decisions go through Codex **"}
- Wall-clock timeout: {timeout_min} min (HARD ABORT on timeout - no graceful continuation)
- Estimated cost: {if 3+ measured runs: "approx from history: {wall_clock_min} min" | else: "first-run unknown — log actuals to cost.json.measured_cost"}
- Run ID: {run_id}

Confirm dispatch?
```

Options: Confirm / Lower N to 2 / Abort.

### Step 0.6: Initialize state

Create `$STATE_DIR/bon-runs/{run-id}/` directory.

Write `dispatched.json` per the schema in State Schemas. Set `status: "dispatched"`, `started_at: <ISO timestamp>`.

---

## Phase 1: Dispatch and Poll

### Step 1.1: Build candidate task briefs

For K=1..N, write a task brief at `{project}/.dmux/tasks/bon-{feature-slug}-{run-id}-{K}.md` extending the standard /dispatch brief template (see `$STRATA_HOME/commands/dispatch.md:86-131` for template) with two BoN-specific additions:

**STRATEGY HINT** (round-robin from /harness `--competitive` mode hints):
1. "Prioritize correctness - verify every criterion before moving on. Prefer explicit over clever."
2. "Prioritize simplicity - keep the fewest clear lines that satisfy the criteria. Leave only required implementation and verification changes."
3. "Prioritize robustness - handle every edge case and failure mode that can affect the criteria, including cases beyond the happy path."

If N > 3, cycle back through the hints. If N == 2, use hints 1 and 2.

**Coordination block**: list all sibling slugs and their strategy hints; instruct each candidate to ignore siblings (worktree-isolated, no cross-talk). Set `scratchpad: false` to enforce blind execution.

### Step 1.2: Sequential dispatch via dmux-dispatch.sh

For K=1..N, call:
```bash
dmux-dispatch.sh \
  --project "{project-root}" \
  --slug "bon-{feature-slug}-{run-id}-{K}" \
  --agent "claude" \
  --brief "{project}/.dmux/tasks/bon-{feature-slug}-{run-id}-{K}.md" \
  --branch-from "{phase_branch_from}" \
  --permission-mode "acceptEdits"
```

Run sequentially with 2-second spacing (matches /dispatch convention to avoid tmux race conditions). After all dispatches, rebalance layout: `tmux select-layout -t {dmux-session} tiled`.

### Step 1.3: Poll loop using /collect status ladder

Every 30 seconds, for each candidate worktree, classify status using `/collect`'s ladder verbatim (`$STRATA_HOME/commands/collect.md:39-45, 180-184`):

| Worktree state | Inferred status |
|----------------|-----------------|
| `.task-result.md` exists | complete (read it) |
| `.task-blocked.md` exists | blocked |
| No protocol files; new commits vs branch_from | complete (synthesize minimal result) |
| No protocol files; uncommitted changes only | auto-commit then complete (Codex behavior fallback) |
| No protocol files; no commits; pane dead | orphan |
| No protocol files; no commits; pane alive | running |

Track per-candidate observed status + observed_at timestamp; persist to `result.json` `candidate_statuses` array (see State Schemas).

### Step 1.4: Terminal state aggregation

Continue polling until ALL candidates reach a terminal state (complete | blocked | orphan | timeout) OR wall-clock timeout fires.

**On wall-clock timeout (HARD ABORT)**:
1. Mark stragglers `terminal_state: "timeout"` in `candidate_statuses`.
2. Write `result.json` with `status: "timeout"` and `failure_reason: "wall_clock_timeout"`.
3. Surface to user (load /ask-better first):
   ```
   /best-of-n timed out after {timeout_min} min.
   Completed: {complete_count} / {N} candidates
   Stragglers: {list of slugs with state}
   Worktrees: {list of paths}

   Cleanup options:
   - Manually inspect via `cd {worktree_path}` and decide per-candidate
   - Run `git worktree remove --force {worktree_path}` to abandon
   - DO NOT continue selection - that violates Decision #1 (hard-abort guarantee)
   ```
4. Exit. Do NOT proceed to Phase 2.

**On orphan-majority or all-blocked**: load /ask-better, then AskUserQuestion failure-mode escalation. Options: re-dispatch failed candidates / accept partial set if 2+ complete / abort.

---

## Phase 2: Select Winner

### Step 2.1: Gauntlet (per-candidate evaluation by the grader)

For each candidate with `terminal_state: complete`, the grader evaluates the candidate diff against every rubric criterion. The grader is a 3-agent DeepSeek swarm (grader + breadth mix per `--swarm-mix`); Codex is retained as escalation on canonical triggers (Decision #5).

**Grader is the evaluation role; the concrete grader here is a DeepSeek swarm (grader + breadth) with Codex escalation.**

**Apply privacy preprocessing** before writing any prompt file (mirror `$STRATA_HOME/commands/codex-review.md:176-185`): scrub real name, private project names, private IPs from the diff text. Apply identically for DeepSeek and Codex paths.

**For each criterion Ci, for each candidate K — build per-slot prompt files and invoke the swarm in parallel:**

The swarm uses three evaluation lenses (Decision #15). Each lens prescribes a specific tool-workflow, not just a label prefix:

- **Slot 1 — strict lens**: grep the diff for criterion-specific patterns, read every referenced file to verify the claim is present. Focus: does the code literally implement what Ci requires?
- **Slot 2 — functional lens**: read the implementation's intent, then simulate the behavior in prose — trace through the change as if executing it. Focus: does it behave correctly under normal conditions?
- **Slot 3 — adversarial lens**: run the test suite (if present) via bash, probe edge-case inputs, look for paths that violate Ci even when the happy path passes. Focus: can you break it?

**Per-slot prompt template** at `/tmp/bon-{run-id}-gauntlet-{K}-C{i}-slot{s}.md`:

```
Goal: Evaluate the candidate diff against the stated rubric criterion and return the verdict with evidence.

Success means:
  - Complete the assigned lens workflow.
  - Return PASS when the diff satisfies the criterion, FAIL when the diff violates or omits it, and TIE when the evidence remains inconclusive.
  - Cite file:line evidence in a 1-2 sentence REASON.

Stop when: You have checked the diff and emitted the sentinel-bounded <final_verdicts> block.

Role: {strict|functional|adversarial} evaluator for a code review rubric.

CRITERION {i}: {Ci text — explicit, gradeable condition from the BoN Criteria block}

DIFF (candidate K={K}, branch {slug}, vs {branch_from}):
{output of `git diff branch_from..slug` — privacy-preprocessed}

YOUR TOOL WORKFLOW (required — complete these steps in order):
{strict:   1. grep the diff for patterns matching Ci. 2. Read referenced files. 3. Verify claim present.}
{functional: 1. Read the intent of the change. 2. Simulate behavior in prose. 3. Verify correct under normal conditions.}
{adversarial: 1. Run tests via bash (if present). 2. Probe edge-case inputs. 3. Find paths that violate Ci.}

OUTPUT FORMAT (sentinel-bounded; emit ONLY this block, nothing outside it):
<final_verdicts>
VERDICT: PASS|FAIL|TIE
REASON: <1-2 sentences citing file:line evidence>
</final_verdicts>
```

**Parallel invocation pattern** (spawn all 3 slots, capture per-PID exit codes):

```bash
# Resolve swarm_mix slots (default: flash,flash,pro)
IFS=',' read -ra MIX <<< "${swarm_mix}"

# For each criterion Ci, for each candidate K:
for s in 1 2 3; do
  model="${MIX[$((s-1))]}"  # flash or pro
  lens="${LENSES[$((s-1))]}"  # strict, functional, adversarial

  # Apply privacy preprocessing — write per-slot prompt file
  apply_privacy_preprocessing \
    --input /tmp/bon-{run-id}-gauntlet-{K}-C{i}-template.md \
    --output /tmp/bon-{run-id}-gauntlet-{K}-C{i}-slot${s}.md

  ds-${model} \
    --file /tmp/bon-{run-id}-gauntlet-{K}-C{i}-slot${s}.md \
    --timeout 600 \
    > /tmp/bon-{run-id}-gauntlet-{K}-C{i}-slot${s}.log 2>&1 &
  PIDS[$s]=$!
done

# Per-PID wait + exit-code capture (bash `wait $PID1 $PID2 $PID3` returns only last status)
for s in 1 2 3; do
  wait ${PIDS[$s]}
  RC[$s]=$?
  SIZE[$s]=$(wc -c < /tmp/bon-{run-id}-gauntlet-{K}-C{i}-slot${s}.log)
done
```

**Parse each slot's output** (lenient — only the LAST well-formed `<final_verdicts>...</final_verdicts>` block counts):
- If block found: extract `VERDICT: PASS|FAIL|TIE`.
- If block missing, multiple blocks, empty block, or RC != 0: slot verdict = INVALID; record `invalid_reason` as `parse_error_missing`, `parse_error_multiple`, `parse_error_empty`, or `exit_code_{N}` respectively.
- RC == 4 (auth failure): hard abort per Decision #6(i) — do not proceed to swarm verdict.
- RC == 3 (quota): slot verdict = INVALID with `invalid_reason: quota`.

**Swarm verdict rule (Decision #3 truth table)**. Let `(p, f, ti)` = `(count(PASS), count(FAIL), count(TIE+INVALID))`. Verdict: **PASS iff `p >= 2 AND p > f`. Otherwise FAIL.** Full 10-state enumeration:

| Tuple (p, f, ti) | Swarm verdict |
|------------------|---------------|
| (3, 0, 0) | PASS |
| (2, 1, 0) | PASS |
| (2, 0, 1) | PASS |
| (1, 2, 0) | FAIL |
| (1, 1, 1) | FAIL |
| (1, 0, 2) | FAIL |
| (0, 3, 0) | FAIL |
| (0, 2, 1) | FAIL |
| (0, 1, 2) | FAIL |
| (0, 0, 3) | FAIL (escalate per trigger (c) before applying — if Codex unavailable, this is the fallback) |

**Escalation check per Decision #5 triggers (b), (c), (e)** after swarm completes each criterion. Codex escalation auto-fires on:
- Trigger (c): `count(TIE+INVALID) >= 2` on any criterion → escalate that decision to Codex per Decision #16 fallback chain.
- Trigger (e): 2+ slots in this decision exited with RC=3 → escalate that decision.
- Trigger (b): N >= 4 AND `p == f` on any criterion → escalate.

Candidate qualifies (passes gauntlet) iff ALL criteria have PASS swarm verdict (or Codex-escalated PASS).

### Step 2.2: Routing

Count qualifying candidates:

- **0 PASS** (zero-pass escalation): load /ask-better, then AskUserQuestion:
  ```
  /best-of-n: 0 of {N} candidates passed the gauntlet.

  Per-candidate failures:
  {for each candidate: slug + list of FAIL criterion IDs + evidence}

  This signals either:
  (a) the criteria are wrong (too strict, or testing for the wrong thing)
  (b) the implementation strategy is wrong (none of the {N} approaches fit)

  Options:
  - Refine criteria and re-run
  - Accept best partial (manual review of all {N} candidates - tournament has no clear winner)
  - Abort and revisit spec
  ```

- **1 PASS**: that candidate is the winner. Skip to Step 2.4 (promote winner).

- **2+ PASS**: proceed to Step 2.3 (tournament).

### Step 2.3: Tournament (deterministic, single-elimination)

The grader (3-agent DeepSeek swarm, same mix as gauntlet) compares pairs of passing candidates across three lenses. Majority verdict selects the winner; mechanical tie-break resolves splits.

**Seeding**: candidates are seeded by their slug suffix K=1..N in order. Deterministic; no randomness.

**Byes for odd N**: bottom-seeded candidate gets a bye in round 1. For N=3: round 1 = (K=1 vs K=2), round 2 = (winner vs K=3). For N=5: round 1 = (1 vs 2) and (3 vs 4); round 2 = winners of those; bye for K=5 to round 2 final.

The tournament grader uses three evaluation lenses (Decision #15) on each pair. Lenses here probe selection-space (not failure-space like the gauntlet lenses):

- **Slot 1 — correctness lens**: run the test suite on each diff via bash; report which candidate has fewer test failures. Focus: which is more correct?
- **Slot 2 — simplicity lens**: run `wc -l` on changed files + apply complexity heuristics (e.g., cyclomatic path count, nesting depth). Focus: which is simpler?
- **Slot 3 — robustness lens**: read each diff for failure modes, error handling, and edge-case coverage. Focus: which handles more failure scenarios?

**Apply privacy preprocessing** before writing any prompt file. Apply identically for DeepSeek and Codex paths.

**Per-slot prompt template** at `/tmp/bon-{run-id}-tournament-round-{R}-pair-{A}-{B}-slot{s}.md`:

```
Goal: Compare the two candidate diffs against the spec criteria and select the stronger implementation for the assigned lens.

Success means:
  - Complete the assigned lens workflow for both candidates.
  - Return WINNER: A when candidate A is stronger, WINNER: B when candidate B is stronger, and WINNER: TIE when the evidence remains evenly balanced.
  - Cite specific evidence in a 1-2 sentence REASON.

Stop when: You have compared both diffs and emitted the sentinel-bounded <final_verdicts> block.

Role: {correctness|simplicity|robustness} evaluator comparing two implementations.

CRITERIA (from spec):
{verbatim BoN Criteria block}

CANDIDATE A (slug {A_slug}):
DIFF: {output of `git diff branch_from..A_slug` — privacy-preprocessed}

CANDIDATE B (slug {B_slug}):
DIFF: {output of `git diff branch_from..B_slug` — privacy-preprocessed}

YOUR TOOL WORKFLOW (required — complete these steps in order):
{correctness:  1. Run tests on each diff via bash. 2. Report test failure counts. 3. Pick winner by fewer failures.}
{simplicity:   1. Run `wc -l` on changed files. 2. Assess complexity heuristics. 3. Pick winner by lower complexity.}
{robustness:   1. Read each diff for failure modes and error handling. 2. Count unhandled edge cases. 3. Pick winner by better coverage.}

OUTPUT FORMAT (sentinel-bounded; emit ONLY this block):
<final_verdicts>
WINNER: A|B|TIE
REASON: <1-2 sentences citing specific evidence>
</final_verdicts>
```

**Parallel invocation pattern** (same structure as gauntlet):

```bash
IFS=',' read -ra MIX <<< "${swarm_mix}"
LENSES=("correctness" "simplicity" "robustness")

for s in 1 2 3; do
  model="${MIX[$((s-1))]}"
  lens="${LENSES[$((s-1))]}"

  apply_privacy_preprocessing \
    --input /tmp/bon-{run-id}-tournament-round-{R}-pair-{A}-{B}-template.md \
    --output /tmp/bon-{run-id}-tournament-round-{R}-pair-{A}-{B}-slot${s}.md

  ds-${model} \
    --file /tmp/bon-{run-id}-tournament-round-{R}-pair-{A}-{B}-slot${s}.md \
    --timeout 600 \
    > /tmp/bon-{run-id}-tournament-round-{R}-pair-{A}-{B}-slot${s}.log 2>&1 &
  PIDS[$s]=$!
done

for s in 1 2 3; do
  wait ${PIDS[$s]}
  RC[$s]=$?
  SIZE[$s]=$(wc -c < /tmp/bon-{run-id}-tournament-round-{R}-pair-{A}-{B}-slot${s}.log)
done
```

**Parse**: from each slot's log, extract the last well-formed `<final_verdicts>...</final_verdicts>` block and read `WINNER: A|B|TIE`. Missing/malformed block → slot verdict = INVALID.

**Tournament majority rule**: count `count_A`, `count_B`, `count_TIE_INVALID` across 3 slots.
- If `count_A >= 2`: A wins this pair.
- If `count_B >= 2`: B wins this pair.
- Otherwise: majority TIE/INVALID or split → **Mechanical tie-break**.
- Record `tournament_low_confidence: true` if any TIE/INVALID slot emerged but majority still held for A or B.

**Escalation check per Decision #5 trigger (d)**: if 2 consecutive pairs in this tournament hit mechanical tie-break → escalate the next pair to Codex per Decision #16.

**Mechanical tie-break** (used on split/TIE/INVALID majority, parse failure, or `--escalate-codex` forced):
1. For each candidate, run `git diff --shortstat {branch_from}..{slug}` and parse `(files-changed, insertions, deletions)`.
2. Sort candidates ascending by `(insertions + deletions)`, then ascending by `files-changed`, then ascending by slug suffix.
3. First in sorted order wins.

Record each round in `result.json` `tournament_decisions` array (per Decision #14 schema).

### Codex Escalation Path

Codex escalation auto-fires on any of the 5 canonical triggers from Decision #5 (a)-(e). When triggered, replace the swarm verdict for THAT decision only with a Codex evaluation. The swarm handles everything else.

**Triggers (verbatim from Decision #5):**
- **(a)** `--escalate-codex` flag passed
- **(b)** N >= 4 AND gauntlet has `p == f` on any criterion
- **(c)** swarm has `count(TIE+INVALID) >= 2` on any criterion
- **(d)** tournament has 2 consecutive pairs hit mechanical tie-break
- **(e)** 2+ slots in any single decision exit with code 3 (quota)

**Orchestrator-owned fallback chain (Decision #16)** — `strong` does NOT auto-cascade on quota; the orchestrator must implement:

```bash
# On any escalation trigger — replace swarm verdict for this decision:
strong \
  --file /tmp/bon-{run-id}-escalation-{context}.md \
  > /tmp/bon-{run-id}-escalation-{context}.log 2>&1
RC=$?

if [[ $RC -eq 3 ]]; then
  fast \
    --file /tmp/bon-{run-id}-escalation-{context}.md \
    > /tmp/bon-{run-id}-escalation-{context}.log 2>&1
  RC=$?
fi

if [[ $RC -eq 3 ]]; then
  breadth \
    --file /tmp/bon-{run-id}-escalation-{context}.md \
    > /tmp/bon-{run-id}-escalation-{context}.log 2>&1
  RC=$?
fi

if [[ $RC -eq 3 ]]; then
  # Chain exhausted — escalation itself unavailable
  # Surface to user via AskUserQuestion: escalation chain exhausted for {context}
  exit 1
fi

# Record actual model that produced the verdict in state.model_invoked
```

**Chain truncation**: the fallback ends at `breadth` — we are escalating FROM grader, so falling back to grader would be circular. The chain is: `strong → fast → breadth → surface to user`.

**Cost note**: each escalated decision costs Codex-tier or breadth-tier (no exact dollar figure per Decision #9). Log actual model invoked and exit code to `cost.json.escalations` on each run.

**Privacy preprocessing** applies identically to the escalation prompt file as to swarm prompts.

Record `codex_replaced_this_decision: true` in the relevant slot of `gauntlet_decisions` or `tournament_decisions`.

### Step 2.4: Promote winner

Set `winner_slug` and `winner_branch` in `result.json`. Compose merge command:
```
git merge bon-{feature-slug}-{run-id}-{winner-K} --no-edit
```

**Surface to user** (no auto-merge). Surface evaluator confidence per Decision #14: if the winning candidate had ANY slot with `invalid_reason != null` on ANY criterion (gauntlet), OR if `tournament_low_confidence: true` on any tournament round, the surface message MUST include a "Selection confidence: LOW" line with INVALID-slot context:

```
/best-of-n WINNER: {winner_slug}
Reason chain: {tournament_decisions summary or "1-PASS direct"}
Diff size: {files} files, {insertions} +, {deletions} -
Selection confidence: {HIGH | LOW — {N} INVALID slot(s), {M} low-confidence tournament round(s). E.g.: "LOW — 1 INVALID slot on K3/C3 (slot 3, grader, invalid_reason: timeout, log: /tmp/...)."}
{if LOW: See gauntlet_decisions in result.json for full slot record.}

Merge with:
  {merge_command}

Loser worktrees (kept for reference, clean up later via /collect):
{list of loser slugs}
```

---

## Phase 3: Wrap-up

### Step 3.1: Record cost

Per-run cost is the sum of: gauntlet (N_candidates × N_criteria × 3 agents × DeepSeek per-call) + tournament (`tournament_pairs = passing_candidates - 1` × 3 agents × DeepSeek per-call) + any Codex escalations (Codex-tier per escalated decision). DeepSeek per-call cost is sub-cent (CLAUDE.md) but exact basis is wrapper-version-dependent; log actual to `cost.json.measured_cost` on each run and refine future estimates from history (3+ runs). `tournament_pairs = passing_candidates - 1` (e.g., N=3 all-pass = 2 pairs; N=4 = 3 pairs; N=5 = 4 pairs).

Write `bon-runs/{run-id}/cost.json` per cost.json schema:
```json
{
  "run_id": "{run-id}",
  "wall_clock_seconds": <int>,
  "source": "measured",
  "candidate_count": {N},
  "measured_cost": {
    "ds_flash_calls": <int>,
    "ds_pro_calls": <int>,
    "codex_calls": <int>,
    "dollar_total": null,
    "source": "billed|estimated|unknown"
  },
  "escalations": {
    "gauntlet_codex_calls": <int>,
    "tournament_codex_calls": <int>
  }
}
```

`dollar_total` starts `null`; update from billing data if available. `source` for `measured_cost` is `"unknown"` on first run, `"billed"` if invoice data is available, `"estimated"` if derived from call counts × known per-call approximation. Only `"measured"` top-level entries feed the Phase 0 Step 0.4 history average.

### Step 3.2: Update spec progress

If `--from-spec`, update the active spec's `>> Current Step` to mark the BoN-tagged phase as in-progress-merge-pending (user runs the merge command themselves). Add a Learnings entry: "BoN run {run-id}: winner = {winner_slug}, gauntlet 0-pass = false, tournament rounds = N".

### Step 3.3: Cleanup suggestions

Output (do NOT execute):
```
Cleanup commands (run after merging winner):
  git worktree remove --force {project}/.dmux/worktrees/bon-{feature-slug}-{run-id}-{K} (for each loser K)
  git branch -D bon-{feature-slug}-{run-id}-{K} (for each loser K, after confirming unmerged is intentional)

Run `/collect` to inspect any blocked or orphan candidates.
```

---

## State Schemas

### dispatched.json

```json
{
  "run_id": "2026-04-26-002629-33304782",
  "feature_slug": "auth-fix",
  "n_candidates": 3,
  "branch_from": "main",
  "candidates": [
    {"slug": "bon-auth-fix-2026-04-26-002629-33304782-1", "agent": "claude", "strategy_hint": "Prioritize correctness - verify every criterion before moving on. Prefer explicit over clever."},
    {"slug": "bon-auth-fix-2026-04-26-002629-33304782-2", "agent": "claude", "strategy_hint": "Prioritize simplicity - fewest lines, clearest logic. Remove anything not required by criteria."},
    {"slug": "bon-auth-fix-2026-04-26-002629-33304782-3", "agent": "claude", "strategy_hint": "Prioritize robustness - handle every edge case and failure mode, even ones not in criteria."}
  ],
  "timeout_min": 30,
  "started_at": "2026-04-26T00:26:29Z",
  "status": "dispatched"
}
```

`status` valid values: `dispatched | running | complete | timeout | aborted`.

### result.json

```json
{
  "run_id": "2026-04-26-002629-33304782",
  "feature_slug": "auth-fix",
  "n_candidates": 3,
  "swarm_size": 3,
  "swarm_mix": "flash,flash,pro",
  "completed_count": 3,
  "candidate_statuses": [
    {
      "slug": "bon-auth-fix-2026-04-26-002629-33304782-1",
      "branch": "bon-auth-fix-2026-04-26-002629-33304782-1",
      "terminal_state": "complete",
      "observed_at": "2026-04-26T00:48:14Z",
      "pane_status": "alive",
      "commit_sha": "abc1234",
      "result_path": ".task-result.md",
      "blocker_path": null
    }
  ],
  "gauntlet_decisions": [
    {
      "candidate": "bon-auth-fix-2026-04-26-002629-33304782-1",
      "criterion": "C1",
      "slots": [
        {
          "slot_index": 1,
          "lens": "strict",
          "model_invoked": "grader",
          "fallback_model": null,
          "pid": 12345,
          "exit_code": 0,
          "log_path": "/tmp/bon-2026-04-26-002629-33304782-gauntlet-1-C1-slot1.log",
          "raw_output_size_bytes": 1234,
          "parsed_verdict": "PASS",
          "invalid_reason": null,
          "codex_replaced_this_decision": false
        },
        {
          "slot_index": 2,
          "lens": "functional",
          "model_invoked": "grader",
          "fallback_model": null,
          "pid": 12346,
          "exit_code": 0,
          "log_path": "/tmp/bon-2026-04-26-002629-33304782-gauntlet-1-C1-slot2.log",
          "raw_output_size_bytes": 980,
          "parsed_verdict": "PASS",
          "invalid_reason": null,
          "codex_replaced_this_decision": false
        },
        {
          "slot_index": 3,
          "lens": "adversarial",
          "model_invoked": "breadth",
          "fallback_model": null,
          "pid": 12347,
          "exit_code": 3,
          "log_path": "/tmp/bon-2026-04-26-002629-33304782-gauntlet-1-C1-slot3.log",
          "raw_output_size_bytes": 0,
          "parsed_verdict": "INVALID",
          "invalid_reason": "quota",
          "codex_replaced_this_decision": false
        }
      ],
      "swarm_verdict": "PASS",
      "codex_escalation": null
    }
  ],
  "tournament_decisions": [
    {
      "round": 1,
      "a_slug": "bon-auth-fix-2026-04-26-002629-33304782-2",
      "b_slug": "bon-auth-fix-2026-04-26-002629-33304782-3",
      "slots": [
        {
          "slot_index": 1,
          "lens": "correctness",
          "model_invoked": "grader",
          "fallback_model": null,
          "pid": 22345,
          "exit_code": 0,
          "log_path": "/tmp/bon-...-tournament-round-1-pair-2-3-slot1.log",
          "raw_output_size_bytes": 850,
          "parsed_verdict": "A",
          "invalid_reason": null,
          "codex_replaced_this_decision": false
        }
      ],
      "majority_winner": "A",
      "tournament_low_confidence": false,
      "used_mechanical_tie_break": false,
      "codex_escalation": null
    }
  ],
  "auto_escalated_to_codex": false,
  "escalation_reason": null,
  "tournament_low_confidence": false,
  "winner_slug": "bon-auth-fix-2026-04-26-002629-33304782-2",
  "winner_branch": "bon-auth-fix-2026-04-26-002629-33304782-2",
  "merge_command": "git merge bon-auth-fix-2026-04-26-002629-33304782-2 --no-edit",
  "completed_at": "2026-04-26T00:55:00Z",
  "status": "complete",
  "failure_reason": null
}
```

`terminal_state` valid values (mirrors /collect ladder): `complete | blocked | timeout | orphan | uncommitted-only`.
`status` valid values: `complete | timeout | zero_pass | aborted | tournament_failure_inconclusive`.
`codex_escalation` field: `null` if swarm decided, or `{triggered_by: "a"|"b"|"c"|"d"|"e", final_verdict: "PASS"|"FAIL"|"A"|"B"|"TIE", model: "strong"|"fast"|"breadth"}` if Codex replaced the swarm for this decision.

### cost.json

```json
{
  "run_id": "2026-04-26-002629-33304782",
  "wall_clock_seconds": 1485,
  "source": "measured",
  "candidate_count": 3,
  "measured_cost": {
    "ds_flash_calls": 6,
    "ds_pro_calls": 3,
    "codex_calls": 0,
    "dollar_total": null,
    "source": "unknown"
  },
  "escalations": {
    "gauntlet_codex_calls": 0,
    "tournament_codex_calls": 0
  }
}
```

`source` (top-level) valid values: `measured | estimated_from_history | unavailable`. Aggregation in Phase 0 Step 0.4 averages only `measured` entries.
`measured_cost.source` valid values: `billed | estimated | unknown`. `dollar_total` starts `null`; update from billing data if available.

---

## Failure Modes

| Failure | Recovery |
|---------|----------|
| Dispatch fails mid-wave (e.g., dmux-dispatch.sh aborts on slug regex violation) | Abort run; report which candidates were dispatched; clean up via /collect |
| Candidate hits dispatch wall-clock timeout | HARD ABORT per Decision #1 - no graceful continuation; mark straggler `timeout`; surface for user cleanup |
| DeepSeek slot exit code 3 (quota), 1 slot | Mark slot INVALID with `invalid_reason: quota`. Apply Decision #3 truth table. |
| DeepSeek slot exit code 3, 2+ slots in single decision | Trigger (e) fires → escalate to Codex per Decision #5 + Decision #16 fallback chain. |
| DeepSeek slot exit code 4 (auth failure) on any slot | Hard abort per Decision #6(i): `evaluator_unavailable`. Report missing DeepSeek API key. No Claude fallback. |
| Swarm has `count(TIE+INVALID) >= 2` on any criterion | Trigger (c) fires → escalate that decision to Codex. Decision #3 truth table is the fallback if Codex also unavailable (Decision #6). |
| Agentic timeout (default 600s) on a slot | Mark slot INVALID with `invalid_reason: timeout`. Apply Decision #3 truth table. |
| Parse failure (no `<final_verdicts>` block, or multiple, or empty) | Mark slot INVALID with `invalid_reason: parse_error_missing|parse_error_multiple|parse_error_empty`. Apply truth table. |
| Codex unavailable on escalation path | If Codex unavailable AND escalation triggered, fall back per Decision #16 chain: strong → fast → breadth. If chain exhausts → surface to user via AskUserQuestion. |
| All candidates `blocked` or majority `orphan` | Failure-mode escalation via /ask-better + AskUserQuestion (re-dispatch | accept partial | abort) |
| Tournament: 2 consecutive pairs hit mechanical tie-break | Trigger (d) fires → escalate next pair to Codex per Decision #16. |
| Mechanical tie-break has true tie (equal diff size + files + slug suffix) | Pick lower slug suffix (deterministic) |
| User aborts at any AskUserQuestion gate | Write `result.json` with `status: "aborted"`, `failure_reason: "user_abort_at_{phase}"`; preserve worktrees for inspection |

---

## DO NOT

- **DO NOT pick a "least bad" candidate when zero pass the gauntlet.** Zero-pass is a signal that criteria are wrong OR all candidates are wrong. Picking least-bad masks the signal.
- **DO NOT use Claude as the tournament judge.** Tournament uses DeepSeek swarm by default; Codex on escalation. Both DeepSeek and Codex are non-Claude; either preserves cross-model asymmetry. Claude wrote N/N candidates — same-family judging would be biased.
- **DO NOT use a single DeepSeek agent for gauntlet or tournament.** Always 3-agent swarm per decision (per `--swarm-mix`).
- **DO NOT trust the wrapper to auto-cascade on quota (rc=3).** The orchestrator owns the fallback chain (Decision #16): strong → fast → breadth → surface to user. Wrappers do not cascade themselves.
- **DO NOT bypass per-PID exit-code capture.** Bash's `wait $PID1 $PID2 $PID3` returns only the last exit status. Capture each PID separately: `wait ${PIDS[$s]}; RC[$s]=$?`.
- **DO NOT use sentinel-less parsing.** Only the last well-formed `<final_verdicts>...</final_verdicts>` block is the verdict source. Anything outside that block, or missing/multiple blocks, is INVALID — not a partially-valid verdict.
- **DO NOT exceed N=5 without `--force-n`.** Hard cap is cost discipline.
- **DO NOT skip the cost confirmation gate.** Phase 0 Step 0.5 is mandatory; the user must confirm before any dispatch.
- **DO NOT auto-merge the winner.** Phase 2 Step 2.4 surfaces the merge command; user runs it.
- **DO NOT continue past a wall-clock timeout.** Decision #1 is HARD ABORT - no "proceed with surviving candidates."
- **DO NOT loop a tournament round more than once.** If all swarm slots are INVALID/TIE-majority, go to mechanical tie-break. No infinite re-prompt loop.
- **DO NOT compose with /harness in v1.** A phase tagged both `Harness: yes` and `BoN: yes` is malformed - stop and report.
- **DO NOT add an `--allow-collision` bypass flag.** Collision detection is non-bypassable in v1; manual cleanup via /collect or git is the only escape.
- **DO NOT skip privacy preprocessing.** Every prompt (gauntlet + tournament, DeepSeek and Codex paths) gets the same scrub as `/codex-review` Step 2.
- **DO NOT skip /ask-better preflight.** Three sites: cost confirmation (Phase 0), failure-mode escalation (Phase 1.5), zero-pass escalation (Phase 2). Every AskUserQuestion call loads /ask-better first.
- **DO NOT silently fall back to inline implementation.** If prerequisites fail, abort and tell the user what's missing. Defeating the parallel-candidate purpose is not OK.

---

## Quality Self-Check

After /best-of-n completes, verify:

1. **Run-id format correct**: `{YYYY-MM-DD-HHMMSS}-{session-id}` with per-second resolution; appears identically in `dispatched.json`, `result.json`, all candidate slugs, all `/tmp/bon-*` prompt paths
2. **Mutex check ran**: Phase 0 Step 0.2 explicitly asserted no `Harness: yes + BoN: yes` collision on the current spec phase
3. **Preflight collision check ran**: Phase 0 Step 0.3 globbed worktrees AND branches matching `bon-{feature-slug}-*-*`; aborted if any unmerged found; NO bypass flag was used
4. **All N briefs written before any dispatch**: `.dmux/tasks/bon-{feature-slug}-{run-id}-{K}.md` for K=1..N exist on disk before the first dmux-dispatch.sh call
5. **Strategy hints round-robin assigned**: K=1 -> correctness, K=2 -> simplicity, K=3 -> robustness, K=4 -> correctness (cycle), etc.
6. **Status ladder cited**: Phase 1 Step 1.3 references `/collect`'s ladder by file:line (`$STRATA_HOME/commands/collect.md:39-45, 180-184`)
7. **Hard-abort on timeout**: Phase 1 Step 1.4 writes `result.json` with `status: "timeout"` and exits before Phase 2; no "continue with surviving candidates" path exists
8. **Gauntlet uses DeepSeek swarm by default**: Phase 2 Step 2.1 spawns 3 parallel grader/breadth agents per decision; per-PID exit-code capture; Codex retained for escalation only
9. **Zero-pass triggers AskUserQuestion**: Phase 2 Step 2.2 routing for 0 PASS loads /ask-better and surfaces escalation options; never picks "least bad"
10. **Tournament uses DeepSeek swarm by default**; Codex on escalation; majority winner wins; split/TIE/INVALID-majority → mechanical fallback
11. **State schemas complete**: `dispatched.json` has 8 fields; `result.json` includes `gauntlet_decisions` and `tournament_decisions` arrays; `cost.json` includes `measured_cost` and `escalations` objects
12. **/ask-better preflight ran at all 3 sites**: cost confirmation, failure-mode escalation, zero-pass escalation - grep skill execution log for "load /ask-better" >= 3 mentions
13. **Rubric vocab present**: `grep -c "rubric\|grader\|gradeable" best-of-n.md` >= 8
14. **Gauntlet uses DeepSeek swarm by default per `--swarm-mix flash,flash,pro`**: three lenses (strict/functional/adversarial), each prescribing a different tool-workflow
15. **Tournament uses DeepSeek swarm by default**: three lenses (correctness/simplicity/robustness), parallel invocation, majority-winner rule
16. **Swarm verdict rule enforced per Decision #3 truth table**: PASS iff p >= 2 AND p > f; INVALID precedence per Decision #6; all 10 tuples enumerated in Step 2.1
17. **Privacy preprocessing runs identically on DeepSeek and Codex paths**: every prompt file (gauntlet + tournament + escalation) gets the same scrub
18. **Per-PID exit codes captured separately**: `wait ${PIDS[$s]}; RC[$s]=$?` — not `wait $PID1 $PID2 $PID3` (which collapses to last exit code)
19. **State has per-slot observability (Decision #14)**: each gauntlet/tournament decision records 3 slots with `{slot_index, lens, model_invoked, fallback_model, pid, exit_code, log_path, raw_output_size_bytes, parsed_verdict, invalid_reason, codex_replaced_this_decision}`
