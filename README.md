# strata

Strata carries a portable snapshot of a working multi-agent setup: shared instructions, native Codex roles, session workflows, and runtime integration notes.

Start with [current-setup/README.md](current-setup/README.md). The September 2026 snapshot reflects the maintainer's current setup, with personal details removed and private services abstracted. It favors coequal primary agents, proportionate delegation and review, and a clear separation between memory, task tracking, and project files.

## Current setup

| File | Purpose |
|---|---|
| [Shared instructions](current-setup/AGENTS.md) | Operating principles and authority boundaries across runtimes |
| [Codex configuration](current-setup/codex/README.md) | Native role definitions and a minimal configuration example |
| [Runtime integrations](current-setup/runtime.md) | Active hook responsibilities, skill inventory, and portability limits |
| [References](current-setup/reference/) | Delegation, memory, and coordination conventions |
| [Session skills](current-setup/skills/) | Portable pickup and close workflows |

The snapshot is for deliberate adoption. It contains no credentials, session history, private ledger contents, or machine-specific connector configuration. Read its adoption notes before copying configuration.

## Earlier skeleton

The root `CLAUDE.md`, `bin/`, `hooks/`, `commands/`, `agents/`, `skills/`, `reference/`, `settings.json`, and `telemetry/` retain the earlier installable skeleton. They include orchestration and process machinery that the current setup has retired. They are historical implementation material, not a description of the current setup.

[SETUP.md](SETUP.md), [CONFIG.md](CONFIG.md), and [MIGRATION.md](MIGRATION.md) apply to that earlier skeleton. `bin/strata-init` installs it; it does **not** install `current-setup/`. Existing installation behavior is unchanged.

## License

MIT. See [LICENSE](LICENSE) and [NOTICE](NOTICE). Some earlier writing skills derive from the MIT-licensed [claude-skills-library](https://github.com/Wondermonger-daydreaming/claude-skills-library).
