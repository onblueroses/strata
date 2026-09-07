# Strata

An anonymized copy of a native multi-provider agent setup: Claude Code, Codex, DeepSeek Harness, and Kimi Code share an operating contract while keeping their own clients, model providers, authentication, and delegation mechanics.

Snapshot: 2026-09-07. The files reflect the inspected local installation; model availability and client configuration support can change.

## Runtimes and providers

| Runtime | Provider / access | What ships here |
|---|---|---|
| [Claude Code](claude/README.md) | Anthropic through the native client | Five native agents, selected settings, active hook registration topology |
| [Codex](codex/README.md) | OpenAI with ChatGPT subscription authentication | Seven native roles, primary settings, native hook registrations |
| [DeepSeek](deepseek/README.md) | Metered official DeepSeek API | Primary/delegate instructions, Harness overlay, provider examples, explicit-spend launch adapter, alternate route documentation |
| [Kimi Code](kimi/README.md) | Native Kimi OAuth | Shared-instruction adoption and native provider/model/search/fetch configuration |

Claude, Codex, and the user-facing DeepSeek primary are coequal operators. Kimi reads the same workspace instructions. Primary authority does not transfer to a delegate merely because it uses a powerful model. The [provider inventory](providers.toml) distinguishes each runtime, provider, model, role, and access route.

Codex's subscription rule applies to native Codex delegation. DeepSeek API calls are separately metered work requiring explicit spend authority; they are never an automatic quota fallback. The optional Codex/LiteLLM DeepSeek bridge is a distinct route, not OpenAI subscription inference.

## Shared setup

- [AGENTS.md](AGENTS.md) is the shared contract; `CLAUDE.md` links to it.
- [delegation/](delegation/README.md) supplies a portable Codex subprocess wrapper and cross-runtime routing instructions.
- [integrations/](integrations/README.md) supplies a hook adapter, configuration template, and contracts for the private services behind native hooks.
- [skills/](skills/README.md) carries the active personal skills and their support files, including outreach, research visuals, triage, deployment, and session workflows.
- [reference/](reference/) carries memory, delegation, and task-ledger conventions.
- [runtime.md](runtime.md) records source coverage, differences from the live installation, and dependencies.

## Adopt it

Read the shared contract and adapt its approval boundaries to your environment. Follow each runtime's README to link instructions, copy or merge native roles, and merge the selected settings. Keep existing files until replacements have been reviewed.

Choose the intended provider and authenticate through its native client or private secret store. Supply local service adapters, replace hook-template path placeholders, and review native hook trust before enabling registrations. The examples contain no credentials, trusted-machine records, personal memory, task data, or private endpoints.

Runtime clients, DeepSeek Harness, the optional LiteLLM bridge, memory/issue/vault services, and vendor-bundled skills remain external dependencies. The hook topology and private service boundaries are abstracted; this repository does not pretend those services come installed. Cloning it does not alter your live setup or start a paid process.

## Validation

With Python 3.11 or newer, run:

```sh
python3 scripts/check_setup.py
python3 scripts/test_adapters.py
```

CI validates runtime coverage, native configuration, hooks, skills, links, and adapter behavior. Adapter tests use local stubs and do not call model providers. Privacy checks complement manual review; they are not a proof that arbitrary future content is safe to publish.

## License

[MIT](LICENSE).
