# Native setup coverage

Snapshot date: 2026-09-07. The source is the live native settings, active skill and agent directories, shared instructions, and installed delegation wrappers. No session transcripts, authentication stores, trust records, or private workspace data are copied.

| Source surface | Portable counterpart | Adaptation |
|---|---|---|
| Shared Claude/Codex/Kimi instruction spine | Root `AGENTS.md` and `CLAUDE.md` link | Identity and private operations replaced with operator-supplied services |
| Claude native agents and selected settings | `claude/` | Five agent bodies retained; safe settings whitelist; credentials and machine permissions omitted |
| Claude active hook registrations | `claude/hooks.example.json` | Event topology preserved through explicit local adapters |
| Codex native roles and settings | `codex/` | Seven roles, actual primary model, subscription provider and memory-feature settings |
| Codex native lifecycle/privacy hooks | `codex/hooks.example.json` | Memory, preserved empty startup slot, compaction, and both privacy gates |
| Claude-to-Codex wrappers | `delegation/codex-run.py` | Native tiers, subscription preflight, authority boundary, logs and process lifecycle; private telemetry/cache removed |
| DeepSeek primary operating layer | `deepseek/` | Primary instructions, managed provider overlay, separate delegate boundary and spend guard |
| DeepSeek alternate routes | DeepSeek README and provider examples | Agentic Flash/Pro and Codex/LiteLLM bridge dependencies identified |
| Kimi native client | `kimi/` | Observed model/provider and OAuth-backed search/fetch config; token stores omitted |
| Active personal skill bodies | `skills/` | Workflows and required support files retained; private campaign examples and services generalized |

## Runtime distinctions

Claude Code uses its native Anthropic model aliases and agents; it may delegate across runtimes through an authorized wrapper. The inspected primary setting is `opus[1m]` with `xhigh` effort.

Codex uses the OpenAI provider and ChatGPT authentication. Its inspected primary is `gpt-6-astra`; native workers select Sol, Terra, or Luna through their role files. The source disables native memory and uses an external wake service. The source's full-access and no-prompt settings are recorded in the example and require deliberate review before adoption. The portable subprocess delegate defaults to read-only rather than inheriting full access.

DeepSeek has a separate user-facing primary and bounded delegates. Its source primary is one-shot/headless and requires explicit spend confirmation. Native child/fork/workflow surfaces are disabled because that harness version does not enforce weaker child memory authority. The additional `ds-flash` and `ds-pro` routes use an agentic pydantic-ai harness; `ds-codex` uses a separately configured LiteLLM bridge. These are metered DeepSeek calls.

Kimi Code uses its own managed provider and OAuth files, with `kimi-code/k3-256k` selected in the inspected configuration. It shares the instruction spine but has no copied custom hook bridge or managed skill installer in this snapshot. Installed does not imply currently running.

## Hooks and services

Both Claude and Codex register hooks natively. The portable registration files call the [shared adapter](integrations/README.md), which requires explicitly supplied commands for memory, continuity, privacy, ownership, notifications, and workspace operations. Empty configuration does not silently pass a privacy check. The adapter is a bridge to policy implementations, not those implementations or an OS sandbox.

The Claude source registers startup memory/core, workspace sync, child-session cleanup, compaction recovery, time, compute, and backup checks; stop/notification handling; edit/write boundaries and receipts; shell isolation and two privacy gates; and end-of-session sync. Retired lint-on-write, resource-sizing warnings, sibling narration, context nudges, browser-window movement, and workspace-wide unpushed warnings are not reintroduced.

The Codex source registers memory wake, an empty startup slot preserving hook trust indices, compaction continuity, and a shell hook dispatching both public-action and outgoing-history privacy gates. Native hook approval remains a target-client responsibility.

The memory store, issue ledger, document vault, Chrome integration, remote infrastructure, and vendor skills are dependencies. Their public forms are the adapter contracts and workflows; private records, service addresses, credentials, identity, and deployment targets are absent. Source-specific cache, telemetry, resume machinery and full external harness installers are not copied blindly.
