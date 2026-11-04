# Strata

A setup where AI agents run as one connected system, with **Linear at the center**. Every task, question,
handoff and result is a Linear ticket. You message the personal assistant from your phone, and a ticket appears. Unii routes
it. A dispatcher wakes an agent on your laptop or server, and the agent does the work, hands parts to other
models if needed, and posts the result back on the ticket. Claude Code, Codex, DeepSeek and Kimi share one set
of instructions and one memory, so any of them can pick up where another stopped.

Everything here comes from a setup in daily use. Snapshot of 2026-10-17.

## How it connects

```text
   you (phone)                 you (terminal)              Claude · Codex · DeepSeek · Kimi
       │                             │                                  │
       ▼                             │                                  │
  Assistant ──files tickets──┐       │                                  │
                             ▼       ▼                                  ▼
                 ┌─────────────────────────────────────────────────────────────┐
                 │                         LINEAR                              │
                 │   tickets · labels (who) · pins (where) · comments (talk)   │
                 └─────────────────────────────────────────────────────────────┘
                             │ webhook, within seconds              ▲
                             ▼                                      │
                    Unii ◀── event log ──▶ dispatcher               │
               (routes, labels,               │ SSH                 │
                answers, chat)                ├──▶ worker on the laptop (Codex, or Claude with your browser)
                                              └──▶ worker on the server (Codex)
                                                          │
                                                          └── progress + signed result ──┘
```

## Linear is the backbone

Nothing talks to anything else directly. Everything goes through a Linear ticket, which is why the system holds
together:

- **One inbox for everyone.** You, the personal assistant, Unii and every agent file work in the same place. Agents file
  their own follow-ups, open questions and anything they had to defer, so nothing is lost when a session ends.
- **Labels are the routing.** One `for:` label says who takes a ticket: `for:codex`, `for:claude`,
  `for:kimi`, `for:ds`, `for:assistant`, or `for:operator` for you. `laptop` and `vps` say where it runs, and
  `from:assistant` marks what the personal assistant filed. Changing a label reassigns the work. Routing is never guessed from the text.
- **Comments are the conversation.** Agents, the personal assistant, Unii and you all talk in the ticket thread. Every
  agent signs its comments, so you can see who said what.
- **The ticket is the job's state.** The dispatcher claims a ticket and the worker posts milestones. The
  ticket counts as done when a signed result is posted, not when a process exits. If a worker goes quiet the
  ticket comes back to the queue; after a second failure it comes to you. If you reply later, a new run picks
  it up.
- **Instant reaction.** A webhook pushes every ticket, comment and label change to the server within seconds
  and appends it to a durable event log ([linear-hook](work/linear-hook/README.md)). A five-minute poll
  catches anything the webhook missed.
- **Each agent has its own identity.** Unii, the dispatcher and the workers act as their own Linear apps.
  They can be assigned and mentioned like teammates.
- **Approvals happen on the ticket too.** A worker that needs a yes ends its comment with
  `APPROVAL NEEDED:`. You tap once on your phone, and the dispatcher continues
  ([approve-gate](work/approve-gate/README.md)).

The Linear client every agent uses is [brain-linear](work/linear/README.md): `brain-linear pickup codex` lists
that runtime's open work. All of the machinery is in [work/](work/README.md).

## The pieces

**The personal assistant → your laptop.** The personal assistant is a personal AI assistant you talk to by chat. It has no API. Through the
[bridge](assistant-bridge/README.md) it reads a published copy of the team vault, suggests vault edits as pull
requests, and files Linear tickets for you. Tickets addressed to the personal assistant show up for it as GitHub issues, and
Codex answers its questions there. One of its tickets can say "do X on my laptop": the dispatcher picks it up,
and a worker on the laptop does it, browser included. A message from your phone ends up driving your own
machine.

**Unii.** The steering agent. It reads every Linear event as it happens, files and labels tickets, and answers in
comments or in its own chat. It never claims work; that is the dispatcher's job.

**Dispatcher and workers.** The [dispatcher](work/dispatcher/) is the only thing that claims tickets. For each
one it starts a fresh worker over SSH, on a key that can only launch that worker. Alerts reach your phone through ntfy
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
mechanical worker, an adversarial reviewer and researchers. Live Claude and Codex sessions on one machine can
also message each other directly ([agent communication](reference/agent-communication.md)).

**One instruction file.** [AGENTS.md](AGENTS.md) is read by all four runtimes; each adds a few lines of its
own ([claude/](claude/README.md), [codex/](codex/README.md), [deepseek/](deepseek/README.md),
[kimi/](kimi/README.md)).

**Shared memory.** Agents write one-line notes ([OptMem](memory/optmem/README.md)). At each session start a hook
shows the notes that matter, so a new session, or a different model, carries on from the last one. Team
knowledge lives in an Obsidian [vault](memory/brain/README.md) that agents, the personal assistant and people all read and
write.

## Repo layout

| Folder | Contents |
|---|---|
| [work/](work/README.md) | Linear client, webhook receiver, dispatcher, workers, phone approvals, alerts |
| [assistant-bridge/](assistant-bridge/README.md) | the personal assistant ↔ vault, tickets and GitHub |
| [delegation/](delegation/README.md) | Routes to other models |
| [AGENTS.md](AGENTS.md) | Shared instructions |
| [claude/](claude/README.md), [codex/](codex/README.md), [deepseek/](deepseek/README.md), [kimi/](kimi/README.md) | Each runtime's agents, hooks and config |
| [memory/](memory/README.md) | Notes and the team vault |
| [skills/](skills/README.md), [reference/](reference/README.md), [decisions/](decisions/README.md) | Methods, how-tos, and why each rule exists |

## Using it

Take whichever piece you want; each folder's README says what it needs, and the `.example` files show the values
to fill in. Cloning installs nothing. Linear, Obsidian, the model clients and the personal assistant are separate services.
Inside the folders, the personal assistant is called "the assistant" and Unii "the steering agent". "The operator" is the
owner, and the machines are `laptop` and `vps`.

```sh
python3 scripts/check_setup.py     # structure and links
python3 scripts/test_adapters.py   # offline tests
```

## License

[MIT](LICENSE)
