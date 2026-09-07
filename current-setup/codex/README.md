# Portable Codex setup snapshot

This directory is a sanitized snapshot of the current native Codex role matrix. The seven
role files under `agents/` are intended to be copied into a user's Codex home as
`$CODEX_HOME/agents/*.toml`; native roles are discovered from that directory. They are a
portable starting point, not a promise that the named model IDs remain available.

## Safe adoption

1. Copy `agents/*.toml` into the target `$CODEX_HOME/agents/` directory.
2. Merge the settings in `config.example.toml` into the local `config.toml`, adapting the
   model and provider choices to the account and CLI version in use.
3. Keep the target machine's own authentication, project trust, MCP, plugin, and UI settings
   in its private config. This snapshot intentionally omits them. The current setup uses the
   OpenAI provider with ChatGPT subscription authentication; no API key is included here.

The source setup also has lifecycle and privacy hooks, but those commands refer to local
memory, continuity, and policy infrastructure. They are intentionally not shipped here:
adapt each hook to the target machine before enabling it, and establish its local trust state
through the Codex UI or the documented CLI flow. Do not copy private hook commands verbatim.

This is a configuration snapshot only. It contains no installer, architecture rebuild, login
state, credentials, private paths, MCP endpoints, or machine trust records.
