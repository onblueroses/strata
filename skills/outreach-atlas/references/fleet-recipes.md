# Fleet recipes — job design, sizing, dispatch

Read before designing any fleet. Use current task measurements for sizing; historical fleet outputs are not part of this portable setup.

## Dispatch mechanics

Use only the native subscription-backed tiers: Luna for mechanical bulk work, Terra for systems research or bounded implementation, and Sol for adversarial review or load-bearing judgment. Provider availability and spend remain operator checks.

- Fleets run through `codex exec` with the native Luna, Terra, or Sol model selectors described above; do not assume another provider or vendor-specific bulk tier.
- Layout per fleet: `raw/fleet-<name>/briefs/<job>.md`, a `run_one.sh` runner (copy an existing fleet's and `sed` the name), pool of ~8 concurrent jobs, backgrounded `codex exec ... < /dev/null` (an open stdin hangs codex at 0 CPU forever).
- Completion: the runner writes `FLEET_DONE` with per-job OK/FAILED counts; log the completion and count deltas as an operator-supplied memory event.
- Each brief gives its objective, completion condition, exact output file, and a markdown list under a `===RESULTS===` marker — one person per line in the atlas entry shape, so the curator lifts lines instead of parsing tables. A search that finds nothing writes `NONE-FOUND: <what was searched>` under the marker.
- Quota reality: Claude-side WebSearch exhausts fast, so the searching goes inside the jobs.
- Job outputs land in `raw/fleet-<name>/out/` and stay there; the primary curates them into atlas.md by hand — there is no conversion or merge step. A rerun writes a new run-stamped output file; an existing `out/` file is audit trail and is never overwritten.

## Tier routing: enumerate on Luna, execute on Luna

Use the native tiers by task shape. Luna handles bounded mechanical bulk work; Terra handles
systems research and bounded implementation; Sol handles adversarial review and load-bearing
judgment. Check current availability and any provider spend before dispatch.

The predictor is whether the job knows its worklist before it starts. An enumerated job spends
context on its list; an open-ended one spends context discovering what the list is, and
discovery has no reliable ceiling.

Use a two-stage fleet:

1. **Enumerate on Luna** — produce names, URLs, and batch boundaries.
2. **Execute on Luna** — fan the worklist out over small jobs of named items, such as batch-* or
   verify-*, while keeping nuanced classification for Sol or the primary.

Split wide jobs when the context budget is the limiting resource. Keep each batch small enough
that it can print a partial result before context runs out.

**The partial-output rule is mandatory in every brief, on either tier.** Context death returns *nothing* — the searching is done and the findings are lost. Every brief says: print the `===RESULTS===` block before you run out of room; a partial list is a good result, an exhaustive search that returns nothing is a total loss; name in one line what you did not reach so the next round picks it up.

Routing in `run_one.sh` — branch on the job name, do not try luna on everything:

```bash
case "$id" in
  verify-*|batch-*)   # enumerated worklist: luna first, luna only if it comes back empty
    codex exec --model gpt-5.6-luna --web-search on --agentic --timeout 900 \
      --cwd "$FLEET" --file "$b" < /dev/null > "$o" 2> "$e"
    if grep -q '===RESULTS===' "$o" && grep -qE '^- |^NONE-FOUND' "$o"; then echo "LUNA-OK" > "$FLEET/out/$id.tier"; exit 0; fi ;;
esac
codex exec --model gpt-5.6-luna --web-search on --agentic --timeout 1800 --cwd "$FLEET" --file "$b" < /dev/null > "$o" 2>> "$e"
```

Test success on the marker plus at least one result or `NONE-FOUND` line, not the exit code: a luna job can exit 0 having printed only prose, and a bare marker over an empty block would silently suppress the luna fallback. `codex exec` writes its event stream to stderr **only on failure** — a tiny `.err` file means the job succeeded, not that it did no work.

## Job shapes

**Map (luna).** One job per lane from the brief; standard lanes: builders/vendors, buyers-with-evidence, academia core, academia adjacent, frontier labs, OSS maintainers, community/contests, international, connectors/analysts. Each returned line: name — role text as observed — org — why-this-person clause — any channel seen verbatim. An email in a map return follows the hunt rule (quoted from a fetched page, with the source URL, tied to the person) or is left to the hunt pass. One person per line, never "A + B". Yield basis: earlier iterations parallel lanes and bounded batches sized to current capacity.

**Hunt (luna, `batch-*`).** ~10 people per job, batched by publishing surface — people found via the same kind of page hunt together (confirmed by the current run's source checks). Pass A: the person's own page (homepage, lab page, GitHub profile). Pass B escalation on misses: git commit patches, CFP listings, thesis PDFs, CVs, Wayback (the escalation pass recovers misses that the first pass cannot). The brief bans aggregators by name (RocketReach, ContactOut, Hunter, Apollo, Lusha) and pattern-guessing; an address the job cannot show on a fetched page is not emitted. Every address returns with its source URL.

**Verify (luna, `verify-*`).** The canonical enumerated job: ~15 URLs per job when each needs a fetch and read-back, ~80 addresses when it is a light recheck. Per address it returns: shown / not-shown / page-dead, plus the page's own role-and-org text so the curator can catch an attribution mismatch — the string appearing is not the same as the page tying it to this person. Earlier iterations found that source rechecks catch page drift and attribution mismatches: hunts done under the verbatim rule verify clean; the pass exists to catch drift and page death.

**Enrich (luna, `batch-*`).** ~10 people per job over the current wave's candidates. Per person: 1–2 artifacts (title, URL, one clause on what is specific about it) and a hook seed that passes the correction test (the person could correct it if it were wrong — see `/cold-email`). No artifact found is a valid result; "their homepage" is not an artifact. Fleet only the facts: finished hooks are framing, drafted in the primary per wave — earlier iterations had five AI-drafted templates rejected on register alone, and fleet-written hooks fail the same detector.

**Judgment does not fleet on the bulk tier.** Nuanced IN/OUT or lane classification misreads systematically there (an earlier round: many bulk verdicts overturned); route judgment calls to sol or keep them in the primary.

## Runner mechanics that cost a round to learn

Use current run evidence when sizing a fleet.

**Do not build the pool with `xargs -P` plus an exported function.** This shape looks right and
silently drops the job id:

```bash
export -f run_one
ls briefs/*.md | xargs -P 8 -I{} bash -c 'run_one "$@"' _ {}   # WRONG
```

All a batch can fail immediately with `file not found: briefs/.md` while `FLEET_PROGRESS` printed
correct-looking ids, so the failure read as a codex problem for several minutes. Use a plain loop
with a job-count semaphore, which also makes the pool size legible:

```bash
for b in briefs/*.md; do
  id="$(basename "$b" .md)"
  [ -s "out/$id.md" ] && { echo "SKIP $id" >> FLEET_PROGRESS; continue; }   # resumable
  while [ "$(jobs -rp | wc -l)" -ge "$POOL" ]; do sleep 4; done
  (
    codex exec --cwd "$FLEET" --file "$b" --agentic --sandbox workspace-write \
      --web-search on --timeout 2400 < /dev/null > "logs/$id.log" 2> "logs/$id.err"
    grep -qs '===RESULTS===' "out/$id.md" "logs/$id.log" && echo "OK   $id" || echo "FAIL $id"
  ) >> FLEET_PROGRESS 2>&1 &
done
wait; touch FLEET_DONE
```

The `[ -s "out/$id.md" ]` skip makes a fleet resumable, so a re-run costs only the missing jobs.

**Launch detached.** The Bash tool caps at 120s, so `timeout 420 codex exec ...` is killed at two
minutes with no useful error. Start the runner with `nohup ./run_x.sh > logs/_runner.log 2>&1 &`
and poll `FLEET_PROGRESS`.

**Pool sizing**: 12–14 concurrent jobs ran fine on the laptop (load ~3, 12 GB of 62 GB). These are
web-fetch bound, not CPU bound, so the ceiling is politeness and quota, not the machine.

**Killing a fleet: match on the fleet path, never on `codex`.** Other sessions run their own codex
processes — one had been up 28 hours — and `pkill -f codex` takes them too. Also note `pgrep -f
codex` matches this session's own tool chain, which returns a confusing exit 144:

```bash
for p in $(pgrep -f 'my-campaign/raw/fleet-'); do kill -TERM "$p"; done
```

**Measured on the later atlas rerun, the recorded period (codex exec, many jobs):** luna's subscription quota was exhausted
from the first job, so every `batch-*`/`verify-*` ran on the Luna fallback; Luna finished many open-ended discovery
jobs in 15 minutes at pool 8 and many enumerated batches in 10 minutes at pool 10. Luna sometimes drops the
bullet markup and prints `Name — ROLE: ...`, so the success test must accept bare-name lines, not only `^- \*\*`;
a strict test marked five good batches FAILED. Luna honoured a 272-name exclusion list imperfectly (9 of 298 relisted).
Hunts on Luna found many of the missing missing addresses (pass A many in pass A and some in pass B in the first wave); rechecks of many claimed
addresses returned most shown and some not shown (most of those printed in obfuscated form, which counts), some page-dead.

## Fleet jobs can drive the operator's browser: disable the Codex browser connectors (the recorded period)

`codex exec` inherits every MCP server and plugin in `~/.codex/config.toml`, which since the Codex app install
includes `mcp_servers.node_repl` (the `cua_repl` computer-use bridge with `BROWSER_USE_AVAILABLE_BACKENDS =
"chrome,iab"`), `mcp_servers.playwright` in `--extension` mode against `/usr/bin/chromium`, and the bundled
`browser@`, `chrome@` and `unified-computer-use@` plugins. Measured on the the atlas fleet verify fleet: a job whose
brief said "if the URL will not load, try one alternative" made 30 `cua_repl.js` calls and drove the operator's live
Chromium to read LinkedIn posts. the operator's standing rule (CLAUDE.md, the recorded period) is @Chrome only, with task
authorization, and never from a delegate.

Measured the recorded period with a tool-list probe (`codex exec ... "List every tool available to you; call none"`):

- `-c 'mcp_servers.node_repl.enabled=false' -c 'mcp_servers.playwright.enabled=false'` removes those two servers, but
  the computer-use bridge survives: the model still lists `mcp__cua_repl.js`. `codex mcp list` shows a third server,
  `cua_repl`, launched from the `unified-computer-use@openai-bundled` plugin cache; it has no `[mcp_servers.cua_repl]`
  entry, so `-c 'mcp_servers.cua_repl.enabled=false'` fails with "invalid transport", and the `-c plugins."..."` overrides
  did not remove it either.
- What works: a fleet-only Codex home. `~/.codex-fleet/config.toml` holds the model, no `mcp_servers`, and
  `[plugins."browser@openai-bundled"] enabled = false` (same for `chrome@`, `unified-computer-use@`, `codex-app-tools@`,
  `sites@`); `~/.codex-fleet/auth.json` is a symlink to `~/.codex/auth.json`. With `CODEX_HOME=$HOME/.codex-fleet`
  the probe lists no `mcp__` tools at all and `codex mcp list` reports none configured. Run fleet jobs as
  `CODEX_HOME=$HOME/.codex-fleet codex exec --skip-git-repo-check -s read-only --model gpt-5.6-luna -c tools.web_search=true
  "$(cat brief.md)" < /dev/null` (runner: the atlas fleet `raw/fleet-map4/run_one.sh`). Web search still works there; the
  read-only sandbox also stops the job from writing or launching anything.
- `codex exec` has no `CODEX_HOME` or `-c` passthrough today (TASK-TOOLING, the operator's tooling). No brief may invite an
  "alternative way to load" a page. Detect a breach after the fact with
  `grep -l '"server":"cua_repl"\|"server":"playwright"' ~/.cache/delegate/progress/<stamp>*.jsonl` or `grep -l cua_repl
  <fleet>/logs/*.err`. The browser-free alternative for small fan-outs is the `web-mapper` agent (WebFetch and curl only,
  no MCP by construction), but note its WebSearch draws on the parent session's shared budget (200 calls per session,
  measured the recorded period: 15 workers exhausted it in minutes), so discovery lanes belong on the Codex route.

## Pipeline reentrancy

A selection step that writes an exclusion list must not read that list on its next run. Reserving
a picked hundred and then re-running the picker excluded those hundred from their own pool, and
the list silently shrank from 100 to 62. This bit three times before the fix, because each
symptom looked like a data shortage rather than a loop.

Either reset the reservation to its base before re-picking, or have the picker ignore reservations
carrying its own tag. Make every pipeline step idempotent under re-running, and print the eligible
pool size next to the picked count so a shrinking pool is visible immediately.
