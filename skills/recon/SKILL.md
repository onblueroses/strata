---
name: recon
description: Three-wave reconnaissance protocol that builds a verified knowledge brief before non-trivial planning, design, debugging, or architecture work. Run this when planning quality is bounded by information quality — before /spec, /hammock, a debugging hypothesis that gates real implementation, an architecture decision, or any multi-file refactor where the path isn't obvious. Wave 1 fans wide for breadth, Wave 2 verifies load-bearing claims and tests seams, Wave 3 synthesizes the merged corpus from two complementary framings. Output is one merged brief written to a known path, ready for the next planner or skill to consume. Auto-trigger when the user is about to design, plan, refactor, or debug something non-trivial and the codebase isn't already in working memory; also trigger when the user says "recon", "scout", "let me understand X first", "investigate before deciding", "research the codebase for", or asks to verify load-bearing claims about repo state. Skip for trivially-scoped work (1-2 files, obvious path) — direct Glob/Grep/Read is faster.
---

# Recon

Three-wave reconnaissance that hands the next planner a verified brief instead of vibes.

```
Goal: Produce one merged recon brief — confirmed facts (with file:line citations),
      surfaced contradictions, remaining gaps, and the 3-5 highest-leverage things
      the next planner must know — written to a known path.

Success means:
  - Brief written to $RUN_DIR/brief.md (path returned to caller)
  - Every confirmed fact carries a file:line citation that resolves on disk
  - Contradictions between Wave 1 reports are surfaced with both citations
  - Remaining gaps are listed (the planner needs to know what recon could not verify)
  - Every load-bearing Wave 1 claim was either verified in Wave 2 or marked unverified
  - Validation gate passed: schema present, statuses recorded, spot-checked citations resolve

Stop when: the validated brief is written and its path is returned.
```

## Model policy

This skill dispatches every reconnaissance wave through codex tiers exclusively. The asymmetry between Wave 1/2 (breadth, cheap, parallel) and Wave 3 (synthesis, judgment, fires twice) is the load-bearing structural choice.

| Wave | Wrapper | Underlying | Role | Why this tier |
|------|---------|------------|------|---------------|
| 1 — Wide fan | `fast` | fast-lane model | Breadth scouting, one domain per spark | the fast lane is cheap and parallel; quality matches strong on focused factual queries; parallelism is the design |
| 2 — Probes | `fast` | fast-lane model | Verify load-bearing claims, test seams | Targeted, citation-bound; depth comes from the seam logic, not the model |
| 2 — Probes (escalated) | `strong` | strong-lane model (high reasoning) | Risky-seam probes only | Escalate one specific probe to the strong lane when the seam touches auth, concurrency, data integrity, schema migration, or cross-language boundaries |
| 3 — Synthesis | `strong` | strong-lane model (high reasoning) | Read merged corpus, name what's missing and what's wrong | Judgment work over a large context; the strong lane self-terminates on the stopping condition |

**Scope of the codex-only rule.** The rule covers wave dispatches — the reconnaissance signal must come from codex so the synthesis sees a coherent voice. Use Claude's native tools (Read, Glob, Grep, Bash, Write) freely for orchestration: composing the corpus, writing prompt files, validating citations, merging the brief. The next planner downstream consumes the brief under its own model policy (Opus, codex, whatever `/spec` or `/hammock` chooses) — recon's job ends at the brief.

**Throttle fallback — codex-only chain.** On exit 3 (quota):
- `strong` → retry the same prompt on `fast` and tag the brief `Wave 3 ran on Spark due to quota`
- `fast` → surface to user and stop; a degraded brief is worse than no brief

Skip breadth, grader, and Claude subagent fallbacks — mixing models defeats the consistency this protocol depends on.

**Skip `--timeout` on every call.** The Goal/Success/Stop block in each dispatched prompt is what bounds work — strong xhigh self-terminates on the stopping condition the prompt names, and a wall-clock timeout kills runs mid-flight. The orchestrator imposes a separate hang-detection deadline at the dispatch layer (see Sentinel-file dispatch pattern below), which catches stuck wrappers without truncating productive reasoning.

## Spot checks (multi-level)

Spot checks are how recon stays honest against an LLM's natural drift toward plausible-sounding citations. The protocol installs them at four levels, each cheap, each catching a different failure mode:

| Level | Who runs it | What it checks | Failure mode it catches |
|-------|-------------|----------------|-------------------------|
| L1 — Spark self-check | Every Wave 1 / Wave 2 spark, before writing each bullet | "I opened the cited file and the cited line says what I'm about to claim" | Hallucinated citations, fabricated line numbers, vibes-based claims |
| L2 — Wave 2 premise verification | Dedicated Wave 2 probes | "The 2-3 most load-bearing Wave 1 claims are verified against current code" | Inherited-premise decay: Wave 1 was true once but is wrong now |
| L3 — Wave 3 synthesis cross-check | Both Wave 3 instances during merge | "Confirmed facts agree across A and B, or have explicit Wave 2 backing, or have spot-checked citations" | Synthesis hallucination — Wave 3 promotes plausible-sounding aggregates |
| L4 — Orchestrator validation gate | Claude-native, before returning brief | "3-5 sampled citations from the merged brief resolve and say what the brief claims" | Anything that slipped through L1-L3 |

Each level operates on a smaller, more important set than the one below: every spark bullet (hundreds across the protocol) → load-bearing Wave 1 claims (2-3) → merged confirmed facts (10-30) → sampled citations (3-5). The cost compounds at the right end of the distribution.

The `SPOT_CHECK_COUNT: N` trailer on every Wave 1 and Wave 2 spark output is a self-attestation, not a verifiable check. The validation gate (L4) is what actually verifies. The trailer is still useful: when a spark reports `SPOT_CHECK_COUNT: 0` or `SPOT_CHECK_COUNT: 1`, the orchestrator should re-dispatch with stronger spot-check emphasis. When a spark consistently reports `N == bullet_count`, the prompt is landing correctly.

## Customization seams

Recon is a scaffold with defaults — calling orchestrators should adapt it to the specific topic. The skill produces better briefs when targeted than when run on autopilot. Every extension point below is a documented place to intervene.

| Seam | Default | When to customize | How to customize |
|------|---------|-------------------|------------------|
| **Wave 1 domains** | The canonical 6 (architecture, constraints, prior-art, gotchas, external-deps, tests-ci) | When the topic targets a specific subsystem or behavior (auth flow, cache path, deploy pipeline, payment integration) | Add topic-specific domains (e.g. `session-storage`, `eviction-policy`, `webhook-handlers`, `idempotency-keys`); drop canonical ones that don't apply. See Wave 1 "Custom domains" table. |
| **Spark count** | 4-6 Wave 1, 2-6 Wave 2 | When the surface is narrow (1 file) or unusually broad (8+ subsystems) | Drop to 2-3 sparks for tight topics; expand to 8 for genuinely broad recon. Each domain must still produce 5-15 bullets — sub-3 means fold domains together. |
| **User notes / focus / scope** | Empty | Always when the calling orchestrator knows something topic-specific the sparks should attend to | Fill the `User notes (optional focus / scope / hints / exclusions)` slot in the spark CONTEXT block: hotspots, paths to ignore, suspected failure modes, time-window for git history, prior failed hypotheses, related PR numbers, anything. **This is where targeting happens.** |
| **Context bundle composition** | The 10-row Wave 0 table | When the topic touches a known entity, an active spec, or a recent incident | Wave 0 chooses which bundle entries apply; the calling orchestrator can pre-populate with specific files (e.g. an incident postmortem, a security audit log, a vendor SDK changelog) that the bundle's defaults wouldn't surface |
| **Wave 2 probe selection** | Calling orchestrator picks 1-3 load-bearing claims + 1-3 seams | Always | Pick by load-bearing-ness for the next decision — what claim, if wrong, breaks the plan. Pick seams by where Wave 1 reports touched the same files/concepts. |
| **Wave 2 escalation** | fast for probes | When a seam touches auth, concurrency, data integrity, schema migration, or cross-language boundaries | Dispatch that specific probe to strong instead. Per-probe choice; the rest stay on fast. |
| **Wave 3 framings** | "name what's missing" + "name what's wrong" | When the topic is not general planning (e.g. security review, performance investigation, merge-safety check) | Substitute framings that match the next decision: "what would break under load + what's the latency p99 risk"; "what's the threat-model gap + what's the privilege boundary"; "what's the merge-conflict risk + what's the rollback path". Keep the dyadic shape (one positive, one negative framing) so the merge protocol stays applicable. |
| **Wave subset** | All three waves | When you need cheap surface scan (Wave 1 only) or are following up an earlier recon brief (Wave 2 only against a prior brief's claims) | Run Wave 1 only and skip merge; the brief is just confirmed-facts + gaps. Or run Wave 2+3 starting from an existing brief and treat its claims as the corpus. |
| **Validation gate strictness** | 3-5 sampled citations, all 4 checks | When the recon feeds high-stakes work (security review, irreversible migration, public API design) | Sample 10+ citations instead of 3-5; demand every Top-must-know to have at least 2 supporting bullets across Wave 1/2 reports |
| **Output schema slots** | Default Output schema | When the consuming planner has a specific format need | Add planner-specific sections (e.g. "Open questions for human", "Resources to read before starting") — keep the canonical sections so generic planners still work |

The calling orchestrator should make these choices in Wave 0 (along with slug, repo root, domain selection) and record them in `$RUN_DIR/scope.md` so the recon's provenance shows what was tuned for this run.

## Run directory and naming

Every recon creates one isolated run directory. Two sessions reconing the same topic at the same time stay completely separate.

```bash
SLUG="<derived-from-topic>"        # e.g. SLUG="auth-service-split"
RUN_DIR=$(mktemp -d -t "recon-${SLUG}-XXXXXX")
```

All wave prompts, outputs, sentinels, corpus, and the final brief live under `$RUN_DIR`. The final brief gets symlinked or copied to `/tmp/recon-${SLUG}.md` for caller convenience; the run dir stays as the audit trail.

**Note on placeholders.** Curly-brace tokens in this skill's code snippets (e.g. `{slug}`, `{domain}`, `{topic}`) are template placeholders to substitute before executing — `$SLUG`, `$RUN_DIR`, and concrete domain ids should appear in the actual command. Read them as `${VAR}` in your head.

**Caching for repeated recon.** When the same slug runs again within a few hours (revisiting the same topic, retrying after a clarification, parallel branches of investigation), append `--cache rw` to the fast Wave 1/2 dispatches. The wrapper keys on `sha256(model | prompt)`, so identical prompts hit cached responses for sub-cent cost. Skip `--cache` for Wave 3 (the corpus changes each run) and skip it when the repo has likely moved (compare `git rev-parse HEAD` before reusing).

**Shell-safe identifiers.** Domain names in Wave 1 contain spaces and `&` ("Architecture & file map"). Map each domain to a slug-style `domain_id` before using it in a path:

| Domain | `domain_id` |
|--------|-------------|
| Architecture & file map | `architecture` |
| Constraints & conventions | `constraints` |
| Prior art & decisions | `prior-art` |
| Gotchas & failure modes | `gotchas` |
| External dependencies | `external-deps` |
| Test/CI surface | `tests-ci` |

Quote every path expansion in dispatch commands (`"$RUN_DIR/..."`).

## Sentinel-file dispatch pattern

Background-launched codex calls lose their exit code by default. To preserve it, wrap each call so the exit code lands in a `.status` file. The orchestrator polls `.status` files (which appear only after the call completes) and branches on the value.

```bash
( fast --file "$RUN_DIR/w1-architecture.prompt.md" > "$RUN_DIR/w1-architecture.out" 2>&1
  echo $? > "$RUN_DIR/w1-architecture.status"
) &
```

Repeat per spark. After dispatching the wave, wait on `.status` files using the Monitor tool (preferred) or a bounded sentinel-poll loop. Wait via Monitor or `wait $!` against tracked PIDs; the naked `pgrep -f PATTERN` busy-loops because the polling shell matches itself (see `feedback_pgrep_self_match`).

**Bundled helper — prefer this over assembling the inline pattern from scratch.** The skill ships `scripts/dispatch_wave.sh` at `$STRATA_HOME/skills/recon/scripts/dispatch_wave.sh`. It encodes the sentinel-file pattern with the deadline checks below and was tested end-to-end against fast and strong wrappers (see `examples-e2e-saa-agent-api/`). Invoke it as:

```bash
bash $STRATA_HOME/skills/recon/scripts/dispatch_wave.sh \
  --run-dir "$RUN_DIR" --wave w1 --wrapper fast \
  --deadline 1800 --no-progress 300 \
  "$RUN_DIR/w1-architecture.prompt.md" \
  "$RUN_DIR/w1-constraints.prompt.md" \
  "$RUN_DIR/w1-prior-art.prompt.md"
```

Outputs land at `$BASE.out`, exit codes at `$BASE.status`, pids at `$BASE.pid`. The script exits with the worst child code seen — `0` all clean, `3` at least one quota, `124` at least one timed out, other for an arbitrary non-zero exit. Use the script's exit code to branch on the Throttle fallback rules above. For strong waves (Wave 3), pass `--deadline 1800 --no-progress 600`; xhigh runs can sit on a single token chain for 5+ minutes without writing the status sentinel.

Monitor pattern for one wave (used when running the dispatch inline rather than via the helper):

```bash
# Emit one event per spark completion + any non-zero exit. Two deadlines:
#   DEADLINE_SECS — overall wave wall-clock cap (e.g. 1800s)
#   STALL_SECS    — fire if no new .status file appears within this window (e.g. 300s)
START=$(date +%s)
LAST_DONE=0
LAST_PROGRESS=$START
DEADLINE_SECS=1800
STALL_SECS=300
TOTAL=NUMBER_OF_SPARKS
while sleep 5; do
  NOW=$(date +%s)
  DONE=$(ls "$RUN_DIR"/w1-*.status 2>/dev/null | wc -l)
  if [ "$DONE" -gt "$LAST_DONE" ]; then
    LAST_DONE=$DONE
    LAST_PROGRESS=$NOW
  fi
  for f in "$RUN_DIR"/w1-*.status; do
    [ -f "$f" ] || continue
    code=$(cat "$f")
    if [ "$code" != "0" ]; then echo "FAIL $f $code"; fi
  done
  if [ "$DONE" = "$TOTAL" ]; then echo "ALL_DONE"; break; fi
  if [ $((NOW - START)) -gt $DEADLINE_SECS ]; then echo "DEADLINE_EXCEEDED"; break; fi
  if [ $((NOW - LAST_PROGRESS)) -gt $STALL_SECS ]; then echo "NO_PROGRESS"; break; fi
done
# On DEADLINE_EXCEEDED or NO_PROGRESS, write a synthetic .status=124 (timeout) for every
# missing spark so the next-wave branch sees a uniform shape.
for f in "$RUN_DIR"/w1-*.prompt.md; do
  s="${f%.prompt.md}.status"
  [ -f "$s" ] || echo 124 > "$s"
done
```

On `ALL_DONE` (or the deadline branch), inspect every `.status` file and branch:
- Every `.status` is `0` → proceed to the next wave
- Any `.status` is `3` → throttle fallback per Model policy
- Any `.status` is `124` (synthetic timeout) → mark the spark unverified and continue with reduced coverage; flag the gap in the brief
- Any other non-zero → re-dispatch the failed spark once, mark unverified on second failure

## When to run

Run the full protocol when the next step is non-trivial planning, design, or debugging:

- `/spec` for any Full-weight spec (3+ files, multi-phase)
- `/hammock` design or planning session on an unfamiliar surface
- Architecture decision (framework choice, refactor strategy, schema change)
- Debugging hypothesis that will gate non-trivial implementation
- Pick-up on an entity after a long pause where the codebase has likely drifted
- Any moment the user asks to "understand X first" or "verify before deciding"

Skip the protocol when scope is small enough that direct exploration wins:
- 1-2 files with an obvious path
- The relevant code is already fully loaded in this session's working memory
- The user's question is a lookup, not a decision

The honest signal that recon was wrong for the task is "the protocol took longer than the work would have". Note it for next time and recalibrate the skip threshold upward.

`/spec` invokes this protocol internally — when called from `/spec`, this skill is the canonical source for what the spec workflow runs. Standalone `/recon` covers everything else.

## Recon scope

Recon stops at the validated brief. The brief is input to the next step; the next step happens elsewhere.

- Writing the plan, spec, or architecture decision — the planner consumes the brief
- Running `/codex-review` on the brief — the planner decides if/when to review its own plan
- Making product decisions — recon surfaces contradictions, the human or planner resolves them
- Implementing the work — recon precedes implementation by definition
- Long-form research outside the repo — use `/research` or `/evaluate` for that

Holding these boundaries keeps the protocol cheap and reusable. When a wave's output drifts into solutions, re-prompt the spark with the outcome block and stop condition so it returns observations only.

## Wave 0 — Scope check + context bundle (Claude-native, no codex call)

Before firing any sparks, run a quick orientation pass to lock the scope **and assemble the context bundle that every Wave 1 spark will receive**. The bundle is what makes a generic protocol adapt to a specific session, project, and topic — without it, every recon starts from a blank slate.

**Scope steps:**

1. **Pick the slug.** Lowercase-hyphenated, derived from the most concrete noun the user named. "Recon the auth stuff" → `auth`; "scout the rate-limit retry path" → `rate-limit-retries`. When the topic names two equally-concrete things, pick one and tag the second as a follow-up.
2. **Locate the repo root.** `git rev-parse --show-toplevel` from the working directory, or use the explicit path the user named.
3. **Pick Wave 1 domains.** Start from the canonical 6 (architecture, constraints, prior-art, gotchas, external-deps, tests-ci) and **add topic-specific domains** that target the actual subsystem under recon — `session-storage`, `eviction-policy`, `webhook-handlers`, `query-shape`, `idempotency-keys`, whatever the topic demands. Drop canonical domains that won't produce content for this topic. The right partition is 4-8 narrow lanes; each must have enough material for 5-15 bullets. See Wave 1 "Custom domains" table for worked examples. Custom domain selection is the single highest-leverage customization the orchestrator makes.
4. **Surface one clarifying question only when scope is truly ambiguous.** When the user says "recon the auth stuff" and the repo has both `web/auth` and `mobile/auth`, ask which (use `/ask-better` first). When the codebase is small or one path is obviously right, proceed.
5. **Create `$RUN_DIR`.** All wave artifacts live here.

**Context bundle** — Wave 0 also collects these inputs into `$RUN_DIR/context.md` so every spark receives a consistent, session-aware briefing:

| Input | Always or topic-conditional | Why it matters |
|-------|-----------------------------|----------------|
| Repo root + `git rev-parse HEAD` + branch | Always | Pins the snapshot the recon is grounded in; spot-checks during validation rebase to this SHA |
| Project entity summary (`$KB_DIR/projects/<entity>/summary.md`) | When the repo maps to a known entity | Gives the spark prior context (architecture, deploy procedure, gotchas, recent sessions) without re-deriving |
| `$KB_DIR/projects/<entity>/items.json` relevant entries | When entity exists | Structured details (specific values, rules, gotchas not in summary) |
| Active spec for this project (`$SPECS_DIR/*` matching project) | When an active spec exists | Decisions table + Standing Rules already encode constraints the spark should respect |
| Repo's CLAUDE.md / AGENTS.md / .agent.md | When present at repo root | Project-specific rules for collaborators; sparks should honor them |
| `$KB_DIR/resources/decision-library.md` filtered to topic keywords | Topic-conditional | Prior architectural decisions that might apply |
| Prior recon brief at `/tmp/recon-${SLUG}*.md` from previous session | When present | Update-mode recon; flag deltas instead of re-reasoning everything |
| `git log --oneline -20 -- <topic-relevant-paths>` | When topic localizes to clear paths | Recent change history grounds "what just changed" |
| Today's daily note JSON (`$KB_DIR/daily/<date>-*.json`) | When session has built up topic-relevant notes | Captures the user's current focus and constraints from this session |
| Session edits log (`.session-edits-<sid>.jsonl`) for files in topic scope | When session has touched topic files | What this session has already changed; recon should account for those edits |

Glob, Read, and Bash freely to assemble these. Skip inputs that aren't relevant — bundling everything bloats the spark context for no value. The bundle is for orienting the spark, not feeding it the answer.

**Output of Wave 0:** `$RUN_DIR/context.md` (the bundle), `$RUN_DIR/scope.md` (slug, topic statement, selected domains, clarifying-question result), and a clean `$RUN_DIR` ready for Wave 1.

Wave 0 is Claude's native work — Read, Glob, Bash, git. No codex call. Wave 0 typically takes 1-3 minutes; that latency is the price of every spark getting an oriented briefing instead of a blank slate.

## Wave 1 — Wide fan (4-6 parallel fast sparks)

Fire 4-6 `fast` sparks in parallel, one per selected domain. Each spark returns a focused bullet report with **file:line citations** for every claim.

Canonical domains (pick 4-6 that apply):

- **Architecture & file map** (`architecture`) — files that exist, how they connect, entry points, naming conventions
- **Constraints & conventions** (`constraints`) — applicable CLAUDE.md rules, project-specific style, framework idioms, lint/build rules that will fire on this work
- **Prior art & decisions** (`prior-art`) — ADRs, decision logs, project summaries, recent commits or specs touching this area
- **Gotchas & failure modes** (`gotchas`) — known bugs, hooks that will fire, edge cases the codebase already handles, dead ends previously hit
- **External dependencies** (`external-deps`, when relevant) — APIs, schemas, third-party docs the work touches
- **Test/CI surface** (`tests-ci`, when relevant) — existing test patterns, CI gates, validation commands

**Custom domains — this is the scaffold, not a cage.** The canonical 6 are general-purpose defaults for "Full-weight spec" planning. Recon usually targets a specific kind of issue; the calling orchestrator should add domains that match the topic and drop ones that don't apply. The right Wave 1 partition is the one that gives fast a clear, narrow lane per spark — not the one that fits the table above.

Worked examples of topic-specific domain sets:

| Topic | Use these domains | Drop these |
|-------|-------------------|------------|
| "OAuth callback dropping state param" | `routing`, `session-storage`, `middleware-order`, `oauth-lib-internals`, `gotchas`, `tests-ci` | architecture (too broad), external-deps (covered by oauth-lib-internals), constraints |
| "Redis caching path is slow" | `cache-key-schema`, `eviction-policy`, `connection-pooling`, `serialization`, `metrics-surface`, `gotchas` | architecture, constraints, prior-art (unless ADR exists) |
| "Adding a new payment provider" | `payment-abstraction`, `webhook-handlers`, `idempotency-keys`, `retry-semantics`, `constraints`, `tests-ci`, `external-deps` | architecture (too broad), gotchas (covered by specific domains) |
| "Tool extension surface for plugin authors" | `architecture`, `tool-registration`, `type-coercion`, `error-contract`, `prior-art`, `gotchas` | constraints, tests-ci |
| "Why is the daily report job timing out" | `job-entry-point`, `query-shape`, `pagination`, `lock-contention`, `recent-deploys`, `metrics-surface` | architecture, prior-art, tests-ci |

Naming guidance for custom domains: keep them shell-safe `domain_id` (lowercase-hyphenated), keep the human-readable name in the spark's CONTEXT block. Each domain must have *enough content to fill 5-15 bullets* — if a candidate domain would produce 2 bullets, fold it into a neighbor instead.

**Spark prompt template** (one per domain, written to `$RUN_DIR/w1-{domain_id}.prompt.md`). Every clause is load-bearing — these were tuned against real fast runs (see `examples/` section for the E2E that produced them).

```
Goal: Surface every fact relevant to {topic} for the {domain} domain in this repo.

Success means:
  - 5-15 bullets between the `## BULLETS:` and `## SPOT_CHECK_COUNT:` markers
  - Every bullet carries a file:line citation (or external URL for external deps) AND a concrete behavior, not a vague reference
  - Every bullet has an epistemic prefix: (verified) (inferred) (unverified)
  - Output is observation only — pure facts, no recommendations, no design opinions
  - Output opens with the `## BULLETS:` marker. Skip any "I'll do X" preamble; it adds parse noise downstream.

Stop when: the `## SPOT_CHECK_COUNT:` line is written.

CONTEXT:
- Repo root: {absolute path}
- Repo HEAD: {git rev-parse HEAD short SHA, so the spark and the merge agree on snapshot}
- Topic: {one sentence}
- Domain framing: {human-readable name + one-line description of this spark's lane — e.g. "session-storage — how session tokens are written, read, and invalidated across web/mobile auth flows"}
- Sibling Wave 1 domains in flight: {list — so this spark stays inside its lane}
- User notes (optional focus / scope / hints / exclusions from the calling orchestrator): {free-form text from the caller — specific files to start from, paths to ignore, suspected hotspots, prior failed hypotheses to avoid retreading, time-window for recent commits, whatever the caller knows that should shape the search. Leave empty when the calling orchestrator has nothing topic-specific to add. This slot is where targeting happens.}
- Project bundle (from $RUN_DIR/context.md): {paste relevant excerpts — entity summary, repo CLAUDE.md, active spec decisions, prior recon delta, recent commits}

TASK:
Read the repo. Trace {domain}-relevant files. For every claim:
1. Read the cited file at the cited line BEFORE writing the bullet.
2. State what the code DOES, not what it's called (`agent.py:248 — Agent.run(task, *, memory=None) returns AgentResult` beats `agent.py — defines run method`).
3. Cite by file:line, not by quoting the code block; the consumer will Read the file directly if they need the source. Quoting raw code wastes the corpus budget.
4. Prefix the bullet with its epistemic status:
   - `(verified)` — you read the file at the cited line and the bullet matches what's there
   - `(inferred)` — the bullet generalizes from what you read; add a one-clause reason
   - `(unverified)` — you tried to verify and could not; state the specific reason

OUTPUT FORMAT (exactly this shape, no surrounding prose):
## BULLETS:
- (verified) `path/to/file.ext:LN` — concrete behavior or fact
- (verified) `path/to/other.ext:LN` — concrete behavior or fact
- (inferred) `path/to/file.ext:LN` — generalized claim. Reason: <one clause>
- (unverified) external URL or assumption — claim. Reason grounding failed: <one clause>
## SPOT_CHECK_COUNT: N
```

Dispatch each spark via the sentinel-file pattern above. Wait via Monitor or sentinel poll. Branch on `.status` codes per Throttle fallback.

The `## BULLETS:` / `## SPOT_CHECK_COUNT:` markers make the output machine-parseable for the corpus assembly step. The epistemic prefixes feed directly into the merge protocol's confirmed/unverified split — sparks doing the labeling at the source beats the synthesis stage trying to infer it.

## Wave 2 — Overlapping probes (2-6 parallel fast sparks)

Wave 2 has two flavors; run **1-3 of each**, totaling 2-6 sparks:

**Premise verification probes (1-3 sparks).** Select the 1-3 most load-bearing Wave 1 claims — the ones the next plan will rest on (e.g., "`X` exports `Y`", "`Z` is implemented at `file:line`", "the route uses middleware `M`"). Dispatch one spark per claim to confirm against current code.

Premise probe template (written to `$RUN_DIR/w2-premise-{n}.prompt.md`):

```
Goal: Confirm or refute one specific claim from Wave 1 against the current code at $HEAD.

Success means:
  - Output opens with the `STATUS:` line. Skip any "I'll check this" preamble.
  - Status is one of CONFIRMED, CONTRADICTED, UNVERIFIED
  - CONFIRMED: the claim matches what the cited file says at the cited line
  - CONTRADICTED: the file at the cited line says something different; cite what it actually says
  - UNVERIFIED: state the specific reason grounding failed (file moved, line wrong, ambiguous, requires runtime)

Stop when: the EVIDENCE line is written.

CONTEXT:
- Repo root: {absolute path}
- Repo HEAD: {short SHA}
- Wave 1 claim under test: "{quoted Wave 1 bullet, including original citation and epistemic prefix}"
- Wave 1 source spark: {domain_id}

TASK:
1. Read the cited file at the cited line range. Read 5 lines before and 5 after for context.
2. Compare what's there to the claim. Be literal — "uses X" should match what the code actually does, not what it could be interpreted as doing.
3. When the cited line has moved (file was reorganized since Wave 1), search for the function/symbol name and report STATUS: CONTRADICTED with the new location.

OUTPUT FORMAT (exactly this shape):
STATUS: CONFIRMED | CONTRADICTED | UNVERIFIED
EVIDENCE: `path:LN` — what the code actually does or says at this line
NOTE: <optional one-clause clarification, e.g. "claim is essentially correct but line moved to 251 in current HEAD">
```

**Seam probes (1-3 sparks).** Identify intersections where Wave 1 reports touched the same files or concepts. Dispatch one spark per seam to test how the pieces actually interact.

Seam probe template (written to `$RUN_DIR/w2-seam-{n}.prompt.md`):

```
Goal: Test how {component A} and {component B} actually interact in this repo at $HEAD.

Success means:
  - Output opens with the `## BULLETS:` marker
  - 3-7 bullets, each a verified observation about the seam with file:line citations
  - Every bullet has an epistemic prefix: (verified) (inferred) (unverified)
  - Output ends with a `SUMMARY:` line classifying the seam
  - Output ends with `## SPOT_CHECK_COUNT: N`

Stop when: SPOT_CHECK_COUNT is written.

CONTEXT:
- Repo root: {absolute path}
- Repo HEAD: {short SHA}
- Wave 1 claim from {report A id}: "{quote with citation}"
- Wave 1 claim from {report B id}: "{quote with citation}"

TASK:
1. Read both citation sites and the code that connects them (imports, call graph, shared state).
2. Trace one full path from A to B (or B to A) — what actually happens at runtime.
3. Test whether the two Wave 1 reports describe the same thing, complementary things, or contradicting things.
4. Quote behavior, not code blocks.

OUTPUT FORMAT (exactly this shape):
## BULLETS:
- (verified) `path:LN` — observation about the seam
- (verified) `path:LN` — observation
- (inferred) `path:LN` — generalized claim. Reason: <one clause>
SUMMARY: holds | leaks: <describe> | contradicts: <describe>
## SPOT_CHECK_COUNT: N
```

**Escalation rule.** When a seam touches authentication, concurrency, data integrity, schema migration, or a cross-language boundary, dispatch that specific probe to `strong` instead of `fast`. The xhigh depth earns its latency on these classes; everywhere else, Spark is the right tier.

## Wave 3 — Synthesis review (2 parallel strong instances)

Concatenate the Wave 1 + Wave 2 outputs into a single corpus file. This typically runs 20-80KB — file-based dispatch is mandatory.

Build the corpus using Claude-native tools:

```bash
{
  echo "# Recon Corpus — {slug}"
  echo
  for f in "$RUN_DIR"/w1-*.out; do
    echo "## $(basename "$f" .out)"
    cat "$f"
    echo
  done
  for f in "$RUN_DIR"/w2-*.out; do
    echo "## $(basename "$f" .out)"
    cat "$f"
    echo
  done
} > "$RUN_DIR/corpus.md"
```

Write two prompt files with complementary framings:

**`$RUN_DIR/w3-missing.prompt.md`** — Instance A, "Name what's missing":

```
Goal: Read the recon corpus for {slug} and name what's missing that the
      next planner will need but does not have.

Success means:
  - Output OPENS with the literal text `## Confirmed facts` on the first line of your response
  - Confirmed facts collated (union across Wave 1 + Wave 2) with citations preserved
  - 3-5 gaps named, each tied to a specific planning decision that goes wrong without it
  - Top 3-5 highest-leverage things the planner must know, ranked
  - The merge step grep-extracts from `^## Confirmed facts` to end-of-output, so any preamble
    before the section header is wasted tokens and noise. Open with the section header.

Stop when: the brief is written.

CORPUS:
{paste contents of $RUN_DIR/corpus.md here}

OUTPUT FORMAT (your response must start with `## Confirmed facts` — no preamble):
## Confirmed facts
- `path:LN` — claim
## Gaps
- gap description — planning decision that depends on it
## Top must-knows (ranked)
1. fact or constraint
```

**`$RUN_DIR/w3-wrong.prompt.md`** — Instance B, "Name what's wrong":

```
Goal: Read the recon corpus for {slug} and name what's wrong, contradictory,
      or unverified.

Success means:
  - Output OPENS with the literal text `## Confirmed facts (independently collated)` on the first line of your response
  - Confirmed facts collated independently (separate union — so the merge can compare)
  - Every contradiction between Wave 1 reports surfaced with both citations
  - Every UNVERIFIED status from Wave 2 carried forward
  - Top 3-5 highest-risk assumptions the planner is about to make, ranked
  - The merge step grep-extracts from `^## Confirmed facts` to end-of-output, so any synthesis
    preamble before the section header is wasted tokens. Open with the section header.

Stop when: the brief is written.

CORPUS:
{paste contents of $RUN_DIR/corpus.md here}

OUTPUT FORMAT (your response must start with `## Confirmed facts (independently collated)` — no preamble):
## Confirmed facts (independently collated)
- `path:LN` — claim
## Contradictions
- topic — Wave 1 A said X (`a:LN`); Wave 1 B said Y (`b:LN`); seam probe found Z (`c:LN`)
## Unverified premises
- claim — reason grounding failed
## Top riskiest assumptions (ranked)
1. assumption — what breaks if wrong
```

Dispatch both via the sentinel pattern. Branch on the Wave 3 statuses before merging:

- **Both `.status` = 0** → proceed to the full merge protocol below
- **One `.status` = 0, the other `.status` ≠ 0** → run a single-instance degraded merge: take the surviving instance's output verbatim, tag the brief `Wave 3 partial — single-framing synthesis (Instance A only / Instance B only)`, downgrade ranked items (top must-knows / top risks) by one tier in the planner's eyes, set Validation to `PARTIAL`, and continue
- **Both `.status` ≠ 0** → recon fails; surface to user with the Wave 3 `.out` contents and the exit codes

## Merge protocol (both Wave 3 instances succeeded)

Treat the two Wave 3 outputs as complementary, not symmetric, and merge deterministically. Each section below names the source of truth and how Wave 2 evidence feeds in.

**Confirmed facts.** Promote a fact to *confirmed* in the merged brief when at least one holds:
- (a) Both Instance A and Instance B independently listed it (independent agreement)
- (b) Wave 2 returned `STATUS: CONFIRMED` for it (active verification)
- (c) Either instance listed it AND the citation spot-check (validation gate, below) confirms the cited line supports the claim

Drop path (a) of v3 that promoted any single-instance claim whose citation merely *resolves on disk* — file existence does not prove the claim. Anything that fails (a), (b), and (c) lands in *unverified premises* with the source spark recorded.

**Contradictions surfaced.** Build by union of three sources, deduplicated by topic:
- Instance B's `Contradictions` section verbatim
- Every Wave 2 premise probe with `STATUS: CONTRADICTED` (cite the contradicting file:line directly)
- Every Wave 2 seam probe with `SUMMARY: contradicts` (cite the seam description directly)

When Instance A listed something as a confirmed fact that any of the three sources contradict, demote it and tag `Instance A missed the conflict`.

**Unverified premises.** Union of: Instance B's `Unverified premises` section, every Wave 2 probe with `STATUS: UNVERIFIED`, and any fact that failed all three confirmation paths above.

**Gaps.** Take from Instance A. Filter: drop any gap that the merged contradictions list already covers (a contradiction is a known problem, not an unknown).

**Top must-knows and top risks.** Keep both lists separately in the merged brief — they're complementary, not redundant. Most planners read both.

## Validation gate (before returning the path)

Treat validation as the final gate before returning the path. Run these checks:

1. **Schema.** Confirm every required section header is present: `Confirmed facts`, `Contradictions surfaced`, `Unverified premises`, `Remaining gaps`, `Top things the planner must know`, `Top riskiest assumptions`, `Provenance`.
2. **Citation spot-check.** Sample 3-5 random `path:LN` citations from `Confirmed facts`. For each, Read the cited file at the cited line and verify the claim is supported by what the file actually says. When a sampled citation fails (file or line missing, or claim contradicted by the cited content), downgrade *all* facts from the same source spark to unverified and log it.
3. **Wave status roll-up.** Confirm every wave file has a `.status` of `0` (or a documented exception covering 3, 124, or other non-zero codes). Embed the wave status block in `Provenance`.
4. **Load-bearing coverage.** Every "Top must-know" item should trace to a confirmed fact or an explicitly-flagged unverified premise. A must-know with no citation chain is a synthesis hallucination — drop it and add a stand-in note "Wave 3 produced an ungrounded must-know; planner should treat this slot as missing".

Outcome:
- **All four pass** → set Validation to `PASS`, write the path-symlink at `/tmp/recon-${SLUG}.md`, return the path.
- **One or more fail** → set Validation to `PARTIAL`, list the failed checks at the top of the brief, return the path with that header. PARTIAL means "the brief is degraded and the planner should treat it as such" — the planner reads the failed-checks list before using anything in the brief. The brief is still returned; the planner decides whether to proceed, re-run, or escalate.

## Output schema

```markdown
# Recon — {slug}

**Topic:** <one-sentence statement>
**Generated:** <date>
**Run dir:** $RUN_DIR
**Inputs:** Wave 1 ({N} sparks), Wave 2 ({M} probes), Wave 3 (2 syntheses)
**Synthesis tier:** strong (or "fast (quota fallback)")
**Validation:** PASS / PARTIAL (list failed checks)

## Confirmed facts
- <claim> — `path/to/file.py:42`
- ...

## Contradictions surfaced
- **<topic>:** Wave 1 Architecture said X (`file.ts:12`); Wave 1 Gotchas said Y (`other.ts:88`). Wave 2 seam probe: <result> (`probe.ts:33`). Planner reconciles.

## Unverified premises
- <claim> — <reason grounding failed>

## Remaining gaps
- <gap> — <planning decision that depends on closing it>

## Top things the planner must know (ranked)
1. ...

## Top riskiest assumptions (ranked)
1. <assumption> — <what breaks if wrong>

## Provenance
- Wave 1 sparks: <domain_id list, status codes>
- Wave 2 probes: <premise list, seam list, status codes>
- Wave 3 framings: missing, wrong (status codes)
- All wave outputs preserved at $RUN_DIR/
- Symlink: /tmp/recon-{slug}.md → $RUN_DIR/brief.md
```

## Handoff contracts

Pass the **merged brief path** to the next consumer. The contract differs slightly per target:

- **/spec**: pass the path as the recon input to `/spec`'s Step 2; `/spec` reads it, derives the file list and constraints, and feeds the Plan model. `/spec` runs its own Codex plan review on the resulting plan — recon stops before that.
- **/hammock**: pass the path as the starting context; `/hammock` enters Lotus-Wisdom reasoning with the confirmed facts and contradictions as the seed corpus.
- **/codex-review --hypothesis**: when the recon's purpose was a debugging hypothesis, the `Top riskiest assumptions` list is the input to the hypothesis review.
- **/best-of-n**: when the recon precedes a design-space exploration, the `Confirmed facts` plus `Top must-knows` go into the candidate-generation brief.
- **Architecture decision (human-driven)**: read the brief yourself, decide. The brief's job is to make the decision tractable.

The downstream consumer chooses its own model tier; recon's codex-only rule applies only to recon's waves.

## Failure modes

- **Hallucinated citations.** Sampled in the validation gate. Downgrade all claims from the offending spark to unverified; document in `Provenance`.
- **Wave 2 contradicts Wave 1.** The point of Wave 2. Surface in `Contradictions surfaced` for the planner.
- **`strong` exit 3 (quota).** Retry the same prompt on `fast`. Tag the brief `Wave 3 ran on Spark due to quota — synthesis depth reduced; treat ranked items as suggestive`.
- **`fast` exit 3.** Surface to user and stop. Recon cannot continue degraded.
- **`codex-*` exit non-zero non-3.** Re-dispatch the specific spark once. On second failure, mark the domain "wave failed" in `Provenance` and continue with reduced coverage; flag the gap in the brief.
- **Empty output despite exit 0.** Treat as a failed spark; re-dispatch once, then mark unverified.
- **Wrapper missing or unauthenticated.** Surface to user; the skill cannot proceed.
- **Wave 3 corpus exceeds practical context (>200KB).** Trim Wave 1 reports to bullets-only before concatenating. When still too large, partition Wave 3 per-domain-cluster and merge the per-cluster syntheses.
- **Partial Wave 3 success (one of two instances failed).** Run with the surviving instance; tag the brief `Wave 3 partial — single-framing synthesis` and downgrade ranked items by one tier.
- **Repo changed mid-recon.** Compare `git rev-parse HEAD` before and after the protocol. When HEAD moved, re-run any Wave 2 probe that depended on changed files; surface the rebase in `Provenance`.
- **Recon took longer than the work would have.** Note the surface area for next-time skip threshold; the brief is still valid.

## Examples

**Standalone recon before /hammock on an unfamiliar surface:**
```
User: /recon the event-scraper rate-limit retries
You:  <Wave 0: slug=rate-limit-retries, 5 domains, $RUN_DIR created>
      <Wave 1: 5 sparks in parallel via sentinel-file dispatch>
      <Wave 2: 2 premise probes, 2 seam probes; one seam touches concurrency → escalate to strong>
      <Wave 3: 2 strong syntheses; merge; validate>
You:  Brief written to /tmp/recon-rate-limit-retries.md (run dir $RUN_DIR).
      Top issue: Wave 2 found the retry middleware referenced in Gotchas
      isn't wired up at scraper/middleware.ts:47. /hammock should start there.
```

**Recon before an architecture decision:**
```
User: /recon should we move auth from Express middleware to a dedicated service
You:  <Wave 0: slug=auth-service-split, asks "which auth surfaces — web only, or web+mobile?">
User: both
You:  <Wave 1: architecture, constraints, prior-art, gotchas, external-deps>
      <Wave 2: 2 premise probes on shared session storage, 2 seam probes incl. one on
       concurrency between web and mobile sessions (strong)>
      <Wave 3: synthesis, validate>
You:  Brief at /tmp/recon-auth-service-split.md. Top risk: session-storage write
      contention assumes Redis transactions, but Wave 2 found we're using SETEX
      without a transaction at session/store.ts:104. Architecture decision should
      address concurrency model before service boundary.
```

**Recon before a debugging hypothesis:**
```
User: I think the OAuth callback is dropping the state param. Recon first.
You:  <Wave 0: slug=oauth-state-drop, 4 domains>
      <Wave 1: routing, OAuth lib, recent auth/ commits, test coverage>
      <Wave 2 verifies "state param is read at auth/callback.ts:88" and
       probes the seam between session middleware and callback handler>
      <Wave 3 synthesizes>
You:  Brief at /tmp/recon-oauth-state-drop.md. State param IS read at
      auth/callback.ts:88 (confirmed). Contradiction: session middleware order
      differs between dev and prod configs. Hypothesis likely belongs at the
      middleware ordering, not the callback. Suggest pivoting before
      /codex-review --hypothesis.
```

**When to skip recon:**
```
User: /recon rename foo_helper to foo_util across the repo
You:  Single-rename refactor — `rg foo_helper` plus Edit is faster than the
      three-wave protocol. Skipping. Want me to do the rename?
```
