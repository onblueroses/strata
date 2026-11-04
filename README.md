# Strata

A working setup for running several AI coding agents as one team: Claude Code, Codex, DeepSeek and Kimi
share one set of instructions and one memory. They hand work to each other, and they pick up tickets from a
queue on their own.

Everything here comes from a setup in daily use. Snapshot of 2026-10-17.

## What it does

- **One instruction file for every agent.** [AGENTS.md](AGENTS.md) tells all four runtimes how to work, and
  each one adds a few lines of its own.
- **Shared memory.** Agents write short one-line notes ([OptMem](memory/optmem/README.md)). At the start of each
  session a hook shows the agent the notes that matter, so it picks up where the last one stopped.
- **Delegation.** A main session can send work to a stronger or cheaper model, or to a free one, through small
  command-line wrappers.
- **A ticket queue that runs itself.** Tickets filed in Linear are picked up by a dispatcher. It starts an agent
  on the laptop or the server, and that agent reports back on the ticket.
- **A team notebook.** An Obsidian vault holds what the team knows. Agents read and write it through an MCP
  server.
- **Skills.** Reusable methods for research, outreach, triage, deploying and wrapping up a session.

## The agents

| Agent | Role | Lives in |
|---|---|---|
| **Claude Code** | Main session. Hooks load memory at start and restore context after compaction | [claude/](claude/README.md) |
| ↳ orchestrator | Plans and hands heavy work to other models, then checks and combines the results | [claude/agents/](claude/agents/) |
| ↳ code-reviewer, quick-research, web-mapper, knowledge-lookup | Small helpers for review, quick lookups, web research and memory search | [claude/agents/](claude/agents/) |
| **Codex** | Equal main session, and the queue's usual worker | [codex/](codex/README.md) |
| ↳ load-bearing worker, adversarial reviewer | Strong tier, for hard work and reviews that try to break things | [codex/agents/](codex/agents/) |
| ↳ implementation worker | Middle tier, for bounded coding tasks | [codex/agents/](codex/agents/) |
| ↳ mechanical worker | Cheap tier, for bulk and repetitive work | [codex/agents/](codex/agents/) |
| ↳ docs / systems researcher, knowledge lookup | Read-only research and memory search | [codex/agents/](codex/agents/) |
| **DeepSeek** | A third main session with its own profile, plus fast and pro tiers for delegated work | [deepseek/](deepseek/README.md) |
| **Kimi** | Config and instructions for Kimi Code | [kimi/](kimi/README.md) |
| **Free models** | Free web research and general tasks, run in a sandbox | [delegation/](delegation/README.md) |
| **Dispatcher** | Picks up queued tickets and starts one worker per ticket | [work/dispatcher/](work/dispatcher/) |
| **Steering agent** | Watches the ticket stream, files and labels tickets, never does the work | [work/](work/README.md) |
| **Messaging assistant** | A personal assistant reached only by chat. It files tickets and suggests vault edits | [assistant-bridge/](assistant-bridge/README.md) |

## How it fits together

```text
              AGENTS.md (shared instructions)
                        │
     ┌──────────────┬───┴──────────┬──────────────┐
  Claude Code     Codex       DeepSeek         Kimi
     │   │                         ▲
     │   └── delegate ─────────────┘ (and free models)
     ▼
  memory notes · team vault · decision records

  you / assistant / agents ──ticket──▶ Linear ──▶ dispatcher ──▶ worker (laptop or server) ──▶ reply on ticket
```

## What's in the repo

| Folder | Contents |
|---|---|
| [AGENTS.md](AGENTS.md) | The shared instructions |
| [claude/](claude/README.md), [codex/](codex/README.md), [deepseek/](deepseek/README.md), [kimi/](kimi/README.md) | Each runtime's agents, hooks, config and installer |
| [memory/](memory/README.md) | OptMem notes and the team vault |
| [work/](work/README.md) | Ticket queue: webhook receiver, dispatcher, workers, alerts |
| [delegation/](delegation/README.md) | Wrappers for sending work to other models |
| [skills/](skills/README.md) | Research, outreach, triage, deploy, session continuity, diagrams |
| [reference/](reference/README.md) | Longer how-tos that the instructions point to |
| [decisions/](decisions/README.md) | Why each rule exists, and when to change it |
| [integrations/](integrations/README.md) | Adapters for wiring the hooks to your own scripts |

## Using it

Read [AGENTS.md](AGENTS.md), then take whichever piece you want. Each folder's README says what it needs and
which values to fill in (see the `.example` files). Cloning installs nothing. Linear, Obsidian and the model
clients are separate services you set up yourself.

Names are placeholders: "the operator" is the owner, and the machines are `laptop` and `vps`.

```sh
python3 scripts/check_setup.py     # checks structure and links
python3 scripts/test_adapters.py   # offline tests
```

## License

[MIT](LICENSE)
