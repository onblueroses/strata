<!-- keywords: load-bearing, iterate to flawless, cross-model review, codex review, four passes, spec-lawyer, ship gate, net findings to zero, adversarial review, regression test, fix-up commit, cross-check claims, verify claims, primary sources, current versions, dependency version, adversarial lenses, parallel review, frozen version, stopping rule, pre-check gate -->
# Load-Bearing Iteration

How to drive a load-bearing artifact to flawless: the four-pass cross-model review loop, the cross-check gate, the version-currency rule, and the parallel-lens discipline. The core `CLAUDE.md` keeps every TRIGGER for these rules; this doc holds the elaboration and worked patterns.

**"Load-bearing"** = downstream phases or external users depend on this, so a silent bug here propagates: a spec phase, a code commit that lands a contract, a design decision, a build-system choice, a schema, an FFI seam, a dependency version pin, an evaluation harness, a numerical result later work rests on.

Throughout, "cross-model review" means review by a model that is not the one that produced the artifact: the bare `codex` CLI where strata wraps it (`/codex-review`, `/verify` Full/Deep, `/review`, the `gate-codex-*` hooks), the `breadth` lane, or any other different-provider model. Same-model self-review is near-zero signal; the asymmetry is the gate. Lane wrappers (`strong`, `fast`, `grader`, `breadth`) live at `$STRATA_HOME/bin/`; rebind the model behind each lane in `config/model-map.toml` as models churn.

## Quick Nav

| Need | Section |
|------|---------|
| The 4 review passes, in order | The Four-Pass Loop |
| When to fix-up vs amend | Apply Findings; Fix-Up After Commit |
| Verify a claim before building on it | Cross-Check Load-Bearing Claims |
| Stop trusting a model's version number | Current Versions, Never Training-Cutoff |
| What "shipped" actually means | Net Findings to Zero |
| When extra rounds stop paying | Stopping Rule: Finding-Character, Not Round Count |
| Cheap checks before the loop | Pre-Check Gate Before the Loop |
| Running multiple review lenses | Adversarial Lenses Run in Parallel |

## The Four-Pass Loop

<details>
<summary>The Four-Pass Loop</summary>

For any load-bearing artifact, the canonical iteration loop offers FOUR cross-model passes. Select by stakes and artifact type rather than running all four every time, and stop by finding-character not round count (see Stopping Rule). The framing passes (1, 3, 4) are independent, so run them as one parallel panel on a frozen draft (see Adversarial Lenses), not a sequential rotation. Declare "shipped" only when net actionable findings reach zero (or are explicitly deferred with a Decisions-table rationale).

1. **Pre-implementation: specification-lawyer review on the design draft.** Write the design as markdown at `/tmp/spec-draft-<phase>-<step>.md`. Run `/codex-review --plan` (specification-lawyer-plan framing), or dispatch the `strong` lane directly with the same framing. Apply BLOCKING + IMPORTANT findings before writing code. Iterate until the reviewer returns PROCEED. For genuinely mechanical phases with zero design freedom, this pass can be skipped, but document the skip rationale in the spec rather than omitting it. (Worked pattern: three spec-lawyer iterations on one multi-phase build caught a missing loader path, an integer-width mismatch, and a test-coverage gap before any code landed.)

2. **Post-implementation: `codex review --uncommitted` on the diff.** The canonical diff gate; runs against the staged + unstaged diff via `/verify` Full/Deep or `/review`. Apply CRITICAL + HIGH + IMPORTANT before commit. Lower-severity findings that aren't trivially fixable can be deferred with a Decisions row.

3. **Deep adversarial 8-criterion review** (when stakes warrant: "is this flawless?"). Write a custom prompt that explicitly asks the reviewer to **run actual commands per criterion** (run the test suite, inspect files, build adversarial repros, fresh-environment smoke test), not just read files. Demand ≥3 AGREE notes (anti-bias) + severity-tagged findings + a per-criterion PASS/FAIL/REVISIONS_NEEDED verdict + final VERDICT. Pipe the prompt via stdin or use `"$(cat /tmp/prompt.md)"` to avoid angle-bracket shell escaping.

4. **Forward-looking lens: simulate future phases against the current artifact.** For each downstream phase that will build on this commit, surface (a) what that phase needs, (b) what the artifact provides, (c) the exact delta required, (d) whether the change is FFI-/contract-breaking. Findings that are "Phase N needs Y" are scope-of-future-phase (file them as a note); findings that are "Phase N can't extend X without breaking the contract" are scope-of-current-phase (fix now).

</details>

## Apply Findings; Fix-Up After Commit

<details>
<summary>Apply Findings; Fix-Up After Commit</summary>

Apply findings before commit. If pass 3 or 4 surfaces a real issue post-commit, do not amend: create a new `fix(...)` commit that includes the fix AND a regression test that fails on the pre-fix state. The reviewer's adversarial-repro pattern (e.g. "corrupt the cache file and verify the rebuild triggers") is the right test shape; it documents what would have been silently broken. (A cache-bypass fix and an encoder-canonicalization fix both shipped this way.)

</details>

## Cross-Check Load-Bearing Claims

<details>
<summary>Cross-Check Load-Bearing Claims</summary>

Before acting on anything subsequent work will rest on — a load-bearing assumption, a numerical result from an experiment, a metric from a long training/eval run, a benchmark summary, a paper's claimed finding treated as ground truth, a recon brief's "X is implemented / Y is missing" claim, or any output of a multi-hour compute job — dispatch a cross-model pass (the `fast` lane for quick sanity, the `strong` lane for load-bearing) that re-derives or independently verifies the claim against primary sources: the raw logs, the actual code, the actual data, the cited line numbers.

Same-model self-review is near-zero signal; cross-model verification is the gate. The longer the compute that produced a number, the more expensive a silent error becomes; verify before propagating. A single source of one model's reasoning is never enough to load-bear; add a cross-model verifier (the `strong` lane, or the `breadth` lane for a second angle) before downstream decisions branch off the claim. If verification disagrees with the original, trust the verifier's primary-source trace over the original's narrative.

</details>

## Current Versions, Never Training-Cutoff

<details>
<summary>Current Versions, Never Training-Cutoff</summary>

A cross-model reviewer (and any LLM) is anchored on its training data. When it says "use library X version `<PICK_OLD_VERSION>`", run `cargo search X` / `pip index versions X` / equivalent first. (Worked pattern: a review recommended pinning a Rust↔Python binding crate to a several-majors-old version; the actual latest stable was far ahead, and going to the real latest saved a future migration round.) This applies to every dependency pin, language version, model version, API version, and binary tool version.

</details>

## Net Findings to Zero

<details>
<summary>Net Findings to Zero</summary>

"Shipped" means: every CRITICAL + HIGH is fixed, every IMPORTANT is either fixed or has a Decisions-table rationale for deferral, MEDIUM/low findings are addressed if trivially fixable. Forward-looking findings categorized as scope-of-future-phase are filed for the relevant phase. The Decisions table absorbs anything explicitly deferred. There is no other ship gate.

</details>

## Stopping Rule: Finding-Character, Not Round Count

<details>
<summary>Stopping Rule: Finding-Character, Not Round Count</summary>

Refined by iteration-loop forensics across many heavy sessions. Rounds 1-3 are the universal high-yield floor. Past round 4 the marginal yield splits by ARTIFACT TYPE, not round number:

- **Intrinsically complex correctness code** (security state machines, FFI contracts, codec-keyed logic): rounds keep paying through 6-11 because each fix legitimately exposes the next layer. Run convergence-not-count here (one security state-machine review earned 8 rounds, an FFI-contract plan earned 11, each closing real holes).
- **Specs/plans and generators without ground truth**: rounds 5+ stop surfacing pre-existing defects and start regressing or cycling. Hard-cap at 3-4; if not ≤1 BLOCKING by round 4, the defect is source ambiguity in the artifact, not review coverage, so surface the ambiguous decisions to the human instead of mining the same text again. (One spec run reached 9 rounds and applied dozens of findings with zero rejections, the signature of unresolved drafting; another cycled the same API drift for 15+ rounds.)

The mechanical knee, stop now regardless of count: a **fix-induced regression** (a round re-breaks a prior finding) or a **verbatim-repeat finding** (a round reproduces the prior round's finding unchanged). Both are the real budget, replacing any fixed round cap. On a regression, re-derive the section from scratch rather than patch (a holistic re-pass converges in one shot where targeted patches spiral).

Batch every finding of a round into one fix pass, then re-dispatch once. Relaunching before all blockers are applied just re-finds the identical set; a sub-10-minute relaunch is the fingerprint of an incomplete fix set, and per-fix confirm cycles (nine sequential confirming reviews in one observed phase) waste recoverable time that batching reclaims.

</details>

## Pre-Check Gate Before the Loop

<details>
<summary>Pre-Check Gate Before the Loop</summary>

The cheapest reviewer is a deterministic check, and a defect caught before round 1 costs zero rounds. Before opening a review loop, run a step-0 gate (these ADD coverage while saving rounds and spend; promote them above any cut):

- **Satisfiability + design-contract check**: for each binary acceptance criterion, ask whether it is satisfiable by pure implementation or needs an architectural primitive; probe the specific gating design-doc sections. (Would have caught a crypto-needing criterion surfaced only at harness round 7, and a contract violation that invalidated half a scope at spec round 5.)
- **Statistical-validity framing** for empirical specs (free-parameter headline, denominator adequacy) BEFORE any GPU spend. (Would have caught a tautological headline found only after real GPU spend.)
- **Local + pre-GPU preflight** baked into launch templates: import-all-modules, list dependency dirs, op-coverage test (e.g. ONNX), model-availability and runtime-API-surface inspection. (Would have prevented wasted box launches, a bad CUDA image, and GPU crash spend.)

Closing the loop with runnable checks (the harness Stage A + tests, a satisfiability pre-check, an op-coverage test) retires whole LLM review rounds for free.

</details>

## Adversarial Lenses Run in Parallel

<details>
<summary>Adversarial Lenses Run in Parallel</summary>

When applying multiple review lenses (security-auditor, specification-lawyer, failure-mode-analyst, contrarian, etc.) to an artifact, dispatch all lenses against the *same frozen version* in parallel and merge findings into one rework brief. Never rotate lenses across iterations on a moving target: a fix for lens A often becomes a violation for lens B, and sequential rotation creates oscillation. One version in, N lens reports out, one merged brief, one next version. If none of the preconfigured lens flags fit the artifact, write a custom cross-model prompt for the lens you actually need rather than forcing a poor match; the preset list is a default, not a cage.

</details>
