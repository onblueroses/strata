---
description: |
  Run the full local gate for the strata repo: ruff, pyright, and pytest, in that order.
  Manual: invoke before committing a code change, or to confirm the tree is green.
---

# Check

Goal: Report whether the working tree passes strata's three local gates.
Success means:
  - `ruff check .` reports no issues.
  - `pyright` reports zero errors over the repo's own source.
  - `python3 -m pytest -q` passes the whole suite.

Stop when: all three gates have run and a single green/red verdict is reported.

Run each gate and read its output:

```
ruff check .
pyright memory telemetry hooks tests bin
python3 -m pytest -q
```

Notes:

- The pyright dir list is deliberate. A bare `pyright` picks up `include: []`
  from `pyrightconfig.json` and walks the gitignored `.local/venv`, drowning
  the real signal in third-party errors. Scope it to the source dirs instead.
- `ruff.toml` and `pyrightconfig.json` exclude `bin/lib/agent.py` and the
  vendored skill packs on purpose; the gates skip them.
- Fix findings before committing. `ruff check --fix .` applies the safe
  autofixes; re-run the gate afterward.
