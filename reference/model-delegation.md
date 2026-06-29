<!-- keywords: delegate, delegation, dispatch, sub-model, sub-agent, lane, strong, fast, grader, breadth, orchestrator, orchestrate, hand off, handoff, offload, farm out, which model, another model, second opinion, parallel review, review panel, agentic, tool-use loop, working tree, cwd, oneshot, read-only, edit files, run commands, fallback, quota, rate limit, cache, prompt cache, exit code, wrapper, model-map, routing, background job, long-running -->
# Model Delegation

How to delegate sub-tasks to other models from this Claude Code session.

You (Claude in this session) are the orchestrator. The lanes are bash wrappers at `$STRATA_HOME/bin/` (`strong`, `fast`, `grader`, `breadth`); the concrete model bound to each lane is set in `config/model-map.toml`, so rebind there as models churn. Each lane takes a self-contained prompt, returns text on stdout, and reports failure modes via exit code.

**All four lanes are agentic** — each runs a real tool-use loop in its working directory via strata's multi-provider agent, with tools to read and write files, run shell commands, and search. They explore, edit, and run commands in their cwd, then return their final text. Point a lane at a tree with `--cwd DIR` and it does the task in that tree (then `git -C DIR diff` to capture the result); pass `--oneshot` to restrict it to read-only reasoning that returns text and changes nothing. The default (`--agentic`) preserves full read/write/exec, so a prompt that asks only for analysis still just gets analysis back.

## Quick Nav

| Task | Section |
|------|---------|
| Pick which lane for a task | Tier Sketch |
| Run a lane agentically in a tree | Wrapper Reference |
| See command flag reference | Wrapper Reference |
| Chain lanes on quota | Fallback Chain |
| Use cached responses | Caching |
| Read failure exit codes | Exit Code Contract |
| Write a self-contained prompt | Prompt Template |
| Long-running jobs (>10 min) | Long-Running Jobs |
| Bench data behind these picks | Empirical Latency / Quality |

## Tier Sketch

Pick the lane by what the task actually needs. The model bound to each lane lives in `config/model-map.toml`; rebind as models churn. Bench numbers (illustrative, one run) below.

```
fast      DEFAULT FOR CODE. Fast and strong; ~strong quality on most code tasks.
          24-37s on hard tasks. Lean on it aggressively.

strong    DEEPER. Load-bearing logic, security review, hardest debugging,
          architecture decisions. 27-166s. Higher quality on subtle reasoning.

grader    CHEAP + FAST. Summaries, simple fixes, non-code reasoning, parallel
          review panels, and sparing primary-lane quota. 43-110s.

breadth   FALLBACK + VERBOSE. When both primary lanes are exhausted, or for
          thorough non-code reasoning / a second model voice. 168-363s; slowest.
```

Be aggressive with `fast`: it is cheap and the empirical winner on code tasks. Reserve `strong` for genuinely hard reasoning that benefits from the deepest reasoning effort. The secondary lanes (`grader`, `breadth`) are the off-ramp when both primary lanes throttle.

## Wrapper Reference

All four lane wrappers share a near-identical interface; the per-group differences are noted below. Each takes a self-contained prompt (arg, `--file`, or stdin) and runs an agentic tool-use loop in its working directory, then returns its final text on stdout.

```bash
# Three ways to pass the prompt
grader "prompt"                  # arg
grader --file prompt.md          # file (binary-safe)
echo "prompt" | grader           # stdin

# Common flags (all four lanes)
--file PATH         Read prompt from file (binary-safe)
--system TEXT       Override the default system prompt
--cwd DIR           Run the agent with DIR as its working root; it explores,
                    edits, and runs commands inside DIR. Capture the result
                    with `git -C DIR diff`.
--oneshot           Read-only: reason + read + return text, mutate nothing.
--agentic           Full read/write/exec in the working directory (default).
--cache MODE        off | read | write | rw   (default off)
--timeout SECS      Max wall time (default 1800 = 30 min)
```

### strong / fast (primary lanes)

```
--reasoning EFFORT  low | medium | high | xhigh   (default xhigh; xhigh is the
                    ceiling, no tier above)
--raw               Emit full backend stdout including session header/footer
                    (default: stripped to model output only)
```

### grader / breadth (secondary lanes)

These take no output-budget flag. Output budgeting is internal (the old `--max-tokens` / `--json` flags were removed); on an empty return, re-run rather than tuning a budget. The `--system` flag (common, above) covers prompt overrides.

## Exit Code Contract

```
0   Success — read stdout for content
1   Usage error (your invocation has a bug; fix it)
2   API error (transient or permanent — read stderr)
3   Quota / rate limit (429) — fall back to next lane
4   Auth error — a lane's API key is missing/wrong, or its login expired
5   Silent failure — empty content despite no error.
    For secondary lanes: re-run (no output-budget flag; persistent emptiness
      means the prompt confused the agent loop).
    For primary lanes: the prompt is likely >8KB on non-TTY input — shrink it.
```

You (the orchestrator) react on exit code, not message text. The contract is stable across all four lanes.

## Fallback Chain

Sequential, not parallel. On exit 3 (quota), drop one lane:

```
strong       exit 3   →   try fast
fast         exit 3   →   try breadth
breadth      exit 3   →   try grader
grader       exit 3   →   surface to user; we're out
```

For exit 5 (silent), recovery differs by group:
- Secondary-lane exit 5: re-run (no output-budget flag; persistent emptiness means the prompt confused the agent loop).
- Primary-lane exit 5: shrink the prompt (likely >8KB) or try the other primary lane.

Do **not** fan the same logical request out to all four in parallel — wastes tokens and creates ambiguous results.

## Caching

Opt-in, off by default.

```
--cache off       (default) no cache interaction
--cache read      hit cache if exists, else API call (no write)
--cache write     always API call, write result to cache
--cache rw        hit cache if exists, else API + write
```

Cache key: `sha256(model | prompt)` — any byte change is a cache miss. Cache files live under the `cache_dir` set in `config/model-map.toml` (`$STRATA_HOME/.local/delegate-cache` by default). An empty `cache_dir` disables caching. `--cwd` forces caching off, since repo state is not in the cache key.

When to use:
- **`rw`** — repeating identical queries across iterations or sessions
- **`read`** — replaying a known-good response without API cost
- **`write`** — explicit refresh (force re-call, save new answer)
- **`off`** — exploratory work where the prompt mutates each call

Failure modes to avoid:
- **Stale embedded files**: if the prompt embeds file contents that have changed, re-embed before re-querying — the cache is keyed on prompt text, not source file mtime.
- **Cache poisoning**: if a previous response was bad, `--cache read` keeps returning it. Use `--cache write` to overwrite.

Some providers also run a server-side prompt cache (free, automatic). Stable prefixes (system prompt, embedded docs) can hit at a steep discount, often 100×+ cheaper than uncached. Structure prompts so stable parts come first and variable content last.

## Prompt Template

Sub-models start fresh — no conversation memory, no shared context. Every prompt is self-contained and opens with an outcome block (Goal / Success / Stop), then a directional body. See `CLAUDE.md` `## Prompt Authoring` and the `/directional-prompting` skill for the underlying discipline.

```
Goal: <one sentence — what you want this model to produce>

Success means:
  - <checkable output element, e.g. "patch in unified diff format">
  - <checkable output element, e.g. "every changed function has a docstring">
  - <length / format / schema constraint>

Stop when: <explicit stopping condition — e.g. "all tests in the suggested patch type-check in isolation">

CONTEXT:
<embedded code blocks, file contents, prior outputs — everything the model needs>

TASK:
<directional body: each sentence leads with the positive verb of the correct action — trace, build, return, check, ask. Describe the destination so completely that the wrong behavior has no foothold.>

OUTPUT FORMAT:
<exact shape: "unified diff", "JSON matching this schema", "numbered fix list", etc.>
```

**Why the outcome block matters for reasoning models**: a heavy reasoning lane (`strong` on its deepest effort) will refine past usefulness without an explicit `Stop when:` — it reasons the task into perpetual revision. The stopping condition is what lets you keep `--timeout` off while still bounding work; the model self-terminates on a criterion it can reason about, rather than being killed mid-flight by a wall clock.

**Why the directional body matters**: a `CONSTRAINTS: don't do X` line plants X as a concept the model now has to actively suppress on every token. A directional `TASK:` line where every sentence names the correct action gives the model a path to walk instead of a fence to avoid. Same constraint coverage, lower token cost, less drift. Reserve negation for the four legitimate cases (safety, near-identical-path disambiguation, large acceptable space, specific banned items).

**Why explicit format constraints**: reasoning models obey them reliably. Without them, a verbose lane like `breadth` produces 5KB of bloat on a 200-byte question. With them, all four lanes produce comparable, terse outputs.

## Long-Running Jobs

The Bash tool's 10-minute timeout is the only real constraint. Wrappers internally support 30-minute timeouts via `--timeout`.

**Background + auto-notify pattern (the right way for any job >10 min):**

Invoke the wrapper via Bash with `run_in_background: true`. The harness tracks the process and **automatically pushes a `<task-notification>` to you when it completes** — you do *not* poll, sleep, or check status. No idle waiting; no tokens burned on monitoring.

Workflow:
1. Issue the wrapper call with `run_in_background: true`. The Bash tool returns immediately with a task ID.
2. Continue with other work — read more files, dispatch other lanes, synthesize earlier results.
3. When the background job completes, you receive a system notification with the task ID and exit status.
4. Read the captured stdout from the notification's output file.

**Anti-pattern: chained polling loops.** Don't write `bash -c 'while pgrep -f X; do sleep 10; done; do_next'` — `pgrep -f` matches the wait shell's own command line and infinite-loops. If you need to chain, either (a) submit step 2 only after step 1's notification fires, or (b) use a sentinel-file pattern (step 1 writes `done.flag`; step 2 waits for that flag's existence).

**Empirical defaults from bench data:**
- `fast` / `strong` on simple prompts: 24-37s — foreground Bash is fine.
- `grader` on simple prompts: 6-110s — foreground usually fits.
- `breadth` on hard reasoning: 168-363s+ — use background.
- Any task with embedded long-context (>20KB) or one that edits many files: background.

## Empirical Latency / Quality

Bench: 3 tasks × 4 lanes × 1 run (illustrative; the bound models have since churned).

| Task | grader | breadth | fast | strong |
|------|--------|---------|------|--------|
| Hard reasoning (rate limiter design) | 110s / 9.5KB | 363s / 15KB | **24s / 18KB** | 166s / 12KB |
| Long-context (33KB doc analysis) | 43s / 2.7KB | 168s / 4.5KB | **24s / 3.7KB** | 27s / 3.7KB |
| Long-form output (5K word writeup) | 101s / 28KB | 313s / 38KB | **37s / 39KB** | 161s / 30KB |

Quality (qualitative spot-check on the rate-limiter task):
- **fast**: richest types (Decision dataclass, Protocol classes for sync/async backends), generic dispatch, frozen dataclasses. Best balance.
- **strong**: comparable to fast in code structure; deeper on edge cases. Worth the latency on subtle bugs.
- **breadth**: TypedDict (less type-safe), bool returns (loses metadata), simpler. Verbose but lower architectural polish.
- **grader**: solid but loses detail on subtle requirements (e.g., distinguishing an all-negative-array case in an earlier bug-finding bench).

Re-run your own matrix after rebinding lanes in `config/model-map.toml`; the picks above are only as current as the models behind them.

## Failure Modes Caught (from research)

Documented gotchas across the four lane wrappers:

1. **Silent crash on prompts >8KB (agent-CLI-backed lanes)**: non-TTY stdin plus a large prompt can exit 0 with empty stdout. The wrappers warn at >8KB and report empty content as exit 5.
2. **400 errors with exit 0**: some backends return invalid-model / 400 responses as `ERROR: {"status":400,...}` lines on stdout while exiting 0. The wrappers detect these and convert them to exit 2.
3. **Reasoning models spend the output budget on hidden reasoning**: 75-90% of the completion budget can go to reasoning before any output appears. Output budgeting is handled internally now; an empty return means re-run, not tune a flag.
4. **`bc` not installed on some systems**: the bench script falls back to integer-second timing when `bc` is absent.
5. **Quota detection**: a backend's rate-limit string is matched and converted to exit 3, which the orchestrator turns into a fallback.

## Examples

**Quick code review on a function.**
```bash
cat my_function.py | grader \
  "Find any bugs in the code below. Output: bug list, then fixed code. Terse."
```

**Hard architecture question.**
```bash
strong --file design-prompt.md --reasoning xhigh
```

**Agentic task in a worktree (the lane edits files itself).**
```bash
strong --cwd /path/to/repo \
  "Implement X across the module, run the tests, report what changed."
git -C /path/to/repo diff      # capture the result
```

**Read-only analysis, no mutations.**
```bash
strong --oneshot --file review-prompt.md
```

**Repeated identical query (e.g., during workflow iteration).**
```bash
fast --file plan.md --cache rw
```

**Fallback chain in pseudocode (you, the orchestrator, run this logic).**
```bash
strong --file prompt.md
if [ $? -eq 3 ]; then fast --file prompt.md; fi
if [ $? -eq 3 ]; then breadth --file prompt.md; fi
if [ $? -eq 3 ]; then grader --file prompt.md; fi
```

**Long-context analysis with cache for re-runs.**
```bash
cat big-file.py prompt.md | strong --cache rw
```

**Background a long breadth job.**
Invoke via Bash with `run_in_background: true`; read stdout from the completion notification.
