# Shared native hook adapters

The local setup shares memory, privacy, continuity, ownership, notifications, and workspace services across runtimes. The service implementations contain operator-specific policy and infrastructure. This directory supplies an executable adapter boundary and the native runtime folders supply registration templates.

Copy `adapters.example.json` to your private `.local/` configuration and set `STRATA_ADAPTERS_FILE` to its absolute path. Each value is an argument vector for your local executable, such as `["python3", "your-script.py"]`; use absolute executable/script paths in your private configuration. Empty arrays are unconfigured, not working no-op protections. The adapter does not expand shell strings, environment variables, or path placeholders in these vectors.

Replace `__STRATA_ROOT__` in each runtime's hook template with your checkout path. Merge registrations into the existing native configuration. Enable a registration only after supplying and testing its adapter. Do not copy trust hashes or replace existing settings wholesale. Codex requires native hook trust approval after command changes.

Each adapter receives the original native JSON hook payload on stdin. It returns zero only on a clean result; any nonzero result, timeout, malformed configuration, or missing command produces a refusal with exit 2. Ordinary hook adapters must emit the output shape expected by their native runtime. Memory wake is the exception: it emits plain text, which this bridge wraps as SessionStart context. Missing memory reports unavailable; it never supplies a fabricated wake or grants write authority.

The `privacy` event runs **both** `privacy-public` and `privacy-push` in sequence. Both must return zero. Each has an 18-second outer timeout, and each configured scanner must apply its own tighter bounds. Register this hook with enough runtime time for both. Claude command-hook timeouts are expressed in seconds; see the [native hooks reference](https://code.claude.com/docs/en/hooks). A missing privacy adapter refuses shell work. These adapters enforce only the command events actually registered by the native runtime; they are not an OS sandbox or a credential boundary.

## Integration contracts

| Adapter | Local responsibility |
|---|---|
| Memory wake/core | Bounded recall and runtime/role-appropriate authority context |
| Continuity/edit receipts | Session-specific recovery and changed-file records |
| Privacy public/push | Secrets on all outbound targets; private identifiers unless every target is proven private |
| Ownership/config write | Scope coordination and shared-configuration write boundaries |
| Workspace sync | Operator-controlled durable workspace synchronization |
| Notifications/async continuation | Native notifications and explicitly owned continuation lifecycle |
| Clock, compute, backup | Time context and checks against the operator's actual infrastructure |

The memory store, issue tracker, document vault, Chrome integration, and provider credentials remain separate dependencies. The shared instructions and skills specify how to use them. This snapshot does not include personal records, remote services, or copied authentication.
