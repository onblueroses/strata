# Telemetry — opt-in runtime instrumentation

A single opt-in place where strata self-telemetry flows together, so later sessions can analyze
"what repeatedly goes wrong / is slow / is unused" and improve the setup. Off by default; when
enabled, hooks and lane wrappers append enveloped events to one live sink, and read-time tools
fold and price that sink on demand.

## Opt-in

Telemetry is OFF unless the environment sets `STRATA_TELEMETRY=1`.

- **Emitters no-op when unset.** `telemetry-emit.sh` and the lane-wrapper EXIT hooks both check
  `STRATA_TELEMETRY` first and exit silently when it is absent, so the default install collects
  nothing and adds zero hot-path cost.
- **Wiring lives in setup/config docs, not in default `settings.json`.** Shipping the variable
  enabled would make collection the default; an operator turns it on deliberately (export it in
  the shell profile or the harness env).
- **Readers run on demand and need no gate.** `unify.py`, `digest.py`, and `cost_rollup.py` are
  read-time tools; they never assume telemetry is enabled. An empty or missing sink yields an empty
  stream, digest, or ledger rather than an error.

## Runtime paths (the contract)

All telemetry resolves the same four anchors, with env override then a deterministic fallback.

Shell:
```sh
STRATA_HOME="${STRATA_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"  # parent of the script dir
state_dir="${STATE_DIR:-${KB_DIR:-$STRATA_HOME/workspace}/state}"
tel_dir="${STRATA_TELEMETRY_DIR:-$state_dir/telemetry}"
```

Python:
```python
STRATA_HOME = os.environ.get("STRATA_HOME") or <parent of this script's dir>
KB_DIR      = os.environ.get("KB_DIR")      or f"{STRATA_HOME}/workspace"
STATE_DIR   = os.environ.get("STATE_DIR")   or f"{KB_DIR}/state"
TEL_DIR     = os.environ.get("STRATA_TELEMETRY_DIR") or f"{STATE_DIR}/telemetry"
```

- **Live event sink**: `$TEL_DIR/events.jsonl` (enveloped JSONL). The per-session token rollup,
  when an install produces one, sits beside it at `$TEL_DIR/session-metrics.jsonl`.
- **Runtime data stays under `$STATE_DIR`**, never the tracked install tree. The scripts here ship;
  the live event/metric data is gitignored.
- **Tracked template**: the rate table `$STRATA_HOME/telemetry/model_rates.json` ships alongside the
  scripts (placeholders only, see below).

## Event envelope

Every event is one JSON object on its own line, with a fixed four-key envelope plus kind-specific
fields:
```json
{"ts":"ISO8601","sid":"<session>","kind":"<event-kind>","source":"live", "...kind-fields":"..."}
```

The envelope keys (`ts`, `sid`, `kind`, `source`) can never be overridden by a payload key: under
`jq` the emitter merges the payload first and the envelope second; on the `jq`-less fallback it
splices payload fields first and the envelope last, so a duplicate key resolves to the envelope
value either way.

## Tools

### `telemetry-emit.sh <kind> <sid> [json_payload]`

Fail-open append helper any hook can call. `json_payload` is a JSON object string of extra fields
(default `{}`). Opt-in gated; **any error exits 0 with no output**, so it never blocks a hook or
changes a caller's exit code. It resolves `$TEL_DIR` per the contract, creates it on demand, and
appends one enveloped row. Uses `jq` when present, with a `jq`-less string-splice fallback.

When the sink append itself fails (unwritable file, full disk), it records a `telemetry_error` row
(`failed_kind` = the kind that could not be written) on `$TEL_DIR/telemetry-errors.jsonl` rather than
swallowing the drop silently, so a failing instrument stays observable; that side-stream write is
itself fail-open. `unify.py` folds the side-stream back in.

### `unify.py`

Read-time merger: folds `$TEL_DIR/events.jsonl` and the `$TEL_DIR/telemetry-errors.jsonl` side-stream
(plus any legacy enveloped JSONL streams the install configures under `$STATE_DIR`) into one
time-sorted stream on the common envelope, so analysis reads one surface. Non-invasive (legacy sources keep their own logs), idempotent, and best-effort: it
skips a malformed or partial line and drops an unreadable stream rather than aborting the merge.

- `python3 unify.py` writes the normalized stream to stdout.
- `--counts` adds a kind/source tally to stderr.
- `--out PATH` writes to a file instead, guarded by `out_path_is_safe`.

**`out_path_is_safe` guard.** The unified stream can carry raw event payload text, and an install
tree may push to a remote, so `--out` refuses to leak that text into version control. The guard:
expands the path; refuses a symlinked destination outright; resolves the realpath before asking git
(a lexical check is bypassable via an ignored symlink pointing at a tracked file); refuses a
nonexistent output parent; scrubs `GIT_*` environment overrides before invoking git; asks
`git -C <parent> rev-parse --show-toplevel`; treats a destination **outside any git metadata
ancestor** as safe; inside a work tree, allows it only when `git check-ignore` reports the target
gitignored, and refuses other paths. It **fails closed**: any git error or indeterminate status
inside a metadata ancestor refuses the write and falls back to stdout.

### `digest.py`

Read-only public telemetry synthesis. It invokes `unify.py` directly and renders router precision
(worst/best-served docs, never-surfaced docs, router score calibration, and zero-routes), delegation
summary, friction/rework signals, and serial-wait diagnostics. Inputs resolve under `$STATE_DIR`
and `$STRATA_HOME` through the shared runtime path contract; the router catalog and lexical cache
live under `$STRATA_HOME/reference/.router-eval/`.

- `python3 digest.py` writes the Markdown digest to stdout; `--json` emits the same findings as JSON.
- `--since DAYS` limits unified events to a recent window.
- `--out PATH` refuses a git-tracked destination and falls back to stdout.

A SessionEnd distiller is optional and is not shipped. The digest reads `unify.py` directly and does
not depend on a distilled metrics stream.

### `rotate_telemetry.sh`

Size rotation for the unbounded sinks. `events.jsonl` (many appends per session) and
`session-metrics.jsonl` (one row per session) grow forever otherwise. When a file crosses its byte
threshold, the script archives the OLD head to a gzip under `$TEL_DIR/archive/` and keeps a recent
live tail in place, so readers keep seeing recent data while deep history compresses away.

- **Single-rotator**: a `flock` makes concurrent SessionEnd hooks rotate at most once.
- **Fail-open**: a no-op is one `stat` per file and every error path exits 0. A rare append during
  the atomic tail-swap (`mv`) can be lost; the whole layer is best-effort by design.
- **Tunable via env**: `TELEMETRY_EVENTS_MB` / `TELEMETRY_EVENTS_KEEP` (events sink threshold + tail
  lines), `TELEMETRY_METRICS_MB` / `TELEMETRY_METRICS_KEEP` (metrics sink), and
  `TELEMETRY_KEEP_ARCHIVES` (gzip files retained per base before pruning oldest).
- Call it from a SessionEnd hook.

### `cost_rollup.py <sid> | --aggregate`

Read-time true-cost ledger. Dollars are **derived here** from `model_rates.json` and never stored in
events, so rates stay correctable after the fact. It fuses three channels, joined by `sid`:

1. **main-loop** tokens, from `$TEL_DIR/session-metrics.jsonl` (`tok_by_model`),
2. **subagent** tokens, from the same record's subagent rollup, and
3. **delegated-lane** tokens, from `delegation` events in `events.jsonl` (token fields when the
   payload carries them).

It reports `cost_notional` (all channels priced at the table's reference rates — the comparable
yardstick) and `cost_real` (only channels whose rate row marks `billing: "marginal"`, i.e. actual
cash), plus `cap_pct` (main-loop share of the total) and `invisible_leg_pct` (delegated-lane share —
the work that does not appear in the main transcript). A model id missing from the table falls back
to a built-in default rate, so a ledger is always producible.

- `cost_rollup.py <sid>` prints the per-channel ledger for one session.
- `cost_rollup.py --aggregate` prints lifetime notional/real totals across all recorded sessions.

Producing `session-metrics.jsonl` (the per-session token rollup) is the install's responsibility.
An optional SessionEnd distiller can produce it, but no such distiller is shipped. With no metrics
file, the delegated-lane channel still reports from `events.jsonl` and the main/subagent channels
read as zero.

### `model_rates.json`

The correctable $/Mtok rate table — the only place prices live. Keys are the concrete model ids your
lanes are bound to in `config/model-map.toml`. Each row carries `in` / `out` / `cache_read` /
`cache_write` (USD per 1M tokens) and a `billing` field: `marginal` = real per-call cash
(pay-as-you-go credentials), `subscription` = a flat-fee plan counted as a notional yardstick rather
than invoiced per call. `cost_rollup.py` reads this at runtime, so corrections take effect
immediately.

The shipped template carries `<PICK_...>` placeholders only — replace each with a concrete model id
and current published rate before use:
```json
{
  "_note": "USD per 1M tokens. Fill in the model ids your lanes are bound to (config/model-map.toml) and current published rates. billing: 'marginal' = real per-call cash; 'subscription' = flat-fee plan = notional yardstick, not invoiced per call. cost_rollup.py reads this at runtime; nothing is baked into events, so corrections take effect immediately.",
  "<PICK_MODEL_ID>":   {"in": "<PICK_IN>", "out": "<PICK_OUT>", "cache_read": "<PICK_CACHE_READ>", "cache_write": "<PICK_CACHE_WRITE>", "billing": "subscription"},
  "<PICK_MODEL_ID_2>": {"in": "<PICK_IN>", "out": "<PICK_OUT>", "cache_read": "<PICK_CACHE_READ>", "cache_write": "<PICK_CACHE_WRITE>", "billing": "marginal"}
}
```

## The `delegation` event (shipped)

The four lane wrappers (`bin/strong`, `bin/fast`, `bin/grader`, `bin/breadth`) emit one `delegation`
event on exit via an EXIT trap. The emit is opt-in gated and fail-open: it never changes the
wrapper's own exit code. Payload as shipped:
```json
{"lane":"strong|fast|grader|breadth","exit":0,"dur_s":0}
```
The `sid` comes from `$CLAUDE_SESSION_ID` (fallback `"unknown"`). `cost_rollup.py`'s delegated-lane
channel reads token fields (`tokens` / `tokens_total`) from `delegation` events when present; the
shipped wrappers emit `lane` / `exit` / `dur_s`, so the delegation cost channel populates once token
capture is added to the payload.

## The `kb_query` event (memory)

The native memory engine emits one `kb_query` event per search when telemetry is enabled, so
retrieval quality stays observable. `/recall` searches set `origin: "recall"`; the SessionStart
memory-index path sets `origin: "digest"`. Payload as shipped:
```json
{"corpus":"cards","query":"<char-capped>","n_hits":3,"top_score":0.0,"rank_top_score":0.0,"bm25_top_score":0.0,"vector_top_score":0.0,"low_confidence":false,"is_miss":false,"miss_reason":null,"scores":[],"latency_ms":0.0,"search_mode":"fused","returned_ids":[],"origin":"recall"}
```
The `query` field is capped at `QUERY_CHAR_CAP` (4096 chars); an over-cap query is truncated and
annotated with `query_chars`, `query_truncated`, and `query_sha256`, so the full text never lands in
the sink. Emission is gated on `STRATA_TELEMETRY`; the sink is gitignored runtime data.

The SessionEnd `memory-access-log.sh` hook consumes these events: `reconcile.py --access-log` tails
the new `kb_query` rows and folds which cards were returned into
`$STATE_DIR/memory/session-state/access-log.json` for the separate memory subsystem. This data is
not an input to `telemetry/digest.py`. The hook is O(new-tail), bounded by a 20s wrapper timeout,
and fail-open.

## Adding a new event kind

Any hook appends by calling `telemetry-emit.sh <kind> <sid> '<json-payload>'`. Keep payload keys
clear of the reserved envelope set (`ts`, `sid`, `kind`, `source`). The emitter already no-ops when
telemetry is off; gate the caller on `STRATA_TELEMETRY=1` too when the hook does extra work before
the emit.

## Analyze

```sh
python3 unify.py                    # all sources -> one normalized time-sorted JSONL on stdout
python3 unify.py --counts           # + a kind/source tally to stderr
python3 unify.py --out PATH         # write to PATH (refused if tracked and not gitignored)
python3 digest.py                   # public router/delegation/friction/serial-wait digest
python3 cost_rollup.py <sid>        # per-channel true-cost ledger for one session
python3 cost_rollup.py --aggregate  # lifetime notional/real totals across sessions
bash    rotate_telemetry.sh         # rotate sinks over threshold (call from a SessionEnd hook)
```

Live event/metric data is gitignored (runtime); the scripts plus the `model_rates.json` template are
tracked.
