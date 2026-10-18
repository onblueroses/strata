# Strata

An anonymized copy of a native multi-provider agent estate: Claude Code, Codex, DeepSeek and Kimi share one
operating contract while keeping their own clients, providers, authentication and delegation mechanics; around
them sit a personal memory method, a team knowledge vault, a work ledger with its own dispatcher and workers, a
bridge to a messaging-only assistant, and the skills the agents run.

Snapshot: 2026-10-17. [runtime.md](runtime.md) says how the copy was made and what to assume while reading it.

## Map

| Layer | What ships | Start at |
|---|---|---|
| Contract | The shared instruction file every runtime links to, and the agent-config repo's own knowledge | [AGENTS.md](AGENTS.md), [claude/AGENTS.md](claude/AGENTS.md) |
| References | The documents the contract opens on cue: memory contract, delegation, peers, tickets, compute, VPS, Bend | [reference/](reference/README.md) |
| Runtimes | Claude agents, hooks and gates; Codex roles, hooks and installer; DeepSeek primary and harness overlay; Kimi config | [claude/](claude/README.md), [codex/](codex/README.md), [deepseek/](deepseek/README.md), [kimi/](kimi/README.md) |
| Memory | OptMem: the one-line note method, its wake and nap, our proof layer; the company brain: an Obsidian vault with a rule book, two synced copies, a sweep and an MCP server | [memory/](memory/README.md) |
| Work | Linear as the ledger; a webhook receiver, the one dispatcher, per-ticket workers over forced-command SSH, a phone approval gate, a bounded operator wrapper, alarms over ntfy | [work/](work/README.md) |
| Assistant bridge | A vault subset published to a private repo for a messaging-only assistant that files tickets and opens pull requests; apply, respond and check jobs; owner authority held on the server | [assistant-bridge/](assistant-bridge/README.md) |
| Delegation | Codex tiers, the free-model silo, provider bridges on demand, the search bridge, the portable subprocess wrapper | [delegation/](delegation/README.md) |
| Skills | Research atlases, outreach, triage, deployment, session continuity, visuals, site obscuring | [skills/](skills/README.md) |
| Decisions | The rulings behind the rules, each with its reason and its reopening bar | [decisions/](decisions/README.md) |

## Adopt it

Read the contract and adapt its approval boundaries to your situation: who taps, what is tier-3 destruction,
which provider is banned. Then take one layer at a time. Each folder's README says what the layer depends on,
how its pieces talk, and which values are placeholders. Keep your existing files until a replacement is
understood; merge settings, never replace a settings file wholesale; approve hook trust in each runtime
deliberately. Cloning this repository changes nothing on your machine and starts no paid process.

The runtime clients, OptMem, the Obsidian vault and its MCP server, Linear, ntfy and the messaging assistant are
external dependencies. This tree carries the contracts, the glue and the rulings; it does not pretend those
services come installed.

## Validation

With Python 3.11 or newer:

```sh
python3 scripts/check_setup.py
python3 scripts/test_adapters.py
```

Each component with tests runs them offline; the READMEs name the runner. CI runs the same.

## License

[MIT](LICENSE). Upstream projects this tree builds on keep their own licenses and are pointed to, not copied.
