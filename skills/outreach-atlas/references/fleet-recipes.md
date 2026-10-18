# Fleet recipes — job design, sizing, dispatch

Read before designing any fleet. The sizing numbers are measurements from earlier runs on 2026-08-25 through 2026-08-27; their retained fleet directories hold the briefs and outputs behind those numbers.

## Dispatch mechanics

- **Map-stage bulk (public org/role/geo briefs) defaults to the FREE tier** — `omp-search` on `thinkingmachines/inkling-small:free` (the operator ruling 2026-09-17: continual atlas/map loops over public inputs use free models, not the Codex subscription; measured on a map fleet at ~15–25 people/run, compared with luna's 30–75). Stages that carry person data — Hunt, Verify, Enrich, or any brief naming a person, address or CRM row — stay on `codex-fast`/spark/`web-mapper`, which do not log prompts. `luna`/`codex-fast` for Map only when a brief must carry private inputs. No Fable/Opus subagents for bulk work.
- Layout per fleet: `raw/fleet-<name>/briefs/<fleetkey>-<job>-brief.md` (fleetkey = run slug plus fleet name, so every basename is unique in the research store; the naming ruling), a `run_one.sh` runner (copy an existing fleet's and `sed` the name), pool of ~8 concurrent jobs, backgrounded `codex exec ... < /dev/null` (an open stdin hangs codex at 0 CPU forever).
- Completion: the runner writes `FLEET_DONE` with per-job OK/FAILED counts; log the completion and count deltas as an OptMem event.
- Each brief gives its objective, completion condition, exact output file, and a markdown list under a `===RESULTS===` marker — one person per line in the atlas entry shape, so the curator lifts lines instead of parsing tables. A search that finds nothing writes `NONE-FOUND: <what was searched>` under the marker.
- Quota reality: Claude-side WebSearch exhausts fast, so the searching goes inside the jobs.
- Job outputs land in `raw/fleet-<name>/out/<fleetkey>-<job>-out.md` (sidecars `-out.err`, `-out.tier`) and stay there; the primary curates them into atlas.md by hand — there is no conversion or merge step. A rerun writes a new run-stamped output file; an existing `out/` file is audit trail and is never overwritten.

## Tier routing: map on the free tier, enumerate on luna, execute on spark

Spark bills a separate weekly meter, so a job that fits spark is close to free against subscription quota and runs faster (measured all-time: median 9.7s vs luna's 17.9s). The constraint is context, and it is sharp.

**Measured in an earlier run, 2026-08-26:**

| Job shape | Tier outcome |
|---|---|
| 23 open-ended discovery briefs ("find every program in this lens") | 22 died on spark with "ran out of room in the model's context window" at 22–52 distinct searches (median 26); each cost a wasted spark run *plus* a full luna run |
| 13 enumerated briefs ("re-fetch these 15 named URLs and verdict each") | 13/13 spark-ok, zero fallbacks |

The predictor is not job size or search count — it is **whether the job knows its worklist before it starts**. An enumerated job spends context on its list; an open-ended one spends context discovering what the list is, and discovery has no ceiling.

So the efficient fleet shape is two-stage, cheaper *and* wider than one-stage:

1. **Enumerate on luna** — a few wide jobs whose only product is the worklist: names, URLs, batch boundaries.
   Organization-level Map lanes (vendors, programs, conferences, public price points, and role/geo people-maps
   whose brief names no individual) run free **by default** on
   `omp-search --cwd "$FLEET" --oneshot "$(cat "$b")" > "$o"` (Inkling on the free route, wired 2026-09-16; measured on an
   atlas fleet 2026-09-17 — a continual map loop ran on it, ~15–25 people/run,
   quality comparable to luna, and near-flat on the free-request meter). Wrap it in `timeout 900 ... --max-time 13m`
   inside `run_one.sh` so a stuck job can't hang the wave's `wait`. Two constraints: the endpoint logs
   prompts, so no person names, addresses or CRM rows in the brief, and every `:free` run on the key shares 20 requests a
   minute, so pool 3–4 lanes, not 12; a 429 storm means the pool is too wide. Its `web_search` still runs gpt-5.5 on the
   Codex login, so searches are not quota-free, only the agent turns are. `--model thinkingmachines/inkling:free` or
   `nvidia/nemotron-3-ultra-550b-a55b:free` swap in a larger free model when a lane needs more depth.
2. **Execute on spark** — fan the worklist out over many small jobs of 10–20 named items each, named `batch-*` or `verify-*` so the runner routes them. 40 narrow jobs beat 8 wide ones on wall-clock, quota, and yield.

Splitting a wide job in half twice usually beats running it wide once: each half carries its whole context budget into a smaller territory. Size enumerated batches at ~15 named items (measured-good: 13/13 clean at 15); the 22-search figure is where open-ended discovery died, not a per-item budget.

**The partial-output rule is mandatory in every brief, on either tier.** Context death returns *nothing* — the searching is done and the findings are lost. Every brief says: print the `===RESULTS===` block before you run out of room; a partial list is a good result, an exhaustive search that returns nothing is a total loss; name in one line what you did not reach so the next round picks it up.

Routing in `run_one.sh` — branch on the job name, do not try spark on everything:

```bash
o="$FLEET/out/$id-out.md"; e="$FLEET/out/$id-out.err"   # $id = <fleetkey>-<job>
case "$id" in
  *-verify-*|*-batch-*)   # enumerated worklist: spark first, luna only if it comes back empty
    codex-fast --model gpt-5.3-codex-spark --web-search on --agentic --timeout 900 \
      --cwd "$FLEET" --file "$b" < /dev/null > "$o" 2> "$e"
    if grep -q '===RESULTS===' "$o" && grep -qE '^- |^NONE-FOUND' "$o"; then echo "SPARK-OK" > "$FLEET/out/$id-out.tier"; exit 0; fi ;;
esac
codex-fast --web-search on --agentic --timeout 1800 --cwd "$FLEET" --file "$b" < /dev/null > "$o" 2>> "$e"
```

Test success on the marker plus at least one result or `NONE-FOUND` line, not the exit code: a spark job can exit 0 having printed only prose, and a bare marker over an empty block would silently suppress the luna fallback. `codex-fast` writes its event stream to stderr **only on failure** — a tiny `.err` file means the job succeeded, not that it did no work.

## Job shapes

**Map (free Inkling by default; luna only when a brief must carry private inputs).** One job per lane from the brief; choose lanes by the field's actual participant types and evidence surfaces. Each returned line: name — role text as observed — org — why-this-person clause — any channel seen verbatim. An email in a map return follows the hunt rule (quoted from a fetched page, with the source URL, tied to the person) or is left to the hunt pass. One person per line, never "A + B". Yield basis: an earlier run's 15 parallel streams returned about 450 unique people; later rounds of about 10 jobs returned 90–130 each.

**Hunt (spark, `batch-*`).** ~10 people per job, batched by publishing surface — people found via the same kind of page hunt together (measured in one run: 39% → 67% hit rate). Pass A: the person's own page (homepage, organization page, GitHub profile). Pass B escalation on misses: git commit patches, CFP listings, archived PDFs, CVs, web archives (measured: pass A 269/388 ≈ 69%; pass B recovered 56/119). The brief bans contact aggregators and pattern-guessing; an address the job cannot show on a fetched page is not emitted. Every address returns with its source URL.

**Verify (spark, `verify-*`).** The canonical enumerated job: ~15 URLs per job when each needs a fetch and read-back, ~80 addresses when it is a light recheck. Per address it returns: shown / not-shown / page-dead, plus the page's own role-and-org text so the curator can catch an attribution mismatch — the string appearing is not the same as the page tying it to this person. Campaign 1 measured 324 verdicts with 0 mismatches: hunts done under the verbatim rule verify clean; the pass exists to catch drift and page death.

**Enrich (spark, `batch-*`).** ~10 people per job over the current wave's candidates. Per person: 1–2 artifacts (title, URL, one clause on what is specific about it) and a hook seed that passes the correction test (the person could correct it if it were wrong — see `/cold-email`). No artifact found is a valid result; "their homepage" is not an artifact. Fleet only the facts: finished hooks are framing, drafted in the primary per wave — campaign 1 had five AI-drafted templates rejected on register alone, and fleet-written hooks fail the same detector.

**Judgment does not fleet on the bulk tier.** Nuanced IN/OUT or lane classification misreads systematically there (one later round: 40 of 60 bulk verdicts overturned); route judgment calls to sol or keep them in the primary.

## Runner mechanics that cost a round to learn

Measured on an earlier run, 2026-08-30 (197 jobs across 8 fleets).

**Do not build the pool with `xargs -P` plus an exported function.** This shape looks right and
silently drops the job id:

```bash
export -f run_one
ls briefs/*.md | xargs -P 8 -I{} bash -c 'run_one "$@"' _ {}   # WRONG
```

All 14 jobs died instantly with `file not found: briefs/.md` while `FLEET_PROGRESS` printed
correct-looking ids, so the failure read as a codex problem for several minutes. Use a plain loop
with a job-count semaphore, which also makes the pool size legible:

```bash
for b in briefs/*-brief.md; do
  id="$(basename "$b" -brief.md)"   # already carries the fleetkey
  [ -s "out/$id-out.md" ] && { echo "SKIP $id" >> FLEET_PROGRESS; continue; }   # resumable
  while [ "$(jobs -rp | wc -l)" -ge "$POOL" ]; do sleep 4; done
  (
    codex-fast --cwd "$FLEET" --file "$b" --agentic --sandbox workspace-write \
      --web-search on --timeout 2400 < /dev/null > "logs/$id.log" 2> "logs/$id.err"
    grep -qs '===RESULTS===' "out/$id-out.md" "logs/$id.log" && echo "OK   $id" || echo "FAIL $id"
  ) >> FLEET_PROGRESS 2>&1 &
done
wait; touch FLEET_DONE
```

The `[ -s "out/$id-out.md" ]` skip makes a fleet resumable, so a re-run costs only the missing jobs.

**Launch detached.** The Bash tool caps at 120s, so `timeout 420 codex-fast ...` is killed at two
minutes with no useful error. Start the runner with `nohup ./run_x.sh > logs/_runner.log 2>&1 &`
and poll `FLEET_PROGRESS`.

**Pool sizing**: 12–14 concurrent jobs ran fine on the laptop (load ~3, 12 GB of 62 GB). These are
web-fetch bound, not CPU bound, so the ceiling is politeness and quota, not the machine.

**Killing a fleet: match on the fleet path, never on `codex`.** Other sessions run their own codex
processes — one had been up 28 hours — and `pkill -f codex` takes them too. Also note `pgrep -f
codex` matches this session's own tool chain, which returns a confusing exit 144:

```bash
for p in $(pgrep -f '<run-slug>/raw/fleet-'); do kill -TERM "$p"; done
```

**Measured on an atlas redo, 2026-09-05 (codex-fast, 136 jobs):** spark's subscription quota was exhausted
from the first job, so every `batch-*`/`verify-*` ran on the Luna fallback; Luna finished 42 open-ended discovery
jobs in 15 minutes at pool 8 and 44 enumerated batches in 10 minutes at pool 10. Luna sometimes drops the
bullet markup and prints `Name — ROLE: ...`, so the success test must accept bare-name lines, not only `^- \*\*`;
a strict test marked five good batches FAILED. Luna honoured a 272-name exclusion list imperfectly (9 of 298 relisted).
Hunts on Luna found 177 of 212 missing addresses (pass A 124, A+B 18 in the first wave); rechecks of 308 claimed
addresses returned 247 shown, 43 not shown (most of those printed in obfuscated form, which counts), 18 page-dead.

## Fleet jobs can drive the operator's browser: disable the Codex browser connectors (2026-09-06)

`codex-fast` inherits every MCP server and plugin in the runtime's Codex config, which since the Codex app install
includes `mcp_servers.node_repl` (the `cua_repl` computer-use bridge with `BROWSER_USE_AVAILABLE_BACKENDS =
"chrome,iab"`), `mcp_servers.playwright` in `--extension` mode against `/usr/bin/chromium`, and the bundled
`browser@`, `chrome@` and `unified-computer-use@` plugins. Measured on a verification fleet: a job whose
brief said "if the URL will not load, try one alternative" made 30 `cua_repl.js` calls and drove the operator's live
browser to read account pages. The operator's standing rule (2026-09-05) is @Chrome only, with task
authorization, and never from a delegate.

Measured 2026-09-06 with a tool-list probe (`codex exec ... "List every tool available to you; call none"`):

- `-c 'mcp_servers.node_repl.enabled=false' -c 'mcp_servers.playwright.enabled=false'` removes those two servers, but
  the computer-use bridge survives: the model still lists `mcp__cua_repl.js`. `codex mcp list` shows a third server,
  `cua_repl`, launched from the `unified-computer-use@openai-bundled` plugin cache; it has no `[mcp_servers.cua_repl]`
  entry, so `-c 'mcp_servers.cua_repl.enabled=false'` fails with "invalid transport", and the `-c plugins."..."` overrides
  did not remove it either.
- What works: a fleet-only Codex home. `$FLEET_CODEX_HOME/config.toml` holds the model, no `mcp_servers`, and
  `[plugins."browser@openai-bundled"] enabled = false` (same for `chrome@`, `unified-computer-use@`, `codex-app-tools@`,
  `sites@`); its `auth.json` points to the runtime's subscription auth file. With `CODEX_HOME=$FLEET_CODEX_HOME`
  the probe lists no `mcp__` tools at all and `codex mcp list` reports none configured. Run fleet jobs as
  `CODEX_HOME=$FLEET_CODEX_HOME codex exec --skip-git-repo-check -s read-only --model gpt-6-luna -c tools.web_search=true
  "$(cat brief.md)" < /dev/null`. Web search still works there; the
  read-only sandbox also stops the job from writing or launching anything.
- At the 2026-09-06 measurement, `codex-fast` had no `CODEX_HOME` or `-c` passthrough. No brief may invite an
  "alternative way to load" a page. Detect a breach after the fact with
  `grep -l '"server":"cua_repl"\|"server":"playwright"' "$FLEET_PROGRESS_DIR"/<stamp>*.jsonl` or `grep -l cua_repl
  <fleet>/logs/*.err`. The browser-free alternative for small fan-outs is the `web-mapper` agent (WebFetch and curl only,
  no MCP by construction), but note its WebSearch draws on the parent session's shared budget (200 calls per session,
  measured 2026-09-06: 15 workers exhausted it in minutes), so discovery lanes belong on the Codex route.

## Pipeline reentrancy

A selection step that writes an exclusion list must not read that list on its next run. Reserving
a picked hundred and then re-running the picker excluded those hundred from their own pool, and
the list silently shrank from 100 to 62. This bit three times before the fix, because each
symptom looked like a data shortage rather than a loop.

Either reset the reservation to its base before re-picking, or have the picker ignore reservations
carrying its own tag. Make every pipeline step idempotent under re-running, and print the eligible
pool size next to the picked count so a shrinking pool is visible immediately.
