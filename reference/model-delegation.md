<!-- keywords: delegate, delegation, model, sub-agent, sub-model, codex, deepseek, grader, breadth, fast, strong, gpt-5.5, gpt-5.3-codex-spark, deepseek-v4-flash, deepseek-v4-pro, orchestrator, orchestrate, fallback, quota, cache, multi-model, routing -->
# Model Delegation

How to delegate sub-tasks to other models from this Claude Code session.

You (Claude in this session) are the orchestrator. Sub-models are bash tools. Each sub-model is invoked via a wrapper that takes a self-contained prompt, returns text on stdout, and reports failure modes via exit code. The wrappers do not run agentic loops — you (the orchestrator) handle file reads, tool use, iteration. Sub-models reason on the prompt you give them and return text.

## Quick Nav

| Task | Section |
|------|---------|
| Pick which model for a task | Tier Sketch |
| See command flag reference | Wrapper Reference |
| Chain models on quota | Fallback Chain |
| Use cached responses | Caching |
| Read failure exit codes | Exit Code Contract |
| Write a self-contained prompt | Prompt Template |
| Long-running jobs (>10 min) | Long-Running Jobs |
| Bench data behind these picks | Empirical Latency / Quality |

## Tier Sketch

Pick the model based on what the task actually needs. Bench data (2026-04-29) below.

```
fast    gpt-5.3-codex-spark   FAST + STRONG. Default for code tasks.
                                    24-37s on hard tasks, ~strong quality.
                                    Use Spark credits aggressively.

strong  gpt-5.5               DEEPER. Use for: load-bearing logic, security
                                    review, hardest debugging, architecture decisions.
                                    27-166s. Higher quality on subtle reasoning.

grader      deepseek-v4-flash     CHEAP + FAST. Use for: summaries, simple
                                    fixes, non-code reasoning, when you want to
                                    spare codex quota. 43-110s.

breadth        deepseek-v4-pro       FALLBACK + VERBOSE. Use when both codex tiers
                                    are exhausted, or for thorough non-code
                                    reasoning. 168-363s — the slowest.
```

Be aggressive with fast. Spark is essentially free (ChatGPT subscription credits) and is the empirical winner on code tasks. Reserve strong for genuinely hard reasoning that benefits from deeper xhigh thinking. DS tier is the off-ramp when both codex tiers throttle.

## Wrapper Reference

All four wrappers share a near-identical interface. Differences noted below.

```bash
# Common flags
grader "prompt"                       # arg
grader --file prompt.md               # file
echo "prompt" | grader                # stdin
cat ctx.md prompt.md | breadth --max-tokens 32000

--file PATH         Read prompt from file (binary-safe)
--cache MODE        off | read | write | rw   (default off)
--timeout SECS      Max wall time (default 1800 = 30 min)
```

### DS-specific (grader, breadth)

```
--max-tokens N      Output budget. DEFAULT 16000. Reasoning eats 75-90% of this
                    before output appears — never go below 8000. Bump to 32000+
                    for long-form output or hard reasoning.
--system TEXT       Optional system message
--json              Emit full JSON response (with usage stats)
```

### Codex-specific (fast, strong)

```
--reasoning EFFORT  low | medium | high | xhigh   (default xhigh)
--raw               Emit full codex stdout including session header/footer
                    (default: stripped to model output only)
```

Codex wrappers do not accept `--max-tokens` — codex CLI handles it internally.

## Exit Code Contract

```
0   Success — read stdout for content
1   Usage error (your invocation has a bug; fix it)
2   API error (transient or permanent — read stderr)
3   Quota / rate limit (429) — fall back to next tier
4   Auth error — DEEPSEEK_API_KEY missing/wrong, or codex login expired
5   Silent failure — empty content despite no error.
    For DS: bump --max-tokens (reasoning ate the budget).
    For codex: prompt likely >8KB on non-TTY (issue openai/codex#19945).
```

You (the orchestrator) react on exit code, not message text. The contract is stable across all four wrappers.

## Fallback Chain

Sequential, not parallel. On exit 3 (quota), drop one tier:

```
strong (5.5)         exit 3   →   try fast
fast (Spark)         exit 3   →   try breadth
breadth                     exit 3   →   try grader
grader                   exit 3   →   surface to user; we're out
```

For exit 5 (silent), the recovery is different per family:
- DS exit 5: re-run with `--max-tokens 32000` or bigger
- Codex exit 5: shrink the prompt (likely >8KB) or try the other codex tier

Do **not** fan the same logical request out to all four in parallel — wastes tokens and creates ambiguous results.

## Caching

Opt-in, off by default.

```
--cache off       (default) no cache interaction
--cache read      hit cache if exists, else API call (no write)
--cache write     always API call, write result to cache
--cache rw        hit cache if exists, else API + write
```

Cache key: `sha256(model | system | prompt | max_tokens)` — any byte change is a cache miss. Cache files live at `~/.cache/delegate/<sha256>.txt`.

When to use:
- **`rw`** — repeating identical queries across iterations or sessions
- **`read`** — replaying a known-good response without API cost
- **`write`** — explicit refresh (force re-call, save new answer)
- **`off`** — exploratory work where the prompt mutates each call

Failure modes to avoid:
- **Stale embedded files**: if the prompt embeds file contents that have changed, re-embed before re-querying — cache is keyed on prompt text, not source file mtime.
- **Cache poisoning**: if a previous response was bad, `--cache read` will keep returning it. Use `--cache write` to overwrite.

DeepSeek also has its own server-side prompt cache (free, automatic). Stable prefixes (system prompt, embedded docs) hit at $0.003625/M vs $0.435/M for breadth — a 120× discount. Structure prompts so stable parts come first, variable user content last.

**Cache management — `delegate-cache` utility:**

```bash
delegate-cache stats              # dir, file count, total size, age range
delegate-cache list [--limit N]   # most-recent N entries (default 20) with age + size
delegate-cache clean [--older N]  # evict files older than N days (default 30)
delegate-cache clear              # wipe everything (asks for confirmation)
```

The local cache has no automatic eviction. Run `delegate-cache clean` periodically (e.g., monthly via cron) if you use `--cache rw` regularly.

## Prompt Template

Sub-models start fresh — no conversation memory, no shared context. Every prompt is self-contained and opens with an outcome block (Goal / Success / Stop), then a directional body. See global CLAUDE.md `## Prompt Authoring` and `/directional-prompting` skill for the underlying discipline.

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

**Why the outcome block matters for reasoning models**: strong / gpt-5.5-xhigh will refine past usefulness without an explicit `Stop when:` — they reason the task into perpetual revision. The stopping condition is what lets you keep `--timeout` off (per `feedback_no_codex_timeout`) while still bounding work; the model self-terminates on a criterion it can reason about, rather than being killed mid-flight by a wall clock.

**Why the directional body matters**: a `CONSTRAINTS: don't do X` line plants X as a concept the model now has to actively suppress on every token. A directional `TASK:` line where every sentence names the correct action gives the model a path to walk instead of a fence to avoid. Same constraint coverage, lower token cost, less drift. Reserve negation for the four legitimate cases (safety, near-identical-path disambiguation, large acceptable space, specific banned items).

**Why explicit format constraints**: reasoning models obey them reliably. Without them, breadth produces 5KB of bloat on a 200-byte question. With them, all four models produce comparable, terse outputs.

## Long-Running Jobs

Bash tool's 10-minute timeout is the only real constraint. Wrappers internally support 30-minute timeouts via `--timeout`.

**Background + auto-notify pattern (the right way for any job >10 min):**

Invoke the wrapper via Bash with `run_in_background: true`. The harness tracks the process and **automatically pushes a `<task-notification>` to you when it completes** — you do *not* poll, sleep, or check status. No idle waiting; no tokens burned on monitoring.

Workflow:
1. Issue the wrapper call with `run_in_background: true`. The Bash tool returns immediately with a task ID.
2. Continue with other work — read more files, dispatch other models, synthesize earlier results.
3. When the background job completes, you receive a system notification with the task ID and exit status.
4. Read the captured stdout from the notification's output file.

**Anti-pattern: chained polling loops.** Don't write `bash -c 'while pgrep -f X; do sleep 10; done; do_next'` — `pgrep -f` matches the wait shell's own command line and infinite-loops. If you need to chain, either (a) submit step 2 only after step 1's notification fires, or (b) use a sentinel-file pattern (step 1 writes `done.flag`; step 2 waits for that flag's existence). See `feedback_pgrep_self_match` memory.

**Empirical defaults from bench data:**
- fast / strong on simple prompts: 24-37s — foreground Bash is fine.
- grader on simple prompts: 6-110s — foreground usually fits.
- breadth on hard reasoning: 168-363s+ — use background.
- Any task with embedded long-context (>20KB) and `--max-tokens 32000+`: background.

## Empirical Latency / Quality

Bench: 3 tasks × 4 models × 1 run, 2026-04-29. All `--max-tokens 32000`.

| Task | grader | breadth | fast | strong |
|------|----------|--------|------------|--------------|
| Hard reasoning (rate limiter design) | 110s / 9.5KB | 363s / 15KB | **24s / 18KB** | 166s / 12KB |
| Long-context (33KB doc analysis) | 43s / 2.7KB | 168s / 4.5KB | **24s / 3.7KB** | 27s / 3.7KB |
| Long-form output (5K word writeup) | 101s / 28KB | 313s / 38KB | **37s / 39KB** | 161s / 30KB |

Quality (qualitative spot-check on the rate-limiter task):
- **fast**: richest types (Decision dataclass, Protocol classes for sync/async Redis), generic Lua dispatch, frozen dataclasses. Best balance.
- **strong**: comparable to fast in code structure; deeper on edge cases. Worth the latency on subtle bugs.
- **breadth**: TypedDict (less type-safe), bool returns (loses metadata), simpler. Verbose but lower architectural polish.
- **grader**: solid but loses detail on subtle requirements (e.g., distinguishing all-negative-array case in earlier bug-finding bench).

Bench tasks live in `/tmp/delegate-bench/tasks/`. Re-run with `bash /tmp/delegate-bench/run-matrix.sh` after model updates to refresh the table. Move to `~/scratch/delegate-bench/` if you want to persist across reboots.

## Failure Modes Caught (from research)

Documented gotchas across the four wrappers:

1. **Codex silent crash on prompts >8KB** (issue openai/codex#19945): non-TTY stdin + large prompt → exit 0 with empty stdout. Codex wrappers warn at >8KB and detect empty content as exit 5.
2. **Codex emits 400 errors with exit 0**: invalid model / 400 responses appear as `ERROR: {"status":400,...}` lines in stdout but exit 0. Codex wrappers grep for `^ERROR: \{.*"status":[45][0-9]{2}` and convert to exit 2.
3. **DS reasoning models eat max_tokens**: 75-90% of completion budget goes to hidden reasoning. `max_tokens=10` returns empty content with `reasoning_tokens=10`. Default 16K, recommend 32K for hard work.
4. **bc not installed on your OS**: bench script originally used `bc` for float arithmetic; falls back to integer-second timing.
5. **Quota detection on codex**: rate-limit string is `"exceeded retry limit, last status: 429"` — wrappers grep for this and exit 3.

## Examples

**Get a quick code review on a function.**
```bash
cat my_function.py | grader --max-tokens 8000 \
  "Find any bugs in the code below. Output: bug list, then fixed code. Terse."
```

**Hard architecture question.**
```bash
strong --file design-prompt.md --reasoning xhigh
```

**Repeated identical query (e.g., during workflow iteration).**
```bash
fast --file plan.md --cache rw
```

**Fallback chain in pseudocode (you, the orchestrator, run this logic):**
```bash
strong --file prompt.md
if [ $? -eq 3 ]; then fast --file prompt.md; fi
if [ $? -eq 3 ]; then breadth --file prompt.md --max-tokens 32000; fi
if [ $? -eq 3 ]; then grader --file prompt.md --max-tokens 32000; fi
```

**Long-context analysis with cache for re-runs.**
```bash
cat big-file.py prompt.md | strong --cache rw
```

**Background a long breadth job.**
Invoke via Bash with `run_in_background: true`; read stdout from the completion notification.
