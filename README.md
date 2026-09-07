# Strata

This repository contains an anonymized, portable snapshot of a local agent setup. It describes operating boundaries, native Codex roles, and the contracts needed to adapt them to another operator's environment.

## Contents

- [`AGENTS.md`](AGENTS.md): shared operating contract; `CLAUDE.md` links to the same file.
- [`codex/`](codex/): native role definitions and provider configuration example.
- [`reference/`](reference/): delegation, memory, and follow-up contracts.
- [`skills/`](skills/): portable pickup and close workflows.
- [`runtime.md`](runtime.md): observed hook wiring, skill inventory, and integration boundaries.

The snapshot preserves coequal primary operators, subscription-backed native model tiers, privacy and approval boundaries, append-only memory separation, task-ledger practice, and session lifecycle guidance. It omits credentials, private integrations, service addresses, issue identifiers, machine trust state, and operator-specific paths.

## Manual adoption

Read `AGENTS.md` and adapt its approval boundaries, privacy rules, browser policy, memory layer, and task ledger to the target environment. Copy or merge only the parts that fit the target runtime. Keep existing instructions and configuration until their replacement is understood.

Read [`codex/README.md`](codex/README.md), then copy the role files into the target Codex agent directory and merge the example configuration. Verify the authenticated provider, model availability, and account permissions before launching work. Adapt lifecycle hooks and external integrations manually; this snapshot does not install them.

Review every adopted instruction and configuration file before enabling it. The target operator remains responsible for credentials, trust decisions, provider selection, and external state.

## Validation

Run `python3 scripts/check_setup.py` with Python 3.11 or newer. CI checks the same portable files, role configuration, and links.

## License

[MIT](LICENSE).
