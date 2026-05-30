<!-- keywords: autooptimize, optimization loop, benchmark, hypothesis, a/b test, autooptimize session, dual-channel logging, llm cache -->
# Autooptimize Methodology

Autonomous code optimization loop. Hypothesize, implement, benchmark, keep or discard, repeat. Inspired by Karpathy's autoresearch (630-line loop, 700+ autonomous commits, 11% efficiency gain).

This is a methodology reference, not a skill. Different optimization targets (Rust perf, JS bundle size, Lighthouse scores, ML training loss) diverge in tooling but share the same core loop and decision logic. Project-specific config lives in `.claude/autooptimize.toml`.

## Quick Nav

| Section | Jump to | Read when |
|---------|---------|-----------|
| Core Loop | Core Loop | Starting any optimization session |
| State Management | State Management | Setting up logging, understanding dual-channel architecture |
| A/B Benchmarking | A/B Benchmarking | Running or interpreting benchmarks |
| Decision Logic | Decision Logic | Understanding keep/discard/inconclusive outcomes |
| Hypothesis Strategy | Hypothesis Strategy | Generating and prioritizing what to try next |
| LLM Explanation Cache | LLM Explanation Cache | Caching LLM-generated summaries of experiments |
| Profiling | Profiling | Reading flamegraphs, choosing what to optimize |
| Rust Patterns | Rust-Specific Patterns | Optimizing Rust code specifically |
| Config Reference | Config Reference | Setting up autooptimize.toml for a project |

---

## Core Loop

The loop is universal across languages and metric types. Everything project-specific is in config.

```
Initialize -> Profile -> [Hypothesize -> Implement -> Gate -> Benchmark -> Decide -> Log] -> Summary
                ^                                                                    |
                |________ re-profile after 2+ kept experiments _____________________|
```

### Phase 0: Initialize

<details>
<summary>Phase 0: Initialize</summary>

1. **Read config.** Parse `.claude/autooptimize.toml` from the project root. Validate required fields.

2. **Check git state.** Must be on `main` (or `master`), clean working tree.

3. **Establish baseline.** If no experiment log exists:
   - Build locally to verify compilation
   - Push to origin, pull on benchmark target (VPS or local)
   - Run benchmark script, parse median metric
   - Write baseline entry to experiment log (JSONL)
   - If log exists, last kept entry's metric is the baseline

4. **Load context.** Read:
   - Performance doc (bottleneck analysis, roadmap)
   - Experiment log (avoid repeating failures)
   - Scope files (code that can be modified)
   - Profile data if it exists

5. **Report.** "Baseline: {metric} {unit}. Running up to {max} experiments. Stopping after {max_failures} consecutive failures."

</details>

### Phase 0.5: Profile

<details>
<summary>Phase 0.5: Profile</summary>

Run before the first experiment. Skip only if `[profiling]` is absent from config AND `--skip-profile` is passed.

1. **Build release binary.** Run `[build].command`.

2. **Run profiler.** Language-specific defaults:
   - Rust: `samply record` (flamegraph)
   - Node.js: `node --prof` + `node --prof-process`
   - Python: `py-spy record`
   - Or use `[profiling].command` verbatim.

3. **Extract top-5 hotspots.** For each: function name, file, inclusive %, exclusive %, call count.

4. **Cross-reference with performance doc.** Flag discrepancies between profiler data and documented bottlenecks.

5. **Store.** Save to `.claude/autooptimize-profile.md` (overwritten each run).

</details>

### Experiment Loop

For each experiment (up to `constraints.max_experiments`):

**Step 1: Hypothesize** - Generate hypothesis with basis citation. See Hypothesis Strategy section.

**Step 2: Implement** - Branch (`autoopt/{NNN}-{short-name}`), edit scope files, commit.

**Step 3: Local Gates** - Format, compile, lint, test. Fix once; if still failing, log `gate_fail` with root cause analysis and discard.

**Step 4: Determinism Check** (if configured) - Same seed must produce identical output. Log `determinism_fail` and discard if not.

**Step 5: A/B Benchmark** - See A/B Benchmarking section.

**Step 6: Decide** - See Decision Logic section.

**Step 7: Loop or Stop** - Re-profile after 2+ kept experiments. Check stopping conditions: max experiments, consecutive failures (with escalation), or plateau.

### Stopping and Escalation

<details>
<summary>Stopping and Escalation</summary>

When `max_consecutive_failures` is hit, escalate before stopping:

1. Count recent failure types. If mostly micro-optimizations (T3/T4): "Micro-optimizations exhausted. Escalating to structural (T1)." Reset counter, force next hypothesis to T0/T1.
2. If structural also failed: re-profile (bottleneck may have shifted). Reset counter.
3. If re-profile + structural still fails: "Optimization plateau reached after {N} experiments."

INCONCLUSIVE results do NOT increment the failure counter.

</details>

---

## State Management

### Dual-Channel Logging

Experiment state uses two separate append-only JSONL files with clean ownership boundaries:

**Channel 1: Experiment Log** (`autooptimize-experiments.jsonl`)
- Owned by the optimization loop
- One entry per experiment: what ran, what measured, what happened
- Never modified by analysis or explanation tools
- Ground truth for the session

```jsonl
{"timestamp":"2026-03-31T14:00:00Z","id":"001","branch":"autoopt/001-simd-distance","hypothesis":"SIMD batch distance calc","basis":"T0: profile hotspot compute_distances (41.2%)","files_changed":["src/signal.rs"],"metric_before":6.17,"metric_after":6.68,"delta_pct":8.3,"snr":3.1,"kept":true,"notes":""}
{"timestamp":"2026-03-31T14:35:00Z","id":"002","branch":"autoopt/002-unroll-inner","hypothesis":"Unroll inner loop 4x","basis":"T4: profile hotspot update_positions (8.3%)","files_changed":["src/sim.rs"],"metric_before":6.68,"metric_after":6.71,"delta_pct":0.4,"snr":0.8,"kept":false,"notes":"inconclusive: delta below noise floor, CoV_baseline=1.2%"}
```

**Channel 2: Enrichment Log** (`autooptimize-meta.jsonl`)
- Owned by the analysis/explanation layer
- Stores LLM-generated explanations, summary text, promotion decisions
- Reads experiment log but never writes to it
- Can be regenerated from experiment log + code without data loss

```jsonl
{"timestamp":"2026-03-31T14:05:00Z","experiment_id":"001","type":"explanation","input_hash":"a3f2...","prompt_version":"v1","content":"SIMD batch processing of distance calculations reduced branch overhead..."}
{"timestamp":"2026-03-31T15:00:00Z","type":"session_summary","experiments_run":5,"kept":2,"total_improvement_pct":12.4}
```

**Why two channels:**
- If the explanation layer crashes or produces bad output, experiment data is intact
- Replaying a session with a better explanation prompt costs zero re-benchmarking
- Clean read-only guarantee on ground truth prevents a category of corruption bugs
- Each channel can be independently backed up, truncated, or migrated

### Entry Format

Each experiment log entry contains:

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | ISO 8601 | When the experiment completed |
| `id` | string | Zero-padded experiment number (e.g., "001") |
| `branch` | string | Git branch name |
| `hypothesis` | string | What was tested |
| `basis` | string | Tier + citation (e.g., "T0: profile hotspot fn (41%)") |
| `files_changed` | string[] | Files modified |
| `metric_before` | number | Baseline metric value |
| `metric_after` | number \| null | Measured metric (null if gate_fail) |
| `delta_pct` | number \| null | Percentage change |
| `snr` | number \| null | Signal-to-noise ratio |
| `kept` | boolean | Whether the experiment was merged to main |
| `notes` | string | Outcome detail: gate_fail reason, regression analysis, etc. |

---

## A/B Benchmarking

<details>
<summary>A/B Benchmarking</summary>

Build BOTH main and experiment binaries, benchmark back-to-back in the same session. This eliminates baseline drift from load changes between runs.

### Protocol

1. **Build both binaries** (baseline from main, experiment from branch)
2. **Warm up** - `warmup_runs` (default 2) for each binary, results discarded
3. **Interleave measurement runs** - pattern: `W W W W B E B E B E B E B E` (W=warmup, B=baseline, E=experiment)
4. **Compute statistics:**
   - Median of each set (after discarding warm-up)
   - CoV (coefficient of variation = std/mean) of each set
   - `delta_pct = (experiment_median - baseline_median) / baseline_median * 100`
   - `signal_to_noise = |delta_pct| / (CoV_baseline + CoV_experiment)`

### VPS Mode

Push branch, SSH to VPS, build both, run interleaved A/B, restore VPS to main. Never benchmark in separate SSH sessions.

Default runs: 7 per binary (VPS), 12 per binary (local - noisier environment).

### Timeout

300 seconds for A/B sessions. If SSH times out: log `vps_timeout`, discard branch (local + remote), continue.

</details>

---

## Decision Logic

Three outcomes based on `delta_pct` and `signal_to_noise`:

**KEEP** - `delta_pct >= min_improvement_pct` AND `snr >= 2.0`:
- Merge to main, push, clean up branch
- Update baseline to new metric
- Reset consecutive failure counter

**INCONCLUSIVE** - `|delta_pct| < min_improvement_pct` OR `snr < 2.0`:
- In the noise floor. Neither better nor worse.
- Clean up branch. Do NOT increment failure counter.
- Log with analysis: was the change too small to measure, or is the benchmark too noisy?

**DISCARD** - `delta_pct < -min_improvement_pct` AND `snr >= 2.0`:
- Real, measurable regression.
- Clean up branch. Increment failure counter.
- Log with root cause: cache pressure? Branch misprediction? Algorithm overhead on small N?

### Multi-Objective Mode

<details>
<summary>Multi-Objective Mode</summary>

When `[[objectives]]` is defined in config:

**Roles:**
- `primary` - the metric being optimized. Exactly one. Drives KEEP decisions.
- `constraint` - must not regress beyond `max_regression_pct`. Violation = DISCARD regardless of primary improvement.
- `secondary` - tracked and reported. Tips borderline decisions. Use `weight` (0-1) for relative importance.

**Decision order:**
1. Check all constraints first. Any violation with SNR >= 2.0 = DISCARD.
2. Evaluate primary with normal KEEP/INCONCLUSIVE/DISCARD logic.
3. For borderline primary results, secondary objectives tip the decision.
4. Log all objective deltas in a single entry.

</details>

---

## LLM Explanation Cache

<details>
<summary>LLM Explanation Cache</summary>

When generating LLM explanations of experiments (summaries, analysis, recommendations), use content-addressed caching to avoid redundant API calls.

### Cache Key

```
key = SHA256(JSON.stringify(explainInput)) + ":" + PROMPT_VERSION
```

Where `explainInput` captures the full context:
- Target experiment (commit, metric delta, files changed)
- Baseline experiment (what it's compared against)
- Prior experiment (for trend analysis)
- Number of kept experiments at time of explanation

This means:
- Same experiment explained at different points in the session gets different cache keys (correct - context changed)
- Same experiment explained with same context hits cache (no re-spend)
- Changing `PROMPT_VERSION` invalidates all cached explanations globally without touching experiment data

### Storage

Cached explanations live in the enrichment log (`autooptimize-meta.jsonl`). The `input_hash` field is the cache key. Before calling the LLM:

1. Grep enrichment log for matching `input_hash` + `prompt_version`
2. If found, use cached content
3. If miss, call LLM, write result to enrichment log with hash

### Heuristic Fallback

If no LLM is available (no API key, rate limited, offline), generate a structured explanation from the experiment data alone:

- Summary: "{hypothesis} targeting {basis}"
- Outcome: "{delta_pct}% change (SNR {snr}) - {KEEP/INCONCLUSIVE/DISCARD}"
- Mechanism: infer from files changed + delta direction
- Recommendation: based on outcome + experiment history

The heuristic path writes to the same cache. LLM explanations are better prose but the heuristic is fully functional.

### Prompt Versioning

```
PROMPT_VERSION = "v1"
```

Bump this when changing the explanation prompt. All cached explanations auto-invalidate because the cache key includes the version. No manual cache clearing needed.

</details>

---

## Hypothesis Strategy

### Prioritization Ladder

<details>
<summary>Prioritization Ladder</summary>

Try ideas in this order. Move to the next tier only when the current tier is exhausted or blocked.

**T0: Profile-Driven (Highest Confidence)**
Target a measured hotspot. Read `.claude/autooptimize-profile.md` for top-5. Estimate impact with Amdahl's Law: `expected = inclusive_pct * (1 - 1/speedup)`.

If the profiler hasn't been run, don't generate hypotheses. Go back to Phase 0.5.

**T1: Structural (Algorithm/Data Structure)**
Changes that alter complexity class or data layout. High impact, higher risk. Examples: O(n^2) -> O(n log n), AoS -> SoA, hash map -> sorted array for small N, spatial indexing for distance queries.

Cross-reference with profiler - structural change to a 2%-of-runtime function is wasted effort.

**T2: Roadmap Items**
Items from the project's performance doc marked high impact, not yet tried. Cross-reference with profile data.

**T3: Variations on Partial Successes**
Past experiments that improved the metric but failed a gate. The optimization works - the constraint violation needs solving. Adapt: if determinism failed from float reordering, use order-independent reduction. If tests failed, fix the edge case.

**T4: Micro-Optimizations (Diminishing Returns)**
Constant tuning, `#[inline]`, struct size reduction, field reordering. If 2+ consecutive T4 experiments produced INCONCLUSIVE, stop - you're below the noise floor. Escalate to T0/T1.

</details>

### Basis Citations

<details>
<summary>Basis Citations</summary>

Every hypothesis must cite its grounding. A hypothesis without a basis is speculation.

```
T0: basis: profile hotspot compute_forces (41.2%)
T1: basis: structural opportunity in spatial indexing (currently O(n^2) neighbor search)
T2: basis: roadmap item "batch brain forward pass"
T3: basis: experiment 003 (+4.1%, determinism_fail) - adapting SIMD to ordered reduction
T4: basis: profile hotspot update_positions (8.3%) - micro-opt
```

</details>

### Parallel Search Mode

When sequential tier exhaustion stalls or the search space is wide, generate N hypotheses across all tiers and evaluate in parallel. See `hypothesis-engine.md > Parallel Search Mode` for the full protocol. Use when: benchmarks are fast (<5 min), T0-T2 producing INCONCLUSIVE, or you have compute budget for N parallel runs. Validated by the Paradigm Autoresearch Hackathon (1,039 parallel strategies, 42.32 mean edge, 1st place vs 110 manual iterations at 2nd).

### Learning from the Experiment Log

<details>
<summary>Learning from the Experiment Log</summary>

Before generating a hypothesis, synthesize the log into actionable patterns:

1. **Constraint boundaries.** Which gates failed and why? Each gate failure narrows the feasible design space. "determinism_fail: SIMD reordered f32 adds" means all future SIMD work must use order-independent reductions.

2. **Diminishing avenue.** If 2+ experiments targeted the same function/approach and both were inconclusive, that avenue is at the noise floor. Move to a different hotspot or escalate.

3. **Partial success signal.** Improved metric but failed gate = highest-value signal. The optimization works; only the constraint violation needs solving.

4. **Regression root causes.** "Cache pressure from larger struct" tells you the workload is memory-bound in that region. Don't try approaches that increase memory footprint in the same path.

</details>

---

## Profiling

<details>
<summary>Reading Profiler Output</summary>

### Flamegraphs

- **Width = time.** Wide bars = CPU time. Narrow = fast.
- **Inclusive vs exclusive time.** 40% inclusive but 2% exclusive = dispatcher. Optimize callees, not it.
- **Call count vs per-call cost.** 10M calls at 1us looks the same as 10 calls at 1s. Check both.
- **Flat tops.** Wide bar with no children = leaf function in its own code. Prime target.

### Key Metrics (perf stat)

- **IPC** < 1.0: memory-bound or branch-heavy. > 2.0: compute-bound (harder to optimize).
- **Cache miss rate** > 5% of loads: cache-unfriendly patterns. Consider SoA or data reordering.
- **Branch misprediction** > 5%: unpredictable branches. But if prediction > 95%, branchless rewrites often regress.

### Traps

- Profiling debug builds (completely different hotspots)
- Profiling with different data than benchmark uses
- Optimizing cold startup code

</details>

---

## Rust-Specific Patterns

<details>
<summary>Rust-Specific Patterns</summary>

### SIMD / Auto-vectorization
- Restructure inner loops for contiguous f32 arrays
- Avoid branches inside innermost loop (conditional moves or masks)
- Ensure loop trip counts are known at compile time
- `#[repr(align(32))]` on arrays processed by SIMD
- Check: `RUSTFLAGS="-C target-cpu=znver3 --emit=asm" cargo build --release`, grep for `vmulps`/`vaddps`

### Cache Locality
- SoA > AoS when iterating one field
- Extract hot fields from large structs for inner loops
- `Vec<T>` > `Vec<Box<T>>` > `Vec<Arc<T>>` for pointer indirection
- Pre-sort data by access pattern

### Allocation Reduction
- `Vec::with_capacity` + `clear()` outside loops, not `Vec::new()` each iteration
- Stack arrays `[T; N]` for small fixed-size collections
- Reservoir sampling instead of collecting into Vec
- `SmallVec` for usually-small vectors

### Branch Elimination
- `if x > 0 { x } else { 0 }` -> `x.max(0)` (branchless)
- Replace `%` with conditional subtract when value is within 2x modulus
- `bool as usize` for conditional indexing

</details>

---

## Estimating Impact

Before implementing, estimate expected speedup:

```
expected_improvement = bottleneck_fraction * (1 - 1/speedup_factor) * 100%
```

Example: function is 41% of runtime, SIMD gives 2x speedup:
`0.41 * (1 - 1/2) * 100% = 20.5% overall improvement`

If expected improvement is below `min_improvement_pct`, skip to next hypothesis.

---

## Config Reference

<details>
<summary>Config Reference (.claude/autooptimize.toml)</summary>

```toml
[project]
name = "project-name"
scope = ["src/file1.rs", "src/file2.rs"]  # files the optimizer can modify

[build]
command = "cargo build --release"
vps_rustflags = "-C target-cpu=znver3"     # RUSTFLAGS for VPS (optional)
test_command = "cargo test"
lint_command = "cargo clippy -- -D warnings"
fmt_command = "cargo fmt --check"

[benchmark]
script = "bench.sh"
metric_name = "gens_per_sec"
metric_direction = "higher"                # "higher" or "lower"
runs_per_experiment = 7
warmup_runs = 2
aggregation = "median"
benchmark_gens = 50
benchmark_seed = 42
benchmark_args = "--metrics-interval 10"

[benchmark.vps]                            # optional - omit for local-only
host_alias = "remote"                     # SSH config alias, never raw IP
repo_path = "/root/project"
binary_path = "target/release/binary-name"

[benchmark.local]                          # optional - defaults shown
warmup_runs = 2
runs_per_experiment = 12                   # more runs for noisier env
threshold = 3.0

[profiling]                                # optional
command = ""                               # e.g., "samply record ./target/release/binary args"

[constraints]
determinism_check = true
determinism_seed = 42
determinism_gens = 10
min_improvement_pct = 2.0
max_consecutive_failures = 5
max_experiments = 5
```

### Multi-Objective Config

```toml
[[objectives]]
name = "latency_ms"
direction = "lower"
role = "primary"
min_improvement_pct = 5.0

[[objectives]]
name = "accuracy_pct"
direction = "higher"
role = "constraint"
max_regression_pct = 1.0

[[objectives]]
name = "false_positive_rate"
direction = "lower"
role = "secondary"
weight = 0.3
```

### Generalization Notes

- `[benchmark.vps]` is optional. Without it, benchmarks run locally.
- `[profiling]` is optional. Uses language-specific defaults based on file extensions.
- `determinism_check` is project-specific. Most projects don't need it.
- `scope` can be directories for larger projects.
- The core loop is universal. Only build/bench/profile commands are language-specific.

</details>

---

## Anti-Patterns

- Don't optimize what you haven't profiled
- Don't combine multiple changes in one experiment
- Don't fight the branch predictor (if prediction > 95%, branchless often regresses)
- Don't add complexity for < 2% gain
- Don't assume local benchmarks transfer to VPS (different CPU, cache, contention)
- Don't benchmark without A/B comparison
- Don't modify the benchmark script during experiments - it's the evaluator
- Don't skip determinism check when configured
- Don't hardcode VPS IPs - use SSH config aliases
- Don't treat inconclusive as failure - it means noise, not bad

---

## Quality Self-Check

After each experiment:
1. Experiment log has a new JSONL entry
2. Git is back on main with clean working tree
3. If kept: main includes merged changes, pushed to origin
4. If discarded: branch deleted (local AND remote)
5. Determinism check ran if configured
