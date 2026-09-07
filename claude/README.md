# Claude native setup

This directory is a sanitized snapshot of the Claude runtime's native agent layer. Claude is one coequal primary alongside Codex and DeepSeek; the primary runtime may delegate bounded work to native Claude agents, subscription-backed Codex tiers, or the authorized DeepSeek route. Provider choice changes mechanics and metering, not task authority.

## Contents

- `agents/`: five native Claude agent definitions adapted from the live setup.
- `settings.example.json`: a small allowlist of non-secret settings observed in the live configuration. It omits permissions, hooks, credentials, MCP endpoints, plugins, paths, and notification commands.
- `hooks.example.json`: the active hook event and matcher topology wired through the repository's portable adapter.

## Adoption

Copy or merge the agent files into the target Claude agents directory after reviewing each one. Preserve existing files until replacements are understood. Merge only the safe settings keys that fit the target account and client version; do not replace a complete settings file with this example.

Use the shared contract at the repository root as the instruction source for all runtimes. If the target runtime supports a shared instruction path, create its supported link or include mechanism to that file after checking existing configuration. Preserve runtime-specific additions at the target.

The live setup registers hooks for memory wake, lifecycle state, policy checks, and observation. Merge the `hooks` object from `hooks.example.json` only after replacing `__STRATA_ROOT__` and supplying `STRATA_ADAPTERS_FILE` with one nonempty argv list per event. The adapter forwards raw hook input and output for generic events, fails closed on adapter errors, and runs both privacy gates for the combined `privacy` event. Test the wiring before enabling it. Generic hooks use a 20-second timeout; privacy uses 40 seconds because it runs two bounded gates.

Claude uses the native Anthropic client route. Verify that client's account and provider before work. Cross-runtime Codex launches require ChatGPT subscription authentication; DeepSeek launches require their own verified provider and explicit metered-spend authority. Preserve the primary/delegate boundary in every route.
