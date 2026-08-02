# Remediation defenses

Goal: Apply accepted era-audit findings without deleting current domain knowledge, incident-derived warnings, distinctive voice, or content no finding named.

Success means:

- Every finding is applied or rejected with evidence.
- A verifier that did not write the fix checks the new file against current ground truth.
- A separate collateral critic compares deletions with the requested findings.
- Empirical premise checks settle claims about tools, paths, APIs, and runtime behavior.
- The declared ship gate is met without requiring an empty finding supply.

Stop when: the chosen gate passes, every deferral has a reason, and the final diff contains no unrequested content loss.

## Freeze the repair input

Save the audited source hashes, findings, ground-truth snapshot, and current pre-edit files. Assign one writer per file. Let each writer read the whole file and every finding for it.

## Fixer

Give the fixer the exact findings, ground truth, house standards, and owned files. For each finding, require one of two evidence-bearing outcomes:

- `APPLIED`: name the concrete change and the finding it closes.
- `REJECTED`: quote the finding and show why its premise fails or why the proposed change would damage current content.

Preserve content outside the finding's scope. Move distinctive trigger phrases into the live activation surface when a retired trigger list is removed. Keep warnings until the protected failure mode is empirically gone.

## Independent verifier

Use a reviewer that did not write the fix. Prefer a different model family when the install provides one. Mark same-family review as degraded rather than calling it independent evidence.

Give the verifier the frozen findings, old and new files, current ground truth, and the fixer's applied/rejected ledger. Ask it to check:

- finding completeness;
- validity of every rejection;
- frontmatter and reference integrity;
- newly introduced stale facts or unfounded scalars;
- whether the file remains executable end to end;
- whether voice and domain knowledge still do their work.

The verifier reports only defects it can quote and defend. A clean result is valid.

## Collateral-only critic

Run a separate pass with one question: **What did this edit remove that no finding requested?**

Order the diff by deletion size. Compare every deletion with the finding list. Flag deleted domain knowledge, incident warnings, worked craft, lineage, distinctive trigger language, and voice. Restore confirmed collateral loss from the frozen original, verbatim when wording carries operational meaning.

Keep this critic separate from completeness review. Its narrow brief is the defense against a technically complete modernization becoming a pruning exercise.

## Premise verification

Treat reviewer claims as hypotheses. Re-run the named command, inspect the current source, parse the live config, or reproduce the failure before changing the file. Record evidence that can refute the reviewer as well as confirm it. Repair only confirmed defects; reject a review claim when the measurement contradicts it.

## Repair and recheck

Give a repairer only confirmed verifier or collateral defects. Change those defects and their immediate consequences. Recheck the same premise against the same authority. Preserve rejected findings and their rationale in the repair ledger.

## Ship gate

Choose the gate before editing from the named failure cost and repository policy. A suitable gate names which severities or contracts block shipment and how deferrals are recorded. Finding supply is inexhaustible, so zero findings is not a stopping rule by itself.

Report the gate, evidence, deferrals, degraded defenses, and any premise the review could not settle.
