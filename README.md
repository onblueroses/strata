# Strata

Strata is a setup where AI agents run as one connected system. Linear is at the center, and three
**stewards** own the parts of it.

Everything here comes from a setup in daily use, and only what runs in production. Snapshot of 2026-11-12.

## What it does

Work and its results go on Linear tickets:

1. Your personal assistant, the agents or you file a ticket.
2. The Linear Steward, a persistent agent on the server, triages the ticket and decides who does it.
3. A dispatcher starts a worker on your laptop or on the server.
4. The worker does the work and posts a signed result on the ticket.

Claude Code, Codex, DeepSeek and Kimi share one set of instructions and one memory. Any of them can continue
where another stopped.

```text
you / assistant / agents ──▶ Linear ──events──▶ Linear Steward ──orders──▶ dispatcher
                               ▲                                               │
                               └────────── signed result ◀── worker (laptop or server)
```

## The stewards

A steward is a persistent owner agent on the server. It owns exactly one thing and acts on it without a request.

| Steward | Owns | What it does |
|---|---|---|
| Linear Steward | the record | Triages, labels, routes and links tickets, and decides which tickets the dispatcher starts |
| Privacy Steward | the public boundary | Reviews everything bound for public GitHub and signs its verdicts. The laptop refuses to publish without a valid signature. |
| Infrastructure Steward | the machines | Works on alarms, failed units, disks, backups and updates. Repairs what it can undo, and asks before a reboot. |

Design, and how to build another steward: [stewards/](stewards/README.md). The full diagram, the Linear
conventions, the delegation routes and the parts that this copy leaves out are in [overview.md](overview.md).

## Using it

Take the piece that you want. Each folder's README states its requirements. The `.example` files show which
values you must supply. Cloning installs nothing. Linear, Obsidian, the model clients and the assistant are
separate services. "The operator" is the owner, and the machines are `laptop` and `vps`.

```sh
python3 scripts/check_setup.py     # structure and links
python3 scripts/test_adapters.py   # offline tests of the launch adapters
```

[runtime.md](runtime.md) tells you how to read this anonymized snapshot.

## Layout

| Folder | Contents |
|---|---|
| [stewards/](stewards/README.md) | The three stewards and how to build one (design) |
| [work/](work/README.md) | The Linear client, and the design of the receiver, dispatcher, phone approvals and alerts |
| [assistant-bridge/](assistant-bridge/README.md) | Assistant to vault and tickets (design) |
| [delegation/](delegation/README.md) | Routes to other models |
| [AGENTS.md](AGENTS.md) | Shared instructions for all four runtimes |
| [claude/](claude/README.md), [codex/](codex/README.md), [deepseek/](deepseek/README.md), [kimi/](kimi/README.md) | The agents, hooks and config of each runtime |
| [memory/](memory/README.md) | Notes, the team vault, agent message records |
| [skills/](skills/README.md), [reference/](reference/README.md), [decisions/](decisions/README.md) | Methods, how-tos, and why each rule exists |

## License

[MIT](LICENSE)
