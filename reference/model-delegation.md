# Model delegation

Use delegation when independent work, a fresh perspective, or context separation helps the task. The primary owns the brief and acceptance. Never launch `prime-inference`, any `prime-inference/*` selector, or the Prime Inference API. Verify the provider before each launch or spawn and refuse an unauthorized fallback.

**Standing ruling — free tier for public bulk (the operator, 2026-09-17):** continual/large mapping and web-research loops over **public inputs** (public organizations, roles, sources) default to the **free** OpenRouter route (`omp-search`, Inkling), not the Codex subscription — see the `omp-search` paragraph below. The Codex subscription (`luna`/`codex-fast`/`sol`) is reserved for work that needs its judgment or carries **private inputs**: **stored contact lists, private record rows, or vault text** never go to the free (prompt-logging) route.

**Amendment (the operator, 2026-09-18):** a **person's name** (with public title/employer/source page) is **allowed** on the free tier — e.g. evidenced address *sourcing*, where inkling finds a published address it was never handed. The line is now about **data we hold**, not about naming a person: still never paste an address from private records, a private record row, or vault text into a free prompt, and still route ranking/classification that reasons over our own records on the subscription tier.

## Coequal operators

Primary Claude, Codex, and user-facing DeepSeek have the same task coverage and authority. Their runtime changes tools and metering. A delegated role has only the authority its task needs; ancestry does not grant primary authority.

## Native Codex routes

The source of the role configuration is `<agent-config>/codex/agents/`, linked into `<codex-config>/agents/`.

| Work | Native model | Configured roles |
|---|---|---|
| Difficult implementation or independent review | `gpt-6-sol` | `load-bearing-worker`, `adversarial-reviewer` |
| Bounded implementation or systems research | `gpt-5.6-terra` | `implementation-worker`, `systems-researcher` |
| Mechanical work or focused lookup | `gpt-6-luna` | `mechanical-worker`, `docs-researcher`, `knowledge-lookup` |

The provider prohibition and pre-launch verification requirement live in the shared contract’s Constraints section. On cross-provider launch/spawn surfaces, use exact `openai-codex/gpt-6-sol`, `openai-codex/gpt-5.6-terra`, and `openai-codex/gpt-6-luna` selectors. Native Codex `model` fields use the client catalog slugs `gpt-6-sol`, `gpt-5.6-terra`, and `gpt-6-luna`.

GPT-6 (2026-09-22, Codex CLI 0.155.1): the catalog lists `gpt-6-astra` (frontier; the `<codex-config>/config.toml` default), `gpt-6-sol` and `gpt-6-luna`, with no GPT-6 Terra, so the Terra route stays on `gpt-5.6-terra`. `codex exec` smoke-tested both new slugs. omp 18.2.9 lists only `gpt-6-astra` under `openai-codex` and fuzzy-matches an unknown name to OpenRouter (paid), so `<omp-config>/agent/config.yml` stays on 5.6 until its `openai-codex` table lists the GPT-6 slugs.

Compatibility evidence (2026-08-14): Codex CLI 0.147.0 with ChatGPT auth rejected the qualified form and accepted the native slug while reporting `provider: openai`. This records that run, not a fresh version check.

If a configured role is unavailable in the current client, a default native agent with the same allowed model and an explicit role brief can serve the task.

Choose independent subtasks and assign disjoint write ownership. Tell workers that other sessions may be editing the tree. A fresh review should receive the goal, evidence, diff, and relevant constraints without being told what conclusion to reach. Research before major new builds is useful; a fixed number of researchers is not required.

The 2026-09-30 unattended Sol worker route used `gpt-6.1-sol` at xhigh and required Codex 0.159 or newer. Since 2026-10-10 the dispatcher handles unclaimed `for:codex` issues; see [followup-convention.md](followup-convention.md).

## Other runtime mechanics

- Claude's `codex-strong` and `codex-fast` wrappers use Codex; their current defaults are printed by `--help`. Use native Codex agents inside Codex. Claude-relay agent types do not launch the intended external model reliably.
- Check `<wrapper> --help` for flags. Both Codex wrappers print a progress-file path and session id; inspect that output before interrupting a run. `--resume ID` continues an existing conversation.
- Background long CLI work, retain its handle and result path, and close stdin with `< /dev/null`. Anything that must outlive the laptop needs a completion chain elsewhere. Never use `pgrep -f` on the waiting command itself as a completion test.
- Keep `CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP=1` in Claude settings: sibling-session memory pressure previously killed unrelated background shells.
- Bare CLI details, including hook trust, are in [codex-invocation.md](codex-invocation.md). An error or interrupted run may have left file edits; inspect the tree before retrying.

`codex-union` (OpenRouter) and the DeepSeek routes both run behind local LiteLLM `/v1/responses` bridges because codex rejects `wire_api = "chat"` outright since 0.154; a raw OpenAI-compatible base_url cannot be added to `<codex-config>/config.toml` without one. They are deliberately separate instances (:4101 and :4100) so the DeepSeek message-order hook never sees other providers' traffic. Serving another model over either bridge means editing its yaml in `<delegate-config>/` and restarting the unit, not a codex config change.

`omp-union` is the same free stealth model (`stealth/union-alpha`, 262K ctx, no reasoning knob) in the omp harness (oh-my-pi, `<user-bin>/omp`, installed 2026-09-16). omp speaks chat-completions natively, so no bridge is in that path and the key lives in omp's auth store (`/login openrouter`), not the env. The wrapper is `omp -p --auto-approve` with `--cwd DIR` and `--oneshot` (read-only tools); it prints only the final message. omp's own roles (`omp config get modelRoles`) run on the Codex subscription OAuth, terra/luna/sol by the same route table as above, and its `task` tool spawns the bundled agents in `<omp-config>/agent/agents/` on `@smol`. The same privacy rule as `codex-union` applies to anything an `omp-union` run can read.

`omp-search` is the free web-research route: `omp -p --auto-approve` inside `free-silo` (2026-09-27: an empty jail, no view of this machine; see the shared contract) on an OpenRouter `:free` model with only `web_search`, `read` and `write` enabled (`--oneshot` drops `write`, `--cwd DIR` receives the files it wrote, `--in FILE` hands it a public input, `--model SLUG` swaps the model, `--max-time` defaults to 15m, `--search tavily` swaps the search backend). Default `thinkingmachines/inkling-small:free` (1M ctx, served by Thinking Machines); `nvidia/nemotron-3.5-lightning:free` (30B-A3B MoE, served by NVIDIA) is the alternate. Evidence, 2026-09-16, same prompts through the same harness: on a public market-sizing task inkling delivered in 264s with every spot-checked figure exact, nemotron in 748s with one ceiling wrong and one unverifiable record, luna in 725s with the strongest answer (primary records, published rate cards, all exact). On a public document-table task inkling (434s, 8 rows) and luna (296s, 13 rows) delivered with verified rows; nemotron hit the 14-minute cap with no output and, rerun, stopped after 158s with garbled text having made two searches and no page reads. Every `:free` model shares one quota per key: 20 req/min and 1000 req/day (the key sits in the 1000/day tier). Both free endpoints log prompts for provider training and forbid personal data, so the `codex-union` privacy rule applies: no private names, addresses, records or vault text in the prompt, no unattributed output. In the silo, search is still Codex-hosted, through `codex-search-bridge` on the host (SearXNG API, 6-8s per query; the Codex login never enters the silo); `--search duckduckgo|tavily` switch backends. Outside the silo, omp's `web_search` tool is model-independent: its first provider is OpenAI's hosted web search run as gpt-5.5 over the Codex OAuth login (`PI_CODEX_WEB_SEARCH_MODEL` overrides the model), so a free chat model still spends a little Codex quota per search call and gets the same search results `luna` gets; DuckDuckGo is only the fallback when no Codex login exists. `--search tavily` switches the run to Tavily (key in `<delegate-config>/.env`, Researcher plan, 1000 credits/month) via a `providers.webSearchOrder` overlay: on the same market-sizing task Tavily runs finished about three times faster but the sources degraded to listicles, a LinkedIn post and off-topic vendors, so it is the fallback for when Codex quota or rate limits bite, not the default. Page reading is omp's `read` tool on the URL (native Readability extraction; trafilatura and lynx are not installed); some primary sites return JavaScript shells or 403 for every model, so verify records through accessible primary APIs or clearly mark secondary corroboration. This route replaces `luna` for search grunt work; `luna` stays for anything that needs the Codex subscription's judgment or private inputs. The `web-researcher` agent now lives only in the silo's omp profile (moved 2026-09-27 so a Codex-model omp session cannot hand a free model private context; it was `<omp-config>/agent/agents/web-researcher.md`: inkling-small:free, tools web_search/read/write/yield, structured output summary/report/sources/unverified); omp's `task` tool picks it for web research by its description, verified 2026-09-16 with a two-site lookup in 39s. The description carries the privacy rule, since a parent session could otherwise hand it private context.

`omp-inkling` is the free general worker: `omp -p --auto-approve --no-session` on `thinkingmachines/inkling:free` (975B MoE / 41B active, 1M ctx) with omp's full tool set, for mechanical and bulk work on public inputs that would otherwise go to `luna` (extraction, classification, reformatting, file edits, data collection). `--small` swaps in `inkling-small:free` (276B / 12B), `--oneshot` limits tools to read/glob/grep/web_search, `--cwd DIR` and `--max-time` (default 15m) as in `omp-search`. OpenRouter serves both Inkling models only to agentic harnesses: a raw `/chat/completions` call returns 403 "only available on agentic harnesses", so scripts go through omp, never curl. The `inkling-worker` agent lives only in the silo's omp profile since 2026-09-27 (was `<omp-config>/agent/agents/inkling-worker.md`, full tools, privacy rule in its description), verified 2026-09-17 by a luna parent picking it through the `task` tool. Speed, 2026-09-17, one 8-row classification prompt through omp with no tools: inkling-small 3.8s, nex-n2.5-mini 4.3s, nex-n2.5-pro 7.9s, nemotron-3-super 13.8s, nemotron-3-ultra 17.3s, qwen3.8-27b 25s, inkling 29s; all were correct, so that prompt ranks speed, not quality. Head-to-head against `luna`, 2026-09-17, same omp harness, auto-scored: eight non-search tasks (messy extraction with corrections and duplicates, a multi-file rename plus unit bug, three buggy modules against 12 hidden tests, CSV aggregation, a three-file join with currency conversion and dedup, headline labels under a seven-rule priority rubric), 2–3 reps each, 60 runs: every model scored 100% on every run, so at this difficulty the free models match `luna` and the test cannot rank them further. Latency across the 60 runs: inkling-small median 16s (p90 97s), `luna` 29s (128s), inkling 31s (209s, max 385s); free endpoints carry the longer tail. Default to inkling-small for public mechanical work; inkling earns its slower tail only on work harder than this suite. Suite: a local benchmark artifact. Same quota and privacy rule as every `:free` route.

DeepSeek routes have separate metering and authority. `dsh-primary` is the user-facing primary launcher; `dsh-agent` is the delegated launcher. `ds-flash`, `ds-pro`, and `ds-codex` are also metered API routes. They are not automatic fallbacks for exhausted Codex quota: obtain the required spend authorization and obey the selected runtime's provider policy.

The isolated primary DSH launcher validates session scope, loads OptMem, and requires `--confirm-spend`. Load Linear with `brain-linear pickup ds` when picking up work. Its native child surfaces remain disabled until they can attenuate primary memory authority; use the separate delegated launcher. `agents-core/CORE-compact.md` serves the cached delegated prefix. Keep stable context before changing task detail; edits near the prefix's start invalidate the cache. A custom `--system` can replace the normal wrapper contract, so supply the needed boundaries deliberately.

## Azure AI Foundry (configured, 2026-10-16)

`<azure-config>/.env` holds `AZURE_FOUNDRY_KEY` and `AZURE_FOUNDRY_BASE_URL` (an OpenAI-compatible `/openai/v1` endpoint); load it with `set -a; . <azure-config>/.env; set +a` or python-dotenv, and use the stock `openai` client with `base_url` + `api_key` (or header `api-key:` with curl). `model=` is the deployment name, case-sensitive: `gpt-6-astra`, `gpt-6.1-sol`, `gpt-6-sol`, `Kimi-K2.7-Code`, `DeepSeek-V4-Flash`, `DeepSeek-V4.1-Flash`; all six answered on 2026-10-16. The gpt-6 family rejects `max_tokens` and needs `max_completion_tokens`, and astra/6.1-sol spend hidden reasoning tokens inside that budget (give it room: 2000+ for real work); `gpt-6-sol` answered a trivial prompt with zero reasoning tokens. Kimi returns `reasoning_content` beside `content`; the DeepSeek Flash pair takes `max_tokens` and does function calling. Responses carry Azure content-filter annotations. A second deployment (`AZURE_FOUNDRY_SECONDARY_BASE_URL`: gpt-5-mini, DeepSeek-V4-Pro) returns 401 with this key and needs its own. Billing lands on the authorized subscription: no bulk or fleet runs without asking the operator first. The key was shared once; recovery copies are `<secret-backup>/` and the hourly estate snapshot.

## Briefs and results

Give the concrete objective, enough source material or paths to understand it, file ownership, granted side effects, and a stopping condition. Include known failure modes when they matter. Let the worker choose routine mechanics. Require the actual artifact or findings and verification evidence, including unresolved gaps.

Long work needs a restart point and a named lifecycle. Keep research and review read-only unless implementation is authorized. For substantive tracked work, name the Linear issue and claimed session scope in the brief; the primary may coordinate the board for a bounded delegate.

## Cooperative issue ownership

Issues coordinate intent, not exclusive file locks. Follow [followup-convention.md](followup-convention.md):

1. Read the current issue, labels, relations, and recent comments before mutation.
2. An overlapping active claim needs a disjoint scope or an agreed handoff. Do not infer that a claim expired merely from its age. A `Starting` comment signed `worker-vps` or `worker-laptop` is a live claim by a queue worker; it reports or gives the issue back within hours.
3. Route claimed work to the current runtime, preserve unrelated labels, and leave one `for:` label on non-DEC issues. Sign the start comment with the supplied `@s/<id>` and concrete scope.
4. Recheck the issue and working tree after a handoff or interruption before editing.
5. Append a signed outcome with evidence. Close only completed work; leave unfinished work restartable and truthfully open.

Sealed decisions live in `<notes-tree>/lore/decisions/`. Check relevant rulings before reopening a direction; follow that directory's README when filing a verdict.

## Memory and acceptance

User-facing primaries may append and settle OptMem under [knowledge-management.md](knowledge-management.md). Delegates return canonical candidates; they never call `memo note` or `memo nap`. Use the detached proposal inbox only when the dispatch requires it.

The append lock serializes writes, not meanings. Before acting on mutable state, recall the exact entity, scope, and key and use the greatest memo id. Keep repository warnings in that repository's `AGENTS.md`, current work on Linear, and rich documents in lore.

The primary checks results against the actual task and artifacts. A passing command or confident delegate report is evidence, not acceptance by itself. Shared `CLAUDE.md` governs when independent review is required.
