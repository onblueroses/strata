---
description: |
  Adversarial generator-evaluator loop for high-stakes implementation tasks.
  Generators produce candidates; the strong-lane evaluator grades against a
  frozen rubric and iterates until aggregate PASS or convergence escalation.
  Cross-model asymmetry (bind a different model family to `strong` than the
  generator uses) breaks same-model bias by construction.

  Auto-trigger: when an active spec's current phase has `Harness: yes` and
  implementation of that phase is about to begin. Also invoke when /verify
  Deep tier finds criteria failures on a second pass.

  Manual: /harness --from-spec | /harness <task>
---

# /harness

Thin redirect to the canonical skill body at `$STRATA_HOME/skills/harness/SKILL.md`. Load that file and follow the protocol it defines.

## Invocation modes

- `/harness --from-spec` — read the current spec's `>> Current Step` phase, run the harness loop against its `#### Harness Criteria`. Persist run state under `$STATE_DIR/harness/<run-id>/`.
- `/harness <task>` — manual mode for ad-hoc adversarial loops; you supply the task brief and the C1/C2/... criteria inline.

## Runtime contract (read before running)

Strata's harness dispatches both evaluator stages through `$STRATA_HOME/bin/strong --file PROMPT`. The wrappers accept `--file`, `--system`, and `--timeout`; older `--effort`, `--cache`, `--max-tokens`, and `--raw` flags are accepted as no-ops for skill bodies that still set them. Before starting, confirm `config/model-map.toml` binds `strong` to a different model family than your generator model; that asymmetry is the load-bearing mechanism. When the lane is unbound, stop and bind it per `CONFIG.md`, and label an accepted same-family fallback as degraded.

For the full loop semantics, framings rotation, convergence detectors, and termination rules, read `$STRATA_HOME/skills/harness/SKILL.md` start-to-finish.
