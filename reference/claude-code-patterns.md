<!-- keywords: harness, hook, permission context, notification, bootstrap, tool pool, claude code internals, deferred init, stream event -->
# Claude Code Internal Patterns

Transferable architectural patterns from studying Claude Code's internal architecture (1902 TS files, 207 commands, 184 tools, 38 subsystems). Derived from studying a Python reconstruction of Claude Code and reference snapshots of the original system.

These patterns inform how to build on top of Claude Code effectively - working with the system's grain, not against it.

## Quick Nav

| Pattern | Jump to | Apply when |
|---------|---------|-----------|
| ToolPermissionContext | Permission Model | Spawning subagents, defining tool access |
| Deferred Init | Deferred Initialization | MCP server config, plugin loading, startup optimization |
| Typed Notifications | Notification Types | Hook design, notification routing |
| Hook Concerns | Hook Concern Separation | Adding or modifying hooks |
| Stream Events | Stream Event Protocol | Building observability, session tracking |
| Simple Mode | Simple Mode Restrictions | Restricting tool access for read-only agents |
| Tool Pool Assembly | Tool Pool Assembly | Understanding how Claude Code filters available tools |
| Bootstrap Sequence | Bootstrap Sequence | Understanding session lifecycle |

---

## Permission Model

<details>
<summary>Permission Model</summary>

Claude Code uses `ToolPermissionContext` with two axes:

```
deny_names: frozenset[str]    # exact tool name match (case-insensitive)
deny_prefixes: tuple[str, ...]  # prefix match (case-insensitive)
```

A tool is blocked if its name matches any deny_names entry OR starts with any deny_prefixes entry. Tool pool assembled fresh per session via `assemble_tool_pool(simple_mode, include_mcp, permission_context)`.

**Three separate permission handlers** for different execution contexts:
- `coordinatorHandler` - multi-agent coordination mode, different denial behavior
- `interactiveHandler` - standard interactive CLI, prompts user on denial
- `swarmWorkerHandler` - background/batch agents, auto-deny without prompting

The critical separation: permission *context* (what's denied) is data. Permission *handler* (what happens on denial) is behavior. Same denial can prompt a user in interactive mode but silently skip in swarm mode.

**Local harness application:**

| Profile | Context | Tool access |
|---------|---------|-------------|
| Evaluator | /harness evaluators, /verify reviewers | Read, Grep, Glob, Bash(read-only) |
| Explorer | /deep-understand, research agents | Read, Grep, Glob, WebSearch, WebFetch |
| Reviewer | /review code-reviewer | Read, Grep, Glob, Bash |
| Generator | /harness generators | Full access (default) |
Enforcement is through agent YAML `tools:` field and skill prompt instructions, not runtime hooks.

Source: `src/permissions.py:6-20`, `src/tool_pool.py:28-37`, `reference_data/subsystems/hooks.json` (toolPermission handlers).

</details>

## Deferred Initialization

<details>
<summary>Deferred Initialization</summary>

Claude Code gates four subsystem initializations behind a trust check:

```
plugin_init:    only when trusted=True
skill_init:     only when trusted=True
mcp_prefetch:   only when trusted=True
session_hooks:  only when trusted=True
```

Nothing loads until trust is established. This is the 5th stage of the 7-stage bootstrap.

**Local harness application:**

Domain-specific MCP servers should not load globally. Move them to project-level `.claude/settings.json` so they only activate in relevant working directories:

- **Global** (used everywhere): your always-on servers (e.g. code-host, browser-automation, docs-lookup)
- **Global** (cross-project infrastructure): automation, notebook, workspace, and browser-devtools servers
- **Project-level** (frontend projects): shadcn-ui, magicui, tailwindcss, aceternityui, google-maps-code-assist

Claude Code's own `ToolSearch` tool already implements deferred loading for MCP tools - tools aren't available until discovered. This IS the deferred init pattern applied to tool availability.

Reference docs that load on trigger (the `$STRATA_HOME/reference/` system) are another instance of deferred init at the prompt level.

Source: `src/deferred_init.py:23-31`, `src/bootstrap_graph.py`.

</details>

## Notification Types

<details>
<summary>Notification Types</summary>

Claude Code's hooks subsystem has 14+ typed notifications in `hooks/notifs/`:

| Notification | What it does |
|-------------|-------------|
| `useRateLimitWarningNotification` | Warns when approaching rate limits |
| `useDeprecationWarningNotification` | Flags deprecated features |
| `useMcpConnectivityStatus` | Reports MCP server connection state |
| `usePluginInstallationStatus` | Plugin install progress |
| `usePluginAutoupdateNotification` | Plugin auto-update alerts |
| `useLspInitializationNotification` | LSP server init state |
| `useModelMigrationNotifications` | Model version changes |
| `useStartupNotification` | Session start info |
| `useFastModeNotification` | Fast mode toggle |
| `useNpmDeprecationNotification` | npm package deprecation |
| `useSettingsErrors` | Config validation errors |
| `useInstallMessages` | Installation progress |
| `useIDEStatusIndicator` | IDE integration state |
| `useTeammateShutdownNotification` | Multi-agent teammate shutdown |
| `useAutoModeUnavailableNotification` | Auto-mode availability |
| `useCanSwitchToExistingSubscription` | Subscription management |

Each notification type fires reactively (not polled). No central event bus - notifications are concern-specific hooks.

**Local harness application:**

Route through `notify.sh` with urgency levels:
- `critical`: permission denials, stop gate blocks, deployment failures
- `normal`: compaction suggestions, idle prompts, skill completions
- `low`: tracking events, observability, status updates

Use `notify-send --urgency=` flag for desktop notification routing.

Source: `reference_data/subsystems/hooks.json`.

</details>

## Hook Concern Separation

<details>
<summary>Hook Concern Separation</summary>

Claude Code's 104 hook modules are organized by concern:

```
hooks/
  notifs/              # 14+ notification types (reactive alerts)
  toolPermission/      # 3 permission handlers (coordinator, interactive, swarmWorker)
  fileSuggestions.ts   # File completion suggestions
  unifiedSuggestions.ts # Combined suggestion engine
  renderPlaceholder.ts  # UI placeholder rendering
  useAfterFirstRender.ts # Post-render lifecycle
```

Three clean categories: **notifications** (what to tell the user), **permissions** (what to allow/deny), and **UI helpers** (rendering concerns).

**Local harness application:**

Name hooks with concern prefixes:
- `session-*`: initialization (ensure-daily-note, check-dev-servers, cleanup-verify-markers)
- `gate-*`: stop enforcement (verify-gate)
- `lifecycle-*`: session end/sync (auto-end-fallback, sync-life-repo)
- `context-*`: context management (context-nudge, pre-compaction-save, suggest-compact)
- `quality-*`: code quality checks (search-path-guard, lint-on-write, crlf-check)
- `observe-*`: tracking/observability (track-edits, track-session-events, track-skill-runs)

Source: `reference_data/subsystems/hooks.json`.

</details>

## Stream Event Protocol

<details>
<summary>Stream Event Protocol</summary>

Claude Code emits structured events in a fixed sequence:

```
message_start    -> {session_id, prompt}
command_match    -> {commands: [...]}
tool_match       -> {tools: [...]}
permission_denial -> {denials: [...]}
message_delta    -> {text: "..."}
message_stop     -> {usage: {input_tokens, output_tokens}, stop_reason, transcript_size}
```

Each event has a `type` field. The sequence is guaranteed. Events are structured (JSON objects), not free-form text.

**Local harness application:**

Standardize hook tracking output as JSONL:
```json
{"type":"edit","ts":"2026-03-31T14:30:00","sid":"e99dbf85","file":"/path/to/file.ts"}
{"type":"skill_invoke","ts":"2026-03-31T14:31:00","sid":"e99dbf85","skill":"harness"}
{"type":"permission_deny","ts":"2026-03-31T14:31:05","sid":"e99dbf85","tool":"Bash","reason":"..."}
```

Enables: session replay, cross-session analytics, skill effectiveness measurement.

Source: `src/query_engine.py:106-127`.

</details>

## Simple Mode Restrictions

<details>
<summary>Simple Mode Restrictions</summary>

Claude Code has a `simple_mode` flag that restricts available tools to:
- BashTool
- FileReadTool
- FileEditTool

Everything else (Agent, MCP, WebSearch, WebFetch, Cron, Task, etc.) is excluded.

`assemble_tool_pool()` takes `simple_mode` as a parameter and filters accordingly. There's also an `include_mcp` flag that controls MCP tool availability independently.

**Local harness application:**

When spawning read-only agents (Explore, research, code-reviewer), verify their tool list excludes write tools. The Agent tool's `subagent_type` already controls this:
- Explore agents: "All tools except Agent, ExitPlanMode, Edit, Write, NotebookEdit"
- Plan agents: "All tools except Agent, ExitPlanMode, Edit, Write, NotebookEdit"
- code-reviewer: "Read, Grep, Glob, Bash"

This is Claude Code's simple_mode applied at the agent level. Already working correctly.

Source: `src/tool_pool.py:28-37`, `src/tools.py`.

</details>

## Tool Pool Assembly

<details>
<summary>Tool Pool Assembly</summary>

Each session assembles its tool pool fresh:

```python
assemble_tool_pool(
    simple_mode=False,      # restrict to basic tools
    include_mcp=True,       # include MCP server tools
    permission_context=None  # ToolPermissionContext for denials
)
```

The tool pool is not a fixed set - it's computed from the registry, filtered by mode flags and permission context. Tools from MCP servers are included conditionally.

**Local harness application:**

Claude Code's `ToolSearch` tool is the user-facing manifestation of this pattern. "Deferred tools" are not loaded until discovered via ToolSearch. This means:
- MCP tools aren't in the active tool pool until explicitly searched for
- Tool availability is dynamic, not static
- The system already implements lazy tool loading

This validates the approach of moving domain-specific MCP servers to project-level settings - they only contribute tools when the project context makes them relevant.

Source: `src/tool_pool.py`, `src/tools.py`.

</details>

## Bootstrap Sequence

<details>
<summary>Bootstrap Sequence</summary>

Claude Code initializes in 7 stages:

```
1. Top-level prefetch side effects
2. Warning handler and environment guards
3. CLI parser and pre-action trust gate
4. setup() + commands/agents parallel load
5. Deferred init after trust
6. Mode routing: local / remote / ssh / teleport / direct-connect / deep-link
7. Query engine submit loop
```

Stage 5 (deferred init) is the trust gate. Nothing from the plugin/skill/MCP ecosystem loads before trust is established.

Stage 6 (mode routing) determines whether this is a local session, remote bridge session, SSH tunnel, etc. The coordinator module routes between these modes.

**Local harness application:**

Local equivalent bootstrap:
1. SessionStart hooks fire (ensure-daily-note, check-dev-servers, cleanup-verify-markers)
2. CLAUDE.md loads (system prompt with all constraints)
3. MEMORY.md loads (auto-memory with entity index)
4. Skills list loads (from settings.json descriptions)
5. MCP servers initialize (all at once - this is where deferred init would help)
6. First user prompt triggers UserPromptSubmit hook (context-nudge)
7. Agent loop begins

The gap is at stage 5: no trust gate, no selective loading. Moving domain-specific MCPs to project-level addresses this.

Source: `src/bootstrap_graph.py`.

</details>
