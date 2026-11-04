# Strata

A setup where AI agents run as one connected system instead of separate chat windows. You can message an
assistant from your phone; a ticket appears; a dispatcher wakes an agent on your laptop or server; the agent
does the work, can hand parts to other models, and reports back on the ticket. Claude Code, Codex, DeepSeek
and Kimi share one set of instructions and one memory, so any of them can pick up where another stopped.

Everything here comes from a setup in daily use. Snapshot of 2026-10-17.

## How it connects

```text
   you (phone, chat)                       you (terminal)
          │                                      │
          ▼                                      ▼
  messaging assistant ──files tickets──▶    Linear    ◀──files / replies── Claude · Codex · DeepSeek · Kimi
  (reads the team vault,                      │                                   │
   suggests edits)                            │ webhook, in seconds               │ delegate
                                              ▼                                   ▼
                                     steering agent                    stronger / cheaper / free models
                                     (labels, routes, you can chat with it)
                                              │
                                              ▼
                                         dispatcher ──SSH──▶ worker on the laptop  (Codex, or Claude with your browser)
                                              │        └──▶ worker on the server (Codex)
                                              │                      │
                                              └──── signed result posted back on the ticket
                                                                     │
                                               shared memory · team vault ◀┘
```

## The pieces

**Messaging assistant → laptop.** The assistant is a personal AI you talk to by chat. It has no API. Through
the [bridge](assistant-bridge/README.md) it reads a published copy of the team vault, suggests vault edits as
pull requests, and files Linear tickets on your behalf. One of those tickets can be "do X on my laptop": the
dispatcher picks it up, and a Claude Code worker on the laptop does it, browser included. A message from your
phone can end up driving your own machine.

**Linear as the switchboard.** Every piece of work is a ticket ([work/](work/README.md)). A label says who takes
it (`for:codex`, `for:claude`), and a pin says where it runs (`laptop`, `vps`). A webhook delivers each change
within seconds. Agents, the assistant and you all talk in the same ticket comments, so the conversation and
the result live in one place.

**Steering agent.** It watches the ticket stream, files and labels tickets, and answers in comments or in its
own chat. It never does the work itself.

**Dispatcher and workers.** The [dispatcher](work/dispatcher/) is the single process that claims tickets. For
each one it starts a fresh worker over SSH, on the server (Codex) or on the laptop (Codex, or Claude
Code with the browser). Workers post progress and finish with a signed result. If a worker goes quiet, the ticket comes back;
if you reply later, a follow-up starts on its own. Alerts reach your phone through ntfy
([work/alarms/](work/alarms/)).

**Delegation.** Any main session can pass work down ([delegation/](delegation/README.md)):

| Route | Model | Use |
|---|---|---|
| `codex-strong` | Codex, strong tier | Hard work and reviews that try to break things |
| `codex-fast` | Codex, cheap tier | Bulk and repetitive work |
| `ds-pro`, `ds-flash`, `dsh-agent` | DeepSeek | Another provider's view; pro and fast tiers |
| `omp-search`, `omp-inkling` | Free models | Web research and general tasks on public inputs |
| Claude [orchestrator](claude/agents/orchestrator.md) | Claude | Plans, fans work out to the routes above, checks and combines the results |

Codex has its own roles too ([codex/agents/](codex/agents/)): a load-bearing worker, an implementation worker, a
mechanical worker, an adversarial reviewer and researchers.

**Peers.** Live Claude and Codex sessions on the same machine can message each other directly
([agent communication](reference/agent-communication.md)).

**One instruction file.** [AGENTS.md](AGENTS.md) is read by all four runtimes; each adds a few lines of its
own ([claude/](claude/README.md), [codex/](codex/README.md), [deepseek/](deepseek/README.md),
[kimi/](kimi/README.md)).

**Shared memory.** Agents write one-line notes ([OptMem](memory/optmem/README.md)). At each session start a hook
shows the notes that matter, so a new session, or a different model, carries on from the last one. Team
knowledge lives in an Obsidian [vault](memory/brain/README.md) that agents, the assistant and people all read
and write.

## Repo layout

| Folder | Contents |
|---|---|
| [AGENTS.md](AGENTS.md) | Shared instructions |
| [assistant-bridge/](assistant-bridge/README.md) | Messaging assistant ↔ vault and tickets |
| [work/](work/README.md) | Linear client, webhook receiver, dispatcher, workers, alerts |
| [delegation/](delegation/README.md) | Routes to other models |
| [claude/](claude/README.md), [codex/](codex/README.md), [deepseek/](deepseek/README.md), [kimi/](kimi/README.md) | Each runtime's agents, hooks and config |
| [memory/](memory/README.md) | Notes and the team vault |
| [skills/](skills/README.md), [reference/](reference/README.md), [decisions/](decisions/README.md) | Methods, how-tos, and why each rule exists |

## Using it

Take whichever piece you want; each folder's README says what it needs, and the `.example` files show the values
to fill in. Cloning installs nothing. Linear, Obsidian, the model clients and the assistant are separate
services. Names are placeholders: "the operator" is the owner, and the machines are `laptop` and `vps`.

```sh
python3 scripts/check_setup.py     # structure and links
python3 scripts/test_adapters.py   # offline tests
```

## License

[MIT](LICENSE)
