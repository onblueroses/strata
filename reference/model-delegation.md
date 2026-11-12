# Model delegation

Use delegation when independent work, a fresh perspective, or context separation helps the task. The primary owns the brief and acceptance. Never launch `prime-inference`, any `prime-inference/*` selector, or the Prime Inference API. Verify the provider before each launch or spawn and refuse an unauthorized fallback.

**Standing ruling — free tier for public bulk (the operator, 2026-09-17):** continual/large mapping and web-research loops over **public inputs** (public organizations, roles, sources) default to a **free** model, not the Codex subscription — see the free-model paragraph below. The Codex subscription (`luna`/`codex-fast`/`sol`) is reserved for work that needs its judgment or carries **private inputs**: **stored contact lists, private record rows, or vault text** never go to the free (prompt-logging) route.

**Amendment (the operator, 2026-09-18):** a **person's name** (with public title/employer/source page) is **allowed** on the free tier. The line is now about **data we hold**, not about naming a person: still never paste an address from private records, a private record row, or vault text into a free prompt, and still route ranking/classification that reasons over our own records on the subscription tier.

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

- From a Claude primary, delegates and research walkers run on Codex through the wrappers (Terra for research, `codex-fast --model gpt-5.6-terra`; Luna for lookups and bulk) or on the free route for public inputs. The harness's own subagents (Agent tool) are not a substitute for them: never Fable, at most Opus, and only when the operator asks for Claude there (ruling of 2026-11-10).
- Claude's `codex-strong` and `codex-fast` wrappers use Codex; their current defaults are printed by `--help`. Use native Codex agents inside Codex. Claude-relay agent types do not launch the intended external model reliably.
- **Groundwork route (ruling of 2026-11-12; first choice for bulk tasks):** `opencode-fast` (laptop and VPS, in `<user-bin>`) runs `opencode run` on OpenCode Go with `deepseek-v4.1-flash` by default, for not-super-complicated implementation, edits and chores; `ds-flash`/`ds-pro` and dsh web also run on Go by default (`DS_AGENT_PROVIDER=deepseek` or the dsh model selector for the direct API); harder work stays on `codex-strong`/`codex-fast`. No secrets in prompts.
- Check `<wrapper> --help` for flags. Both Codex wrappers print a progress-file path and session id; inspect that output before interrupting a run. `--resume ID` continues an existing conversation.
- For long main runs, select `codex-strong --hcom` or `codex-fast --hcom` explicitly (ruling of 2026-11-11). Short calls keep the ordinary `codex exec` path. Duration alone does not select a mode.
  The wrapper launches a native headless Codex session through hcom, prints its hcom name to stderr, then waits for a completed turn and hcom's listening state. Use that name with `hcom list NAME` or `hcom send @NAME -- MESSAGE` during the run.
  In hcom mode, `--cwd DIR` selects the working folder; the folder must already be trusted in Codex, and a saved refusal stops the launch. A folder-trust prompt or another startup dialog returns an error with a remedy. An initialized idle session without a started turn also returns an error. During startup, the wrapper reports that delivery is pending. Codex can draw an empty composer and a model footer before its native session binds, so those screen elements alone cannot prove failed delivery. The printed hcom name alone does not prove prompt delivery.
  Model, reasoning, web search, sandbox, browser and service-tier options pass to Codex. The hcom mode selects the subscription provider `openai` and disables response caching. The hcom mode has no timeout by default. Set `--timeout SECONDS` explicitly when the task needs one; `--timeout 0` also requests an uncapped run.
  The wrapper prints the final answer to stdout and stops its own hcom process on completion, failure, timeout or interruption. The Codex transcript and hcom records remain available. A blocked or inactive agent returns an error. Existing exit classification, telemetry and breaker checks also apply to this mode.
  `--hcom` rejects `--raw` and `--resume`. The progress file contains events translated from the native rollout. Resume a stopped conversation separately through `hcom r SESSION_ID --headless --go`, or use the ordinary wrapper's `--resume SESSION_ID` path.
- Background long CLI work, retain its handle and result path, and close stdin with `< /dev/null`. Anything that must outlive the laptop needs a completion chain elsewhere. Never use `pgrep -f` on the waiting command itself as a completion test.
- Keep `CLAUDE_CODE_DISABLE_BG_SHELL_PRESSURE_REAP=1` in Claude settings: sibling-session memory pressure previously killed unrelated background shells.
- Bare CLI details, including hook trust, are in [codex-invocation.md](codex-invocation.md). An error or interrupted run may have left file edits; inspect the tree before retrying.

The DeepSeek routes run behind a local LiteLLM `/v1/responses` bridge because codex rejects `wire_api = "chat"` outright since 0.154; a raw OpenAI-compatible base_url cannot be added to `<codex-config>/config.toml` without one. Each provider gets its own bridge instance on its own loopback port, so the DeepSeek message-order hook never sees other providers' traffic. Serving another model over a bridge means editing its yaml in `<delegate-config>/` and restarting the unit, not a codex config change.

`opencode-fast` is the first route for bulk and groundwork: OpenCode Go with a DeepSeek Flash model, on the laptop and the VPS. Use `codex-fast` for mechanical work that needs Codex and `codex-strong` for difficult delegated work.

`codex-union`, `omp-union` and `omp-inkling` are dead: their upstream models were retired or went paid-only (2026-09-27 and 2026-11-10), and no replacement has been measured. Never fall back to a paid slug.

Free models are the web-research route for public inputs. They run inside a sandbox with no view of the machine, and every quote they return is checked with `quote-check`. Free endpoints log prompts for provider training: no private names, addresses, records or vault text in the prompt, no unattributed output. For private inputs and quick lookups use `codex-fast --web-search on --oneshot`.

DeepSeek routes have separate metering and authority. `dsh-primary` is the user-facing primary launcher; `dsh-agent` is the delegated launcher. `ds-flash`, `ds-pro`, and `ds-codex` are also metered API routes. They are not automatic fallbacks for exhausted Codex quota: obtain the required spend authorization and obey the selected runtime's provider policy.

The isolated primary DSH launcher validates session scope, loads OptMem, and requires `--confirm-spend`. Load Linear with `brain-linear pickup ds` when picking up work. Its native child surfaces remain disabled until they can attenuate primary memory authority; use the separate delegated launcher. `agents-core/CORE-compact.md` serves the cached delegated prefix. Keep stable context before changing task detail; edits near the prefix's start invalidate the cache. A custom `--system` can replace the normal wrapper contract, so supply the needed boundaries deliberately.

## Briefs and results

Give the concrete objective, enough source material or paths to understand it, file ownership, granted side effects, and a stopping condition. Include known failure modes when they matter. Let the worker choose routine mechanics. Require the actual artifact or findings and verification evidence, including unresolved gaps.

Long work needs a restart point and a named lifecycle. Keep research and review read-only unless implementation is authorized. For substantive tracked work, name the Linear issue and claimed session scope in the brief; the primary may coordinate the board for a bounded delegate.

## Cooperative issue ownership

Issues coordinate intent, not exclusive file locks. Follow [followup-convention.md](followup-convention.md):

1. Read the current issue, labels, relations, project, milestone, current-state block, and recent comments before mutation.
2. An overlapping active claim needs a disjoint scope or an agreed handoff. Do not infer that a claim expired merely from its age. A `Starting` comment signed `worker-vps` or `worker-laptop` is a live claim by a queue worker; it reports or gives the issue back within hours.
3. Route claimed work to the current runtime, preserve unrelated labels, and leave one `for:` label on non-DEC issues. Sign the start comment with the supplied `@s/<id>` and concrete scope.
4. Recheck the issue and working tree after a handoff or interruption before editing.
5. Append a signed outcome that opens with the closure summary (`Delivered:`, `Still unresolved:`, `Continues in:`, `Evidence:`). Close only completed work; leave unfinished work restartable and truthfully open.

Sealed decisions live in [decisions/](../decisions/README.md). Check relevant rulings before reopening a direction; follow that directory's README when filing a verdict.

## Memory and acceptance

User-facing primaries may append and settle OptMem under [knowledge-management.md](knowledge-management.md). Delegates return canonical candidates; they never call `memo note` or `memo nap`. Use the detached proposal inbox only when the dispatch requires it.

The append lock serializes writes, not meanings. Before acting on mutable state, recall the exact entity, scope, and key and use the greatest memo id. Keep repository warnings in that repository's `AGENTS.md`, current work on Linear, and rich documents in the notes tree.

The primary checks results against the actual task and artifacts. A passing command or confident delegate report is evidence, not acceptance by itself. Shared `CLAUDE.md` governs when independent review is required.
