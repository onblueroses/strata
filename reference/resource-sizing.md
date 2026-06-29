<!-- keywords: num_workers, worker count, single worker, batch size, batch_size, concurrency, parallelism, max_tokens, learning rate, prefetch, dataloader, conservative defaults, conservative configuration, silent defaults, floor value, throughput, serial loop, too slow, ineffective config, right-size, pessimal, hyperparameter, try/except, defensive, swallowed exception, PYTHONUNBUFFERED, unbuffered monitor, saturate -->
# Resource Sizing & No Silent Defaults

Performance-relevant scalars (concurrency, batch size, worker count, prefetch depth, `max_tokens`, learning rate, parallelism) are load-bearing choices, not free safe defaults. This doc holds the behavioral layer: how to size them, which direction to lean, and how to keep the choice catchable. The non-defensive-coding half lives in `reference/code-quality-principles.md` §3; the fixed-vs-adaptive tuning detail lives in `reference/optimization-philosophy.md`.

## Quick Nav

| Need | Section |
|------|---------|
| Why conservative defaults are a bug | The Floor Is a Fingerprint |
| What to read before picking a number | Read the Substrate First |
| Which way to lean under uncertainty | Direction by Cost of Failure |
| How to make the choice catchable | Make It Legible |
| The wider failure family | Sibling Tells |
| A write-time backstop for the floor tell | Write-Time Backstop |

## The Floor Is a Fingerprint

<details>
<summary>The Floor Is a Fingerprint</summary>

The recurring agent failure is not picking *wrong* numbers; it is not attending to them at all: auto-fill the value least likely to crash (`num_workers=1`, `batch_size=1`, a serial loop over a large iterable, `concurrency=1`), never surface it, move on. Training rewards avoiding the visible failure (a crash, attributable to the agent) and is blind to the invisible one (a job running at 1/50th throughput, unattributed). So latency gets traded for robustness every time, silently.

The fix does not fight the safety drive; it reprices the failures. **A floor value is the fingerprint of an unmade decision.** Nobody reasons their way to `num_workers=0` on a 16-core box; you arrive there exactly one way, by accepting the library default and not thinking. So the floor is special: it is the syntactic signature of an absent decision, and that is dumb-detectable without knowing the right answer for the case. The intelligence (the right number) stays with the model and the substrate; the discipline only guarantees the choice gets *made* and *seen*.

The correction is not "be aggressive" (that trades silent slowness for OOMs and rate-limit bans). It is **sized-to-substrate and stated**.

</details>

## Read the Substrate First

<details>
<summary>Read the Substrate First</summary>

Before picking any throughput/parallelism number, spend the 2 seconds to read the machine instead of picking a value safe across all machines (= the worst machine):

```
nproc                 # logical cores          -> worker count
free -h               # RAM headroom           -> in-flight batch / buffer size
nvidia-smi            # VRAM + current load    -> batch size, model parallelism
# API: the rate limit (rps / TPM) and the cost -> request concurrency
# the dataset / work size                       -> whether parallelism is even worth it
```

Then match knob to bottleneck: batch size to VRAM, worker count to cores, prefetch depth to IO latency, data/model sharding to topology. Profile to know whether the work is GPU/VRAM/IO/CPU-bound before you tune; guessing the bottleneck wastes the pass. For GPU or long unattended runs, confirm the hardware is actually saturated rather than merely "the script started" — utilization checks and mid-run recovery live in `reference/gpu-training-workflow.md`.

</details>

## Direction by Cost of Failure

<details>
<summary>Direction by Cost of Failure</summary>

Conservative-by-default feels safe because of an asymmetry the agent usually gets backwards. The "bias up" rule holds only for **pure, idempotent, bounded-local** work; the moment a knob drives side effects or shared resources, overshoot stops being a clean crash and becomes a hang, lock contention, duplicate writes, FD exhaustion, or a rate-limit failure. So gate the direction on what the work touches:

| Knob / work | Overshoot failure | Recoverable? | Lean |
|------|-------------------|--------------|------|
| local workers over pure / in-memory data | RAM pressure, clean crash | yes, instantly | **up**, crash-and-halve |
| batch size on a re-runnable job | OOM | yes, one re-run | **up**, crash-and-halve |
| eval/embedding loop over local data | memory blip | yes | **up** / batch it |
| workers touching DB / API / files / fork-unsafe libs / non-idempotent side effects | hang, contention, duplicate writes, FD exhaustion | often not cleanly | **measured ramp**, even locally |
| paid-API request concurrency | rate-limit ban, cost blowup | sometimes not cheaply | measured ramp |
| irreversible writes / migrations | data damage | no | measured, gated |

Where the failure is loud, fast, and recoverable, the bold choice *is* the safe choice: bias up and let it crash-and-halve. Where overshoot turns into a silent hang or a non-idempotent side effect, ramp measured even on local hardware.

</details>

## Make It Legible

<details>
<summary>Make It Legible</summary>

State every performance-relevant number with its basis, in one breath: `workers=12 (16 cores)`, `concurrency=8 (rate limit 10 rps)`, `batch=1 (VRAM-bound, 4k-token items)`. The act of writing the basis forces the reasoning, and surfaces the absurd cases on contact ("workers=1 because the machine has 16 cores" cannot be written with a straight face). It also makes the choice catchable by a reviewer. When the value is genuinely a floor, say why; the floor with a stated reason is fine, the floor in silence is the bug.

</details>

## Sibling Tells

<details>
<summary>Sibling Tells</summary>

The same move shows up across the codebase: converting a loud, recoverable failure into a silent, expensive one. Prefer the loud one.

- **Swallowed exceptions** (`try/except: pass`, bare `except:`, empty `catch {}`) hide the failure the conservative config would otherwise make visible. Let it surface, or name why it is safe to eat. Detail: `reference/code-quality-principles.md` §3 *Non-Defensive Coding*.
- **Blind monitors** (a watcher behind buffered stdout, `tail` on a dead process, a job whose log never advances) report nothing while looking healthy. Verify the monitor actually advances before trusting it (`python -u` / `PYTHONUNBUFFERED=1`, confirm the process is alive, confirm the log moves). For GPU or long runs, "the script started" is not "the hardware is saturated": confirm utilization, see `reference/gpu-training-workflow.md`.
- **Fixed conservative hyperparameters** are a guess frozen in. Adaptive mechanisms (acceptance-rate-targeted step size, reheating, diagnose-before-you-compute) find the operating point automatically: `reference/optimization-philosophy.md` → *Adaptive Beats Fixed*, *Diagnose Before You Compute*.

</details>

## Write-Time Backstop

<details>
<summary>Write-Time Backstop</summary>

A directive alone leaks; the floor tell wants a bias-immune layer. If you wire one, the right shape is a `PostToolUse` hook on `Edit|Write` (sitting alongside `quality-lint-on-write.sh`) that is a *silence detector*, not an optimality judge. It does **not** decide whether a number is optimal (impossible per-case, and a linter that is wrong constantly gets muted). It scans written Python/TS/JS for the floor-value fingerprint and the swallowed-exception tells, then emits an advisory asking you to right-size or name the basis.

- **Flags**: floor throughput scalars (`num_workers`/`max_workers`/`n_jobs`/`concurrency`/`parallelism` = 0|1, `batch_size=1`); `DataLoader(...)` with no `num_workers` anywhere in the call (paren-balanced, multi-line and nested-paren safe, so `DataLoader(TextDataset(x), ..., num_workers=2)` does not false-positive); bare / `pass` / `continue` / multi-line-`pass` excepts; empty JS `catch {}`.
- **Self-silencing**: a comment on the flagged line that *names a basis* (substrate or cost, non-vacuous, ≥12 chars, not `# ok` / `# todo` / `# noqa`) marks the decision as made and the check stays quiet. A genuinely-correct floor costs one basis comment; that is the legibility we wanted, and it is the only residual false positive such a hook leaves.
- **Changed-lines only**: an Edit flags tells in the edit's new text; a Write scans the whole (new or overwritten) file. Unrelated edits do not re-flag old lines. Vendored / generated / `tests/` paths are skipped.
- **Limits**: syntactic, floor-only tells. It catches `workers=0` but not `workers=2` on a 64-core box, an obfuscated serial loop, or `max_tokens` / learning-rate / `prefetch_factor` (no meaningful floor value) — those stay directive- and review-only. The blind-monitor tell is a Bash-invocation concern, carried in prose, not in such a hook. Swallowed-exception detection overlaps ruff (E722/S110/SIM105); a hook is a backstop where those rules are off.
- **Non-blocking**: advisory via `additionalContext`, never a verdict; the model decides.

</details>
