# Codex operating layer

config.example.toml records the subscription-backed OpenAI default, sandbox and approval defaults, and disabled native memory. Session memory arrives from the external OptMem wake. hooks.json registers that wake, compaction continuity, and the shared privacy gate. The empty second SessionStart entry preserves native hook trust indices. hooks.example.json shows the same core registration with checkout-relative placeholders.

Run `codex/install.sh` to link the shared constitution, hooks, role files, and skills into CODEX_HOME. `codex/install.sh --check` audits those links without writing. The installer leaves unmanaged files and credentials in place. Run `bash codex/tests/test_install.sh` to exercise the link and gate contracts offline.

Codex stores a trusted hash per hook entry. After changing a command, review and approve the new hook in the native startup UI; until then it may be skipped. The PreToolUse script relays only permit or refuse statuses from both privacy gates and refuses malformed payloads, missing gates, timeouts, and crashes. The empty SessionStart slot must stay in place when editing hooks.json.

Local collaboration through [hcom](https://github.com/aannoo/hcom) is optional. [hcom-hooks.example.json](hcom-hooks.example.json) holds its Codex event commands for PreToolUse, PostToolUse, SessionStart, Stop, and UserPromptSubmit. Merge them after installation; they do not replace the privacy gate. Load the issue queue explicitly when picking up work.
