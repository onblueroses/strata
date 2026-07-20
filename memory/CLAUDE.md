# memory/ conventions

Daemonless retrieval over Markdown cards and entity summaries. BM25 is the
baseline and carries no model dependency; an explicitly configured `model2vec`
embedding adds a second ranking fused through reciprocal-rank fusion. Subsystem
overview and entry points: `README.md`; card frontmatter: `CARD-SCHEMA.md`.

## Local invariants

- **Code-only tree.** Runtime cards, vector caches, access logs, locks, session
  state, backups, and telemetry live under `$STATE_DIR/memory/`, never the
  tracked repo. The repo ships only synthetic fixtures and the neutral examples
  under `examples/`. Keep it that way; tests assert it.
- **Config, not hardcoded paths.** Every entry point resolves `STRATA_HOME` /
  `KB_DIR` / `STATE_DIR` through `memory.config`. Point new code at the config
  object; `tests_deep/conftest.py` isolates these via an autouse fixture, so
  hardcoded paths break under test.
- **Degrade to BM25.** An unset or `<PICK_...>` embedding model, or a missing
  `model2vec` install, leaves retrieval in BM25 mode. No model downloads unless
  both the dependency and an explicit model value are present.
- **Portable IDs.** `recall` returns a logical ID plus a root label and
  root-relative path, never a host-absolute path.
- **Index safety.** `regen_memory_index` writes a proposal by default; `--apply`
  copies the live preimage into the backup dir first.

## Local checks

```
python3 -m pytest memory/tests_deep -q                    # 70 tests
python3 -m memory.eval.probe_runner --dry-run --mode bm25  # retrieval probes
```
