# Native Codex roles

This directory contains a portable role matrix for subscription-backed native Codex work. The seven files under [`agents/`](agents/) define read-only researchers and reviewers plus workspace-writing workers. The model selectors reflect the inspected installation on 2026-09-07; verify current catalog availability before use.

## Adoption

1. Read the repository [operating contract](../AGENTS.md) and [delegation reference](../reference/model-delegation.md).
2. Copy or merge `agents/*.toml` into the target Codex agent directory. Preserve existing role files until you have reviewed each replacement.
3. Merge [`config.example.toml`](config.example.toml) into the target configuration. Preserve authentication, trust, MCP, plugin, and UI settings already present.
4. Verify that the target session reports the subscription-backed OpenAI provider before launching or spawning work. The source installation's ChatGPT-authenticated/default-OpenAI status is a dated observation, not a guarantee about the target account.
5. Adapt lifecycle hooks, memory commands, task-ledger commands, and external integrations to the target environment before enabling them. The role files contain boundaries and responsibilities; they do not install private infrastructure.

Delegates return findings and memory candidates to the primary. The primary owns acceptance, shared memory, task-ledger state, and external side effects. Use the strong, bounded, and mechanical tiers according to failure cost and task shape.
