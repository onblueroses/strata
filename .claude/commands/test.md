---
description: |
  Fast inner-loop test run for the strata repo: the whole suite, or one subsystem.
  Manual: invoke while iterating on Python code, before the full /check gate.
---

# Test

Goal: Run the pytest suite (or a scoped slice) and report pass/fail.
Success means:
  - The chosen pytest invocation runs and its summary line is reported.

Stop when: pytest exits and the pass/fail count is reported.

The whole suite runs in well under a second, so default to it:

```
python3 -m pytest -q
```

Scope to one subsystem for a tighter loop while iterating there:

```
python3 -m pytest memory/tests_deep -q     # retrieval engine, digest, reconcile
python3 -m pytest tests -q                  # agent prompt-file, cost rollup, unify, digest
python3 -m pytest memory/tests_deep/test_wiring_hooks.py -q   # memory hook wiring
```

Add `-k <expr>` to select by test name, or a file path to run one module.
