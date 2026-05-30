# workspace/

Your knowledge base lives here.

`bin/strata-init` populates this directory with a PARA-flavored seed tree on first run:

```
areas/         ongoing responsibilities you maintain over time
projects/      one directory per project entity (summary.md + items.json)
resources/     reusable references not tied to a project
daily/         session journals (YYYY-MM-DD-<slug>-<session-id>.json)
inbox/         unsorted captures
archives/      deprecated entities
state/         specs/ + handoffs/ — runtime state strata writes
```

Each directory ships with its own README explaining the pattern in more detail. Entity directories ship with a `summary.md` skeleton and an `items.json` example so you have a working template to copy from.

## Override

Set `$KB_DIR` in your shell rc to point this somewhere else (a separate repo, a synced directory, an existing knowledge base). `$STATE_DIR` and `$SPECS_DIR` default to subdirectories under `$KB_DIR` but can be overridden independently. See `bin/strata-init` and the `## Knowledge Persistence` section of `CLAUDE.md` for the contract.

## Source of truth

`summary.md` owns entity state. `items.json` holds structured details that do not fit prose (specific values, rules, gotchas). Skills like `/pickup`, `/end`, and `knowledge-lookup` read and write this tree. Over time it accumulates the persistent memory the orchestrator dispatches off.
