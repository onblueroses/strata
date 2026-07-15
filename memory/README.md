# Memory subsystem

`memory` is a daemonless retrieval subsystem for Markdown memory cards and
project or area summaries. BM25 is the baseline and has no model dependency.
An explicitly configured `model2vec` static embedding model adds a second
ranking that is fused with BM25 through reciprocal-rank fusion.

The subsystem is code-only. Runtime cards, vector caches, access logs, locks,
session state, backups, and telemetry stay under `STATE_DIR`; the repository
ships only neutral examples and synthetic evaluation fixtures.

## Configuration

Every entry point resolves the same environment-backed configuration in
`memory.config`.

| Variable | Default | Purpose |
|---|---|---|
| `STRATA_HOME` | `$HOME/.strata` | Installed Strata root |
| `KB_DIR` | `$STRATA_HOME/workspace` | User-authored knowledge root |
| `STATE_DIR` | `$KB_DIR/state` | Mutable runtime root |
| `STRATA_MEMORY_EMBEDDING_MODEL` | unset | Optional local or cached embedding model |
| `STRATA_MEMORY_DIGEST` | `1` | Enables digest rendering |
| `STRATA_TELEMETRY` | unset | Set to `1` to emit bounded JSONL events |

The card store is `STATE_DIR/memory/cards`. Vector and ID caches use
`STATE_DIR/memory/cache`; access-log state and locks use
`STATE_DIR/memory/session-state`; backups use `STATE_DIR/memory/backups`.
Project and area summaries are read only from `KB_DIR/projects/*/summary.md`
and `KB_DIR/areas/*/summary.md`. Telemetry is opt-in and lives under
`STATE_DIR/telemetry`.

An unset model, a `<PICK_EMBEDDING_MODEL>` placeholder, or an unavailable
`model2vec` installation leaves retrieval in BM25 mode. No model is downloaded
unless both the dependency and an explicit model value are present.

## Usage

Copy or adapt the neutral cards in `memory/examples/cards` into the configured
card store. The accepted frontmatter is documented in `CARD-SCHEMA.md`.

```bash
python3 -m memory.recall --no-embeddings "bounded queue overload"
python3 -m memory.digest --text
python3 -m memory.digest --section table --text
python3 -m memory.regen_memory_index --diff
python3 -m memory.eval.run --report
python3 -m memory.eval.probe_runner --dry-run --mode bm25
```

`recall` returns a logical ID plus a root label and root-relative path. It never
returns a host-absolute path. `regen_memory_index` writes a proposal by default;
`--apply` first copies the live preimage into the configured backup directory.

## Dependencies

BM25 uses the Python standard library. Fused retrieval additionally requires
`numpy` and `model2vec`. Tests use `pytest`; repository gates also use Ruff and
Pyright.
