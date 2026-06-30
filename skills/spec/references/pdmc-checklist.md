# Probe-Design Methodological Checklist (PDMC)

A methodological-review checklist for empirical probe and experiment designs.

Procedural review verifies that the design specifies what the implementation should do. Methodological review verifies that the design measures what the spec intends. PDMC is the methodological review checklist and must run as a separate pass after procedural review; it cannot be folded into procedural review.

Each item is a binary gate. A probe design reaches PROCEED only if every applicable item passes or a locked D-decision explicitly narrows the claim and accepts the residual risk.

1. **Comparator-vs-baseline distinction.**
   - What to check: Does the design explicitly distinguish the baseline subtracted in lift computation from the comparator paired in McNemar or other paired tests? If they are the same arm, does it say so? If different, are both named with exact IDs?
   - Example violation: "LB95(lift over baseline)" is paired with "McNemar vs best comparator" while no field says whether the subtracted baseline is `control`, `best_comparator`, or both.
   - Acceptable repair: Define `primary_lift = mean(candidate_correct - baseline_correct)` and `primary_mcnemar = McNemar(candidate_correct, baseline_correct)`, or explicitly define a different named comparator for both tests.

2. **Comparator label-blindness.**
   - What to check: Is the comparator's prediction stream computable without seeing eval labels or eval correctness bits?
   - Example violation: `best_comparator_correct[item] = max(correct_bit_for_arm[item])` over multiple arms.
   - Acceptable repair: Use one pre-locked arm such as `control` or a named fixed baseline, selected before eval labels are read; report OR/max unions only as `oracle_diagnostic`.

3. **Selection rule pre-registration.**
   - What to check: If the design uses "best of N" anywhere, is the selection rule registered before scoring and computable from non-eval data?
   - Example violation: The "best comparator" is whichever arm has the highest eval accuracy after all predictions are scored.
   - Acceptable repair: Register arm set, non-eval selector data, tie-break order, multiplicity correction, and selected-arm persistence before launch.

4. **Selection effect bound.**
   - What to check: For any selected-from-N rule, is the upper bound on selection-induced optimism calculated and below 0.05 at the registered N and selector sample size?
   - Example violation: Selecting one of nine comparators on a 30-row holdout with no relation stratification and no bound.
   - Acceptable repair: Increase and stratify the selector set until the bound is <= 0.05, require candidate superiority against every arm, or mark the selected comparator diagnostic-only.

5. **Bootstrap clustering.**
   - What to check: For every LB95/CI computation, does the bootstrap respect the data's clustering structure, such as fold, trial, pool, instruction family, or fixed corpus?
   - Example violation: Item-level bootstrap over concatenated observations from two eval splits when trials and folds are the independent units.
   - Acceptable repair: Use a hierarchical bootstrap over `(fold, trial)` or the probe-specific cluster unit, or require both item-level and clustered LB95 gates to clear.

6. **Per-fold AND aggregate gate definitions.**
   - What to check: If the design has folds, are per-fold and aggregate gates both specified, with explicit Bonferroni/Holm correction, weighting, bootstrap unit, McNemar unit, and minimum N per fold?
   - Example violation: Aggregate LB95 clears because large folds dominate while the smallest held-out relation fails.
   - Acceptable repair: Define per-fold alpha, aggregate alpha, fold weighting, cluster unit, and failure behavior; require every fold and the aggregate to pass unless the claim is explicitly narrowed.

7. **Sentinel discipline.**
   - What to check: Does the design specify which sentinels are written by scout, mock, diagnostic, and decision modes, and is this mechanically enforced before sentinel write?
   - Example violation: A scout directory contains both `.SCOUT_DONE` and `.DONE`.
   - Acceptable repair: Add a mode-gated sentinel writer and pre-launch sentinel validator; non-decision modes never write `.DONE` or `.PASS`.

8. **Decision-grade vs validation-grade explicit.**
   - What to check: Are scout, mock, and diagnostic run modes distinct from decision-grade in artifact schema, route fields, and sentinel behavior? Can a scout artifact be mistaken for a decision-grade input?
   - Example violation: A one-candidate scout writes `status="fail"`, `gate_a_pass=false`, and `route_on_fail="ROUTE-X"`.
   - Acceptable repair: Set `decision_grade=false`, `route_eligible=false`, `phase_pass=null` or `"pending"`, omit route fields, and record missing candidates/trials.

9. **Cross-probe input schema.**
   - What to check: For every prior-probe input, does the design specify consumed fields, source path, sha256, schema version, stale/retracted status, and route eligibility? Does launch hard-fail on missing or stale fields?
   - Example violation: A downstream probe consumes an upstream probe's `carry_forward` field without pinning the valid rerun artifact rather than the retracted full-run artifact.
   - Acceptable repair: Add a source registry validator that checks exact paths, hashes, decision fields, effective replicates, and probe-specific booleans before launch.

10. **Held-out family/lexicon contract.**
    - What to check: For every disjointness contract, are the sets, IDs, thresholds, audit fields, and hard-fail rules mechanically defined?
    - Example violation: "Held-out instruction-family + lexicon split" appears without instruction family IDs, template IDs, normalized token sets, or overlap thresholds.
    - Acceptable repair: Define disjointness by entity/value/triple/relation or instruction/template/operator/value/token sets; write per-trial audits and hard-fail forbidden overlap.

11. **Calibration-vs-eval overlap audit.**
    - What to check: Are overlap counts for every relevant key recorded in trial JSON, and are hard-fail versus soft-report categories explicit?
    - Example violation: Calibration permits correct-value overlap with the eval split, but trial JSON lacks `value_overlap_count` and `attribute_value_overlap_count`.
    - Acceptable repair: Record overlap by `entity_id`, `value_id`, option ID, full tuple, attribute-value pair, source statement, item ID, template ID, and lexical tokens; declare each key hard-fail or diagnostic.

12. **Trial JSON schema completeness.**
    - What to check: Does the schema include every promised audit field, training metadata field, gate input, prediction stream, correctness bit array, rate field, and source pin used by the design body?
    - Example violation: The design promises training-health evidence, but trial JSON has no `fitted`, final train loss, final validation loss, best epoch, stopped-early flag, or loss curve hash.
    - Acceptable repair: Cross-check the design body against the schema appendix; add strict validation and fail `.DONE` on omission.

13. **Pivot rule unambiguity.**
    - What to check: Does the routing decision map every possible gate tuple to exactly one outcome, including conflicting or partial states?
    - Example violation: `gate_a_pass=true` but `gate_b_pass=false` can be read as either ROUTE-A or ROUTE-B.
    - Acceptable repair: Define one composite route boolean, such as `probe_pass = gate_a_pass AND gate_b_pass AND gate_c_eligible`, and make unmatched tuples a verifier hard-fail.

14. **Power calculation per fold.**
    - What to check: For each fold/family's smallest N, does the design show 80% power at the registered alpha to detect the gate threshold or target effect?
    - Example violation: A fold with 41-61 eval rows per trial is decision-grade by assertion only.
    - Acceptable repair: Add `power_inputs.json` with N, alpha, threshold, target delta, pilot discordance rates, expected power, and a decision-grade/validation-grade flag per fold.

15. **Empirical adversarial check.**
    - What to check: Does the design include an "Adversarial Check" section that walks through observed or synthetic data under the proposed gates and confirms the verdict is sensible?
    - Example violation: A new comparator selector is introduced without showing how it behaves on an existing scout run or on null synthetic data.
    - Acceptable repair: Include a worked example with stored or synthetic correctness bits, expected gate outputs, sentinel state, route eligibility, and failure cases.
