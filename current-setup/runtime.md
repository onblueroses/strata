# Current runtime snapshot

This document is an anonymized snapshot of one working installation. It describes observed wiring and portability boundaries; it is not a drop-in configuration.

## Provider and execution defaults

The active Codex CLI uses the default OpenAI service tier with ChatGPT authentication. Authentication material is stored by the local client and is not part of this snapshot. The runtime permits commands without an approval prompt and uses full local filesystem access. Reproduce those choices only after reviewing the security model of the target machine.

The configured model and reasoning settings are installation choices. The role files retain the observed native model identifiers as dated configuration examples. Account names, project paths, and trust entries are omitted.

## Hook wiring

The Codex hook configuration has these effective routes:

| Event | Matcher | Current behavior |
| --- | --- | --- |
| `SessionStart` | startup, resume, clear, compact | Runs a memory wake hook. It injects the session scope and memory authority rules, then includes the external store's wake output when available. |
| `SessionStart` | startup, resume, clear, compact | An empty hook slot is present. It does nothing and preserves the configured matcher layout. |
| `SessionStart` | compact | Runs a continuity hook. It reports repository status and saved session context after compaction. |
| `PreToolUse` | `Bash` | Runs a wrapper that sends the command to both privacy gates. A clean result from both permits the command; a refusal, timeout, missing gate, malformed event, or hook failure refuses it. |

The wrapper invokes two local gates: one for public or external actions and one for outgoing repository history. Their implementation is installation-specific and is deliberately not copied here. The wrapper uses absolute host paths in the live setup, so copying the hook file alone would create a broken or unsafe install.

The host's broader settings file also contains event hooks for session lifecycle, file edits, Bash, and notifications. Those hooks are separate from `codex/hooks.json`; this snapshot records their presence as host integration, not as portable Codex behavior. The settings file also enables a status-line command and a single installed editor plugin. Their commands, paths, credentials, and account-specific integrations stay local.

The host settings register the following responsibilities (names are abstracted):

| Event | Configured responsibilities |
| --- | --- |
| Session start | Memory wake and authority, workspace sync, stale child-session cleanup, compaction recovery, clock injection, paid-compute and backup checks |
| Before edit/write | Shared-config write boundary; ownership warning for writes |
| Before shell | Isolated-runtime boundary; outgoing-history and public-action privacy gates |
| After edit/write | Session edit receipts |
| Stop / notification | Notifications; asynchronous continuation on stop |
| Session end | Workspace sync |

Retired process hooks can remain on disk without being registered. The inspected settings do not register lint-on-write, resource-sizing warnings, sibling narration, context nudges, browser-window movement, or workspace-wide unpushed warnings.

## Enabled versus present

The native Codex memory feature is disabled. A separate memory service and its wake hook are present and active, so disabling native memory does not disable external memory behavior. The runtime should treat the external store as optional: if its executable or store is absent, report that wake is unavailable and continue from current files and other authoritative sources.

The live skill directory contains these personal skills:

| Skill | Purpose |
| --- | --- |
| `pickup-context` | Reconcile current files, repository instructions, active work, decisions, and optional memory or issue ledgers into a short orientation. |
| `close-session` | Reconcile completed work, verification, follow-ups, and restart context at the end of a session. |
| `cold-email` | Draft a constrained, personal cold-outreach message from verified recipient context. |
| `outreach-atlas` | Build and audit a sourced prospect or outreach data layer. |
| `research-viz` | Create diagrams or interactive research visualizations. |
| `triage` | Route inbound material to an owner and tracking level without resolving it. |

The installation also has bundled or vendor-provided skills elsewhere in the client skill search path. They are available to the host runtime but are not vendored in this snapshot. A skill being installed on the host does not make it part of the portable core.

## Install links and portability

The local install script links the shared instruction file, hook configuration, role definitions, and selected skill directories into the Codex home directory. It repairs missing or wrong symlinks and reports regular files as blocked rather than replacing them. It also links a small set of shared personal skills. Existing unrelated skills remain untouched.

The script currently embeds the source repository location and assumes a Unix shell, symlinks, Python, and a writable Codex home. A portable installer must replace those with a user-selected repository root and runtime home, validate source files before linking, and make no assumptions about a particular home directory.

## External services

The live workflow can consult an external memory store and an issue or work ledger. Those services are optional adapters, not requirements of the portable skills. The skills below name the information they need and define read-only fallback behavior; they do not invent endpoints, credentials, or client commands. A target installation may provide equivalent adapters, local files, or no adapter at all.

Keep credentials in the target runtime's secret store. Keep account-specific MCP integrations, private project inventories, trust lists, telemetry, session databases, and host paths out of this directory.
