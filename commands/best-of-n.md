---
name: best-of-n
description: "Run N agentic `strong`-lane candidates in parallel for a high-stakes implementation task, each in its own isolated git worktree with full read/write/exec access, all driven by one well-constructed prompt (no framing variation — divergence comes from agentic exploration + sampling). The orchestrator is the judge: it reads every candidate's diff and test output against the criteria with full project context, picks the winner with written reasoning, and breaks ties by smallest diff. The strong lane generates, the orchestrator judges — cross-lane by construction when `strong` is bound to a different model family than the orchestrator runs, and the judge holds the project context the sandboxed candidates lack. Tests are evidence, not a hard gate: a candidate's tests should pass, or there is a stated good reason they don't. MANDATORY auto-fire when an active spec phase is tagged `BoN: yes`. Triggers on: 'run best-of-n', 'try N parallel', 'generate N candidates and pick', 'parallel candidates', 'best of N implementation', 'spawn parallel implementations', 'compete N approaches', 'BoN this phase'. Also triggers when: active spec's current phase is tagged `BoN: yes` (mandatory, no skip); user faces multiple defensible designs / novel algorithms / irreversible migrations and wants competition; verify has failed 3 consecutive times on the same files (advisory). Pairs with /spec (upstream — `BoN: yes` phase tag is the trigger; mantra is 'best-of-N is downstream of better specs'), /harness (HARD MUTEX — a phase tagged both `Harness: yes` AND `BoN: yes` is malformed; fail loud). Manual: /best-of-n --from-spec [--n K] [--feature-slug SLUG] [--timeout-min N] [--lane strong|fast]."
tier: core
cost_hint: medium
parallelizable: false
when_to_use: "When entering a spec phase tagged `BoN: yes`, or when an implementation task has multiple credible designs and the cost of picking wrong is high."
---

# /best-of-n

Spawn N agentic `strong`-lane runs on the same task, each in its own git worktree with full access, then let the orchestrator judge the resulting diffs and pick the winner. The runs do real work — explore the repo, edit files, run tests, iterate. The orchestrator neither generates nor edits a candidate; it dispatches, collects, judges, and surfaces the winner for the user to apply.

Selection-bottleneck mantra: best-of-N is downstream of better specs.

## Conceptual Lineage

`/best-of-n` implements the outcome + rubric + grader + iteration pattern the managed-agents API later named; see https://platform.claude.com/docs/en/managed-agents/define-outcomes.

In that vocabulary: the `#### BoN Criteria` block in a spec phase is the *rubric* — a set of explicit, gradeable conditions. The *grader* is the orchestrator itself: it reads each candidate's diff and test output and grades it against that rubric directly, with the whole-project context the sandboxed candidates lacked. The N agentic candidates are *outcomes* generated in parallel; judging them down to one winner is the selection step. The cross-lane asymmetry — the `strong` lane generates, the orchestrator grades — is the load-bearing invariant: bind the `strong` lane to a different model family than the orchestrator runs and no model grades its own output.

## The whole loop

1. **Generate** — N agentic `strong`-lane runs, one shared well-constructed prompt, each in a throwaway worktree off the base branch, full read/write/exec. They implement the task in their own tree.
2. **Collect** — the orchestrator captures each worktree's `git diff` vs the base branch as a patch and runs the test suite in that worktree, saving the output. The orchestrator-run test result is authoritative over any self-report.
3. **Judge** — the orchestrator reads every candidate patch + its test output against the criteria, with the full project context the sandboxed runs lacked, and picks the winner with a written reason. Tests are weighed as evidence; smallest diff breaks ties.
4. **Apply** — surface the winning patch + reasoning. The user applies it.

## Why this shape

- **The strong lane generates, the orchestrator judges** → cross-lane by construction when `strong` is bound to a different model family than the orchestrator runs; no model grades its own output, and the judge holds the whole-project context each candidate's sandbox could not.
- **One prompt, N agentic runs** → real candidate divergence from exploration order + sampling. Non-agentic same-prompt generation produces near-duplicates; agentic does not — so no hand-seeded "correctness vs simplicity" framings are needed.
- **Every candidate on the strong lane** → quality over cheap-tier diversity. The prompt carries the diversity-free weight: construct it well once.
- **Tests are evidence, not a gate** → a candidate's tests should pass, or the judge sees a stated reason they don't and weighs it. The judge with full context decides; a green suite on a wrong-shaped change does not auto-win.

## Usage

```
/best-of-n --from-spec                  # read criteria from active spec phase
/best-of-n --from-spec --n 3            # override N (default 3, max 5 without --force-n)
/best-of-n --from-spec --feature-slug auth-fix
/best-of-n --from-spec --timeout-min 45
/best-of-n --from-spec --lane fast      # cheaper generator lane (default strong)
```

## Skip conditions

- **Skip if** the task is trivial (single file, < 30 lines) — parallel candidates add nothing.
- **Skip if** the working directory is not a git repo (candidates run in throwaway worktrees).
- **Skip if** no `#### BoN Criteria` block exists in the active spec phase AND no inline criteria can be derived.
- **Skip if** `/harness` is running on the same files (concurrent conflict).

## Prerequisites

1. Current directory is a git repo a throwaway worktree can branch from (`HEAD`, or the phase's `branch_from`).
2. The generator lane wrapper exists: `$STRATA_HOME/bin/strong` (or `bin/fast` with `--lane fast`), and its lane is bound to a concrete model in `config/model-map.toml`.
3. With `--from-spec`: an active spec at `$SPECS_DIR/` whose current phase is tagged `BoN: yes`.

If any fail, say what is missing and how to fix it. Surface the gap and stop; a silent fall back to a single inline implementation defeats the purpose.

## Auto-trigger, mutex

- **Spec-driven (MANDATORY)**: active spec's current phase has `BoN: yes` → invoke with `--from-spec` on entering that phase. When you believe BoN is genuinely unnecessary, ask the user for an explicit skip; decide it together, never unilaterally.
- **Explicit request**: "run best-of-n", "try N parallel", etc.
- **Verify-escalation (advisory)**: after 3 consecutive `/verify` failures on the same files, offer BoN.
- **Harness mutex**: a phase tagged BOTH `Harness: yes` AND `BoN: yes` is malformed. Stop and report; do not pick one unilaterally.

---

## Phase 0: Setup

1. **Parse args**: `--from-spec`, `--n N` (default 3, max 5 without `--force-n`; reject N < 2), `--feature-slug`, `--timeout-min` (default 30), `--lane` (default `strong`; `fast` allowed), `--force-n`.
2. **From-spec**: read the active spec, find the current phase via `>> Current Step`. Assert the Harness/BoN mutex (abort if both tagged). Read the phase's `#### BoN Criteria` block; if absent, fall back to the step acceptance criteria with an explicit warning that they may be coarse.
3. **Run-id**: `{YYYY-MM-DD-HHMMSS}-{session-suffix}`. State dir: `$STATE_DIR/bon-runs/{run-id}/`.
4. **Cost gate** (load `/ask-better` first): show N, the generator lane, the timeout, and the run-id; confirm before dispatch. N agentic strong-lane runs cost real tokens — the user confirms.

## Phase 1: Generate

1. **Identify the base branch** (`branch_from` from the phase, else `HEAD`).
2. **Write the shared prompt** once to `$STATE_DIR/bon-runs/{run-id}/prompt.md`. Construct it well — this single prompt carries all the candidates. Open with an outcome block and embed the task + criteria:

   ```
   Goal: Implement the task below in this working tree so every criterion holds.

   Success means:
     - Every criterion is satisfied by working code in this tree.
     - The relevant tests pass; if any test cannot pass, you leave a one-line note in your final message saying which and why.
     - Changes are minimal and focused — no unrelated edits.

   Stop when: the criteria hold and the tests you can run are green (or you have noted why one cannot pass).

   TASK: {spec phase/step body, or the inline task}

   CRITERIA (satisfy every one):
   {verbatim #### BoN Criteria block, or fallback acceptance criteria}

   Work directly in this directory: read what you need, edit files, run the tests yourself, iterate.
   ```

3. **Spawn N agents in parallel**, each in its own worktree with full access (capture per-PID exit codes). The lane wrapper acts on its working directory, so run it from inside the worktree via a subshell:

   ```bash
   RUN_DIR="$STATE_DIR/bon-runs/{run-id}"
   for k in $(seq 1 "$N"); do
     git worktree add -q --detach "$RUN_DIR/wt-$k" {branch_from}
     ( cd "$RUN_DIR/wt-$k" && "$STRATA_HOME/bin/$LANE" --file "$RUN_DIR/prompt.md" \
         --timeout {wave_timeout_s} ) > "$RUN_DIR/gen-$k.out" 2>&1 &
     PIDS[$k]=$!
   done
   for k in $(seq 1 "$N"); do wait "${PIDS[$k]}"; RC[$k]=$?; done
   ```

   `$LANE` is `strong` (default) or `fast`. Each agent edits only its own worktree, so parallel candidates never collide. Same prompt for all — divergence is the point.

   **Per-candidate quota fallback**: `RC == 3` (quota, or a wrapper-remapped per-run timeout) → re-run that candidate on the `fast` lane; record the lane that produced it. `RC == 4` (auth) → the lane backend is down; abort `generator_unavailable`.

4. **Collect** each candidate (capture diff, run tests, then drop the worktree):

   ```bash
   # diff against the base branch, not bare `git diff` — an agent with full access may have committed
   # its work, in which case `git diff` shows nothing; `git diff {branch_from}` captures it either way.
   ( cd "$RUN_DIR/wt-$k" && git add -A -N && git --no-pager diff {branch_from} ) > "$RUN_DIR/candidate-$k.patch"
   ( cd "$RUN_DIR/wt-$k" && {test_command} ) > "$RUN_DIR/test-$k.log" 2>&1
   git worktree remove --force "$RUN_DIR/wt-$k"
   ```

   `{test_command}` comes from the spec/phase or the obvious project default. If no suite is discoverable, skip and note "tests not run" — the judge will weigh that.

   Classify: **complete** (non-empty patch that applies clean), **empty** (no usable change → drop), **failed** (RC ≠ 0 after fallback). On wall-clock timeout, mark stragglers and proceed with whatever completed.

5. Proceed to judging with 2+ complete candidates. With exactly 1 complete, it wins by default — surface it and say so. With 0, report the failures and offer a re-run on a stronger prompt or higher timeout.

## Phase 2: Judge (the orchestrator)

Read, for each complete candidate: `candidate-$k.patch`, `test-$k.log`, and the agent's `gen-$k.out` final note. Judge against the `#### BoN Criteria` with full project context.

- **Criteria first**: a candidate wins by satisfying the criteria with the cleanest correct change, not by superficial diff size.
- **Tests as evidence**: green tests support a candidate; a failing test counts against it unless the candidate's note gives a good, verifiable reason (e.g. the test encodes a stale assumption the task changes). A passing suite is not sufficient when the change is wrong-shaped against the criteria.
- **Reason in writing**: name why the winner beats each rival — which criterion, which evidence, which file:line.
- **Tie-break (only when genuinely even on criteria + tests)**: smallest diff wins — fewest `insertions + deletions`, then fewest files changed, then lowest candidate index. Deterministic.

Write a short `result.md` in the run dir: winner, one-paragraph reasoning, per-candidate one-liners, tie-break if used.

## Phase 3: Apply + record

Surface to the user (no auto-apply):

```
/best-of-n WINNER: candidate-{k} (generated by {lane})
Why: {one-paragraph reasoning — criteria + test evidence}
Diff: {files} files, {ins}+ {del}-   |   Tests: {test-{k}.log summary or "not run"}

Apply with:
  git apply $STATE_DIR/bon-runs/{run-id}/candidate-{k}.patch
  (on conflict, retry: git apply --3way $STATE_DIR/bon-runs/{run-id}/candidate-{k}.patch)

Loser patches kept at $STATE_DIR/bon-runs/{run-id}/candidate-*.patch
```

If `--from-spec`, update the spec's `>> Current Step` to in-progress-apply-pending and add a one-line Learnings entry (run-id, winner, N). Note any leftover `wt-*` worktrees for the user to `git worktree remove` if a crash left one.

---

## DO NOT

- **DO NOT generate or edit a candidate yourself.** Candidates are agentic `strong`-lane runs in worktrees. The orchestrator dispatches, collects, judges.
- **DO NOT vary the prompt across candidates.** One well-constructed prompt for all N. Divergence comes from agentic exploration + sampling, not framing.
- **DO NOT mix generator lanes for diversity.** Every candidate runs on the same lane (default `strong`). `--lane fast` lowers the whole run's tier; it does not mix.
- **DO NOT treat a failing test as automatic disqualification, or a passing suite as automatic victory.** Tests are evidence the judge weighs with full context; a stated good reason can carry a red test, and a green suite does not save a wrong-shaped change.
- **DO NOT run agents in a shared directory.** Each gets its own throwaway worktree, so parallel edits never collide.
- **DO NOT use a sub-model swarm, tournament, or truth table for selection.** The judge is the orchestrator, once, with project context: the strongest judge with the most context is worth the orchestrator tokens.
- **DO NOT add an external grader, swarm, or scrub hop.** The diffs stay local — candidates produce them in their worktrees and the orchestrator reads them directly; there is no external evaluator hop to preprocess for.
- **DO NOT bypass per-PID exit-code capture.** `wait $P1 $P2` collapses to the last status; capture each: `wait ${PIDS[$k]}; RC[$k]=$?`.
- **DO NOT exceed N=5 without `--force-n`.** Cost discipline.
- **DO NOT skip the Phase 0 cost gate.** The user confirms before any agent fires.
- **DO NOT auto-apply the winner.** Surface `git apply {winner_patch}`; the user runs it.
- **DO NOT compose with /harness.** A phase tagged both is malformed — stop and report.
