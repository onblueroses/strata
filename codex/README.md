# Codex operating layer

config.example.toml records the subscription-backed OpenAI default, sandbox and approval defaults, and disabled native memory. Session memory arrives from the external OptMem wake. hooks.json registers that wake and compaction continuity. hooks.example.json shows the same registration with checkout-relative placeholders.

Run `codex/install.sh` to link the shared constitution, hooks, role files, and skills into CODEX_HOME. `codex/install.sh --check` audits those links without writing. The installer leaves unmanaged files and credentials in place. Run `bash codex/tests/test_install.sh` to exercise the link contract offline, and `bash codex/tests/test_optmem_start.sh` for the start hook (stub memo, scratch HOME).

Codex stores a trusted hash per hook entry. After changing a command, review and approve the new hook in the native startup UI. Codex logs no hook runs of its own, so the hooks write a row each through `hooks/record.py`; a missing recorder changes nothing else.

Local collaboration through [hcom](https://github.com/aannoo/hcom) is optional; hcom adds its hooks at each `hcom codex` launch and keeps none in hooks.json. Load the issue queue explicitly when picking up work.
