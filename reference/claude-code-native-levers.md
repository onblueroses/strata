<!-- keywords: native triggers, claude code env vars, agent files, agents directory, agent-teams, SendMessage, worktree isolation, run_in_background, autoDream, asyncRewake, coordinator mode, subagent model, hooks, hook events, hook if filter, matcher, settings.json permissions, PreToolUse deny, Stop hook loop, fail open, output style, append-system-prompt, GrowthBook gating, what can claude code do natively, native levers -->
# Claude Code Native Levers

What the stock Claude Code binary already does that a heavy config layer often reimplements by convention. Verified by string-grepping the installed Claude Code bundle and cross-reading the source. Verified against a recent Claude Code build; binary auto-updates churn these flags, so re-verify after upgrades.

**Hard caveat:** presence of a literal in the binary is NOT proof the feature fires. Several capabilities sit behind GrowthBook defaults or compile-time `feature()` gates that are dead-code-eliminated in shipped builds. Smoke-test each before relying on it. Gating below is for a recent build; re-check after upgrades.

## Quick Nav
| Want | Jump to |
|------|---------|
| Spawn/define specialized agents as files | Tier 1 - Multi-agent |
| Parallel / background / isolated agents | Tier 1 - Multi-agent |
| The full hook surface (this install wires 6 of ~27 events) | Tier 1/2 - Hooks + Hook-Event Table |
| Native memory self-maintenance | Tier 2 - Memory |
| System-prompt / permission / turn knobs | Tier 3 - Prompt & turn |
| What NOT to port (this layer is richer) | Don't-port |

Gating legend: **external-OK** = works in stock binary; **gated** = external-reachable but behind a GrowthBook default (smoke-test); **inert** = literal present but feature DCE'd; **internal-only** = needs an internal `USER_TYPE` marker / a custom build.

## Tier 1 - Multi-agent & orchestration

<details>
<summary>Tier 1 - Multi-agent & orchestration</summary>

| Capability | Native trigger | Gating | Notes |
|---|---|---|---|
| Custom subagents as files | `$STRATA_HOME/agents/<name>.md` frontmatter: `description`(→whenToUse), `prompt`, `tools`, `disallowedTools`, `model`, `permissionMode`, `isolation`, `maxTurns` | external-OK | This install ships a handful under `$STRATA_HOME/agents/` (e.g. orchestrator, code-reviewer, knowledge-lookup, quick-research, planner); the schema supports much more |
| Run MAIN session as an agent | `claude --agent <name>` (or `--agents '<json>'`) | external-OK | Replaces the system prompt with that agent's. The real way to express an "orchestrator" identity |
| Agent teams + peer message bus | `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` or `--agent-teams`; then `TeamCreate` + `SendMessage` | gated (GrowthBook default) | Teammates **share the leader's cwd** (do NOT auto-isolate); plain output is invisible to peers |
| Worktree-isolated agent | Agent param `isolation:'worktree'` (or agent-file `isolation: worktree`) | external-OK | Auto-creates + GCs a temp git worktree, returns the changed branch. Separate mechanism from teams |
| Background / detached agent | `run_in_background:true`; auto-background after 120s via `CLAUDE_AUTO_BACKGROUND_TASKS=1` | external-OK | Completion arrives as a `<task-notification>` (no polling) |
| Subagent model override | `CLAUDE_CODE_SUBAGENT_MODEL=<alias>` (or per-agent `model:`) | external-OK | Route cheap lookups to a small fast model (the grader lane) |
| Scheduled / triggered agents | `ScheduleCron` / `RemoteTrigger` tools (feature `AGENT_TRIGGERS` in base); disable with `CLAUDE_CODE_DISABLE_CRON=1` | external-OK | |
| Coordinator orchestrator mode | `CLAUDE_CODE_COORDINATOR_MODE=1` | **inert** (`feature('COORDINATOR_MODE')` DCE'd) | Env does nothing in shipped builds. Use `--agent <orchestrator>` instead |
| Fork-subagents (cache-sharing) | omit `subagent_type` when `FORK_SUBAGENT` on | internal-only (custom build) | Pattern only; can't switch on externally |

</details>

## Tier 1/2 - Hooks

<details>
<summary>Tier 1/2 - Hooks</summary>

Five hook types in `settings.json` `hooks`: `command` (shell), `prompt` (forced-JSON `{ok,reason}` on a small fast model, no subprocess), `agent` (multi-turn small-model verifier, reads transcript + read-only tools, ~50-turn cap), `http` (POST, SSRF-guarded, `allowedEnvVars` header allowlist).

| Lever | Trigger | Gating |
|---|---|---|
| Re-wake the model on a background job | command-hook field `asyncRewake: true` → on exit 2, stderr becomes a task-notification that interrupts the model | external-OK |
| Background a hook | `async: true` (or `{"async":true,"asyncTimeout":N}` as first stdout line) | external-OK |
| Fire a hook only on matching calls | hook field `if: "Bash(git *)"` (permission-rule syntax) | external-OK |
| One-shot hook | hook field `once: true` (frontmatter/skill hooks) | external-OK |
| Block / rewrite-input / inject-context | hook stdout JSON: `continue:false` (stop turn), `decision:'approve'\|'block'`, `hookSpecificOutput.updatedInput` (rewrite tool input), `additionalContext` | external-OK |
| Inject session env from a hook | write `KEY=VALUE` lines to `$CLAUDE_ENV_FILE` on SessionStart/Setup/CwdChanged/FileChanged | external-OK |
| File-watch hooks | a hook returns `watchPaths:[...]`; `FileChanged` hooks then fire with `{file_path,event}` | external-OK |
| Hooks in skill/agent frontmatter | `hooks:` block in a SKILL.md / agent file; agent `Stop` auto-maps to `SubagentStop` | external-OK |
| Kill-switch | settings `disableAllHooks: true`; `allowManagedHooksOnly` (managed-settings only) | external-OK |

**`matcher` vs `if` (the two-stage filter that grounds the settings contract):** `matcher` selects on the **tool name** (`Edit|Write|Bash|...`, regex over the tool identifier); `if` is a second-stage **permission-rule** filter on the tool *input* (e.g. `if: "Bash(git push*)"` fires only when the Bash command matches that pattern). They compose: a hook with `matcher: "Bash"` + `if: "Bash(git push*)"` runs the binary only on git-push commands. `matcher` is the cheap gate, `if` is the precise gate.

</details>

## Hook-Event Table

<details>
<summary>Hook-Event Table</summary>

This install wires 6 of ~27 events. Wired now (from `$STRATA_HOME/settings.json`): **SessionStart, Stop, UserPromptSubmit, PreCompact, PreToolUse, PostToolUse**.

| Event | In recent build | Wired | Worth wiring | Idea |
|---|---|---|---|---|
| PreToolUse | yes | ✅ | — | (already heavy: gates + routers) |
| PostToolUse | yes | ✅ | — | (already heavy: observe + lint) |
| UserPromptSubmit | yes | ✅ | — | (doc router + nudge) |
| SessionStart | yes | ✅ | — | (restore + daily note) |
| Stop | yes | ✅ | — | (teardown — overloaded) |
| PreCompact | yes | ✅ | — | (pre-compaction save) |
| Notification | yes | — | maybe | surface idle / permission notifications |
| PostToolUseFailure | yes | — | ✅ | react to a failed Bash/Edit (retry/capture) |
| StopFailure | yes | — | maybe | |
| SubagentStart | yes | — | ✅ | per-subagent telemetry start |
| SubagentStop | yes | — | ✅ | subagent quota/telemetry; verify a field-agent's output |
| SessionEnd | yes | — | ✅ | move teardown off the overloaded Stop |
| PostCompact | yes | — | ✅ | native post-compaction restore (replaces the SessionStart+guard hack) |
| PermissionRequest | yes | — | maybe | delegate allow/deny |
| PermissionDenied | yes | — | maybe | |
| Setup | yes | — | maybe | first-run provisioning |
| TeammateIdle | yes | — | ✅ (with teams) | event-driven coordination vs polling |
| TaskCreated | yes | — | ✅ | task-lifecycle log |
| TaskCompleted | yes | — | ✅ | task-lifecycle log / spec progress |
| Elicitation / ElicitationResult | yes | — | maybe | structured prompts vs AskUserQuestion |
| ConfigChange | yes | — | maybe | |
| WorktreeCreate / WorktreeRemove | yes | — | maybe | observe native worktree agents |
| InstructionsLoaded | yes | — | maybe | react to CLAUDE.md load |
| CwdChanged | yes | — | maybe | auto-load entity context on dir change |
| FileChanged | yes | — | ✅ | react to a job writing a result file (pairs with asyncRewake) |

</details>

## Hook semantics

<details>
<summary>Hook semantics</summary>

Verified against the bundle:

- **timeout units differ by hook type.** `command` hooks: **milliseconds** (existing hooks use 2000–15000). `prompt`/`agent` hooks: **seconds** (the runtime multiplies ×1000). So a `command` `timeout:3000` = 3s, but a `prompt` `timeout:3` = 3s. Easy to get wrong.
- **prompt/agent hooks FAIL OPEN.** timeout, runtime error, and unparseable/missing structured output all return non-blocking (`cancelled` / `non_blocking_error`); only an explicit `{ok:false}` blocks. Safe to wire a native LLM gate without trapping a session.
- **PreToolUse deny contract.** A `command` hook that **exits 2** denies the tool call and feeds its stderr back to the model as the reason; exit 0 allows, other non-zero is a non-blocking error. JSON `decision:'block'` (or `permissionDecision:'deny'` in `hookSpecificOutput`) is the structured equivalent. This is the contract every gate hook relies on.
- **Stop cannot be narrowed — do not put a model-gate on it.** `Stop` has no match query (so `matcher` is a no-op) and `if` is evaluated only for tool events (so a Stop `if` is skipped). A blocking Stop (`decision:block` / agent `{ok:false}`) re-prompts the model with `stopHookActive:true` and has **no single-shot guard** → loop risk across every session. Put a native verifier on **PostToolUse** (narrowable by `matcher` + `if` path), never Stop.
- **asyncRewake contract**: a `command` hook with `asyncRewake:true` that exits 2 hands its stderr to the runtime as a task-notification that re-wakes the model (pairs with `async:true`).
- **Native LLM verifier output shape**: both `prompt` and `agent` hooks force `{ok:boolean, reason?:string}`; `agent` hooks read transcript + read-only tools, hard-capped at 50 turns (no settings field for it); payload arrives via `$ARGUMENTS`.

</details>

## Tier 2 - Memory self-maintenance
| Capability | Trigger | Gating | Notes |
|---|---|---|---|
| Background dream consolidation | `settings.json autoDreamEnabled: true` | external-OK | Writes a **flat** MEMORY.md → 2nd writer vs the `consolidate-memories` hook; port the pattern, don't flip blind |
| Auto-memory master switch | `autoMemoryEnabled` / `CLAUDE_CODE_DISABLE_AUTO_MEMORY` | external-OK (default on) | This is the MEMORY.md mechanic |
| Auto-compaction (9-section summary) | `autoCompactEnabled` (default on) / `DISABLE_AUTO_COMPACT=1`; window `CLAUDE_CODE_AUTO_COMPACT_WINDOW` | external-OK | |
| Verification agent / extractMemories / native memory commands | — | internal-only / flag-gated | Not cleanly switchable externally |

## Tier 3 - Prompt & turn knobs

<details>
<summary>Tier 3 - Prompt & turn knobs</summary>

| Lever | Trigger | Gating |
|---|---|---|
| Append to the system prompt | `--append-system-prompt "<t>"` / `--append-system-prompt-file <p>` | external-OK |
| Replace the system prompt | `--system-prompt[-file]` | external-OK |
| Trim dynamic prompt sections | `--exclude-dynamic-system-prompt-sections` | external-OK |
| Ultra-minimal prompt | `CLAUDE_CODE_SIMPLE=1` / `--bare` | external-OK |
| Swap identity via output style | `settings.json outputStyle: "<Style>"` | external-OK (style only — NOT for orchestration/tool-policy) |
| Disable CLAUDE.md/AGENTS.md auto-inject | `CLAUDE_CODE_DISABLE_CLAUDE_MDS=1` / `--bare` | external-OK |
| Persistent allow/deny/ask rules | `settings.json permissions.{allow,deny,ask,defaultMode,additionalDirectories}`; `--permission-mode`; `--add-dir`; lockdown via managed-settings.json | external-OK |
| Widen parallel reads | `CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY=<int>` (default 10) | external-OK |
| Thinking control | `CLAUDE_CODE_DISABLE_THINKING=1`; `MAX_THINKING_TOKENS=<int>`; `ultrathink` keyword | external-OK |
| Cap main-loop output | `CLAUDE_CODE_MAX_OUTPUT_TOKENS=<int>` | external-OK |

</details>

## Don't-port (this layer is richer)
verification (`/verify` tiered + `codex review --uncommitted`); planning (recon/hammock/grill/spec); cross-model review (`/codex-review`); the `$KB_DIR` entity knowledge base (`summary.md`/`items.json` vs the native flat MEMORY.md); context save/resume. Porting the native flatter versions over these would be a regression.

## Standing caveats
- **Presence ≠ enabled.** GrowthBook defaults can leave a present feature off. Smoke-test in a scratch `CLAUDE_CONFIG_DIR`.
- **`CLAUDE_CODE_COORDINATOR_MODE` is inert** (feature DCE'd). Run the main session as an agent instead (`--agent <name>`).
- **`autoDreamEnabled` writes a flat MEMORY.md** — a second, unsynchronized writer against the `consolidate-memories` hook's store.
- **Native teams share the leader's cwd**; isolation is a separate `isolation:'worktree'` mechanism. Don't conflate them (collision risk).
- **Version drift**: tables verified against a recent build (the binary auto-updates). Re-check gating after any minor bump — presence of a flag in `--help` survives bumps, but GrowthBook defaults can flip.
