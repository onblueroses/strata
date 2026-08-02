# workspace/

Runtime state strata writes while you work. `bin/strata-init` creates it on first run.

```
state/specs/      active implementation specs, one file per feature
state/handoffs/   session-to-session notes
```

A spec survives context compaction: after a compaction the agent reads the spec's
current step and its settled decisions instead of reconstructing them. A handoff briefs
a fresh session on a different next task.

Strata keeps no knowledge store of its own. For durable notes, use the memory your agent
platform ships; see `reference/knowledge-management.md`.

## Override

Set `$KB_DIR` in your shell rc to put this somewhere else, such as a separate repo or a
synced directory. `$STATE_DIR` and `$SPECS_DIR` default to subdirectories under `$KB_DIR`
and can each be overridden independently. `bin/strata-init` reads the same variables.
