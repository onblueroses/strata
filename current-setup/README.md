# Current agent setup

Snapshot date: 2026-09-07.

This is an anonymized adaptation of a working local setup. The shared operating contract and Codex roles are supplied as files. Private integrations are described by their responsibilities so another operator can supply equivalents.

## Adopt it

1. Read [AGENTS.md](AGENTS.md) and adapt its approval boundaries to your own needs.
2. Use that file as the shared instruction source for your runtimes. Point each runtime's instruction file at it using that runtime's supported mechanism. Preserve existing files before replacing them.
3. Follow [codex/README.md](codex/README.md) to adopt the native roles. Merge configuration deliberately; do not replace an existing config wholesale.
4. Adapt the [pickup](skills/pickup-context/SKILL.md) and [close](skills/close-session/SKILL.md) skills to your memory and issue tools.
5. Read [runtime.md](runtime.md) before implementing hooks. Hook descriptions are not installed enforcement.

## What is copied and what is abstracted

| Local component | Public form |
|---|---|
| Shared cross-runtime instructions | Adapted instructions without identity, private projects, or infrastructure addresses |
| Native Codex roles | Role TOML files plus a minimal registration example |
| Delegation and knowledge conventions | Portable reference documents |
| Pickup and close workflows | Adapted skills with operator-supplied integrations |
| Configured hooks and personal skills | Inventory and integration boundaries |
| Credentials, trusted paths, connector settings, memory, issues, vault contents | Omitted |
| Vendor-provided skills and runtime packages | Referenced by purpose; not copied |

This is a curated snapshot, not an automatic sync. Model selectors reflect the inspected installation on the snapshot date; availability and configuration support must be checked in the adopting client. The files do not enable paid fallback providers.

The earlier installer at the repository root does not consume this directory. No existing user configuration is changed by reading or cloning it.
