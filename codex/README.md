# Native Codex roles

This directory contains a portable role matrix for subscription-backed native Codex work. The seven files under [`agents/`](agents/) define read-only researchers and reviewers plus workspace-writing workers. The model selectors reflect the inspected installation on 2026-09-07; verify current catalog availability before use.

## Adoption

1. Read the repository [operating contract](../AGENTS.md) and [delegation reference](../reference/model-delegation.md).
2. Copy or merge `agents/*.toml` into the target Codex agent directory. Preserve existing role files until you have reviewed each replacement.
3. Merge [`config.example.toml`](config.example.toml) into the target configuration. Preserve authentication, trust, MCP, plugin, and UI settings already present.
4. Verify that the target session reports the subscription-backed OpenAI provider before launching or spawning work. The source installation's ChatGPT-authenticated/default-OpenAI status is a dated observation, not a guarantee about the target account.
5. Adapt lifecycle hooks, memory commands, task-ledger commands, and external integrations to the target environment before enabling them. The role files contain boundaries and responsibilities; they do not install private infrastructure.

Delegates return findings and memory candidates to the primary. The primary owns acceptance, shared memory, task-ledger state, and external side effects. Use the strong, bounded, and mechanical tiers according to failure cost and task shape.

## Primary settings and hooks

The example now records the inspected primary model (`gpt-6-astra`), reasoning effort, disabled native memory, and full-access execution settings. These are source defaults to review, not required permission levels for a new installation. Native role files retain their own model and sandbox choices.

[hooks.example.json](hooks.example.json) preserves the native event topology. Replace `__STRATA_ROOT__`, configure the [shared adapters](../integrations/README.md), merge the registration, and approve hook trust through the native client. The empty SessionStart slot intentionally preserves the source layout.

The separate metered DeepSeek/Codex bridge is described under [DeepSeek](../deepseek/README.md). Do not use it as an automatic subscription fallback.
