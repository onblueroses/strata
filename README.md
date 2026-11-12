# Strata

A setup where AI agents run as one connected system, with **Linear at the center** and **stewards** that own it.
Work and its results are recorded on Linear tickets. Your personal assistant files tickets for you. The Linear Steward, a persistent agent on the server, triages it and decides who does it. A
dispatcher wakes a worker on your laptop or server, the worker does the work and posts the result on the ticket.
Two more stewards own the rest: one reviews everything bound for public GitHub, one owns the health of the
machines. Claude Code, Codex, DeepSeek and Kimi share one set of instructions and one memory, so any of them can
pick up where another stopped.

Everything here comes from a setup in daily use, and only what runs in production. Snapshot of 2026-11-12.

## How it connects

```text
   you (phone)            you (terminal)                Claude · Codex · DeepSeek · Kimi
       │                        │                                     │
  assistant ──files tickets──┐  │                                     │
                             ▼  ▼                                     ▼
          ┌────────────────────────────────────────────────────────────────────┐
          │                              LINEAR                                │
          │      tickets · labels (who) · pins (where) · comments (talk)       │
          └────────────────────────────────────────────────────────────────────┘
                 │ change events                                   ▲
                 ▼                                                 │
          event log ──▶ Linear Steward ──orders──▶ dispatcher      │
                        (triage, routes,              │            │
                         links, follow-up,            ├──▶ worker on the laptop (Codex, or Claude with your browser)
                         asks you on a                └──▶ worker on the server (Codex, DeepSeek)
                         phone page)                              │
                                                                  └── milestones + signed result ──┘

   laptop push / gh ──▶ Privacy Steward ──signed verdict──▶ push goes out, or not
   alarms ──▶ your phone, and the Infrastructure Steward beside it ──▶ repairs what it can undo, asks you before a reboot
```

## The stewards

A steward is a persistent owner agent: one long-lived resident on the server with its own account, login,
standing instructions and memory, which owns exactly one thing and acts on it without being asked.
Their design, and how to build another one, is in [stewards/](stewards/README.md).

| Steward | Owns | What it does |
|---|---|---|
| **Linear Steward** | the record | Reads every Linear event as it happens. Triages, labels, routes, links and reconciles tickets, keeps each ticket's current state, and decides which tickets the dispatcher starts. Asks you ready decisions with options on a phone page and wakes on your answer. |
| **Privacy Steward** | the public boundary | Everything bound for a public destination (pushes, GitHub text) passes this independent reviewer first. It runs on the server, signs its verdicts, and the laptop refuses to publish without a valid signature. What it checks and how is private by design. |
| **Infrastructure Steward** | the machines | Works on every alarm while the alarm also reaches your phone. Owns failed units, disks, backups and updates; repairs what it can undo, asks before a reboot or a planned stop. |

One owner per domain: a steward that sees something outside its post files one ticket or sends one message to
the owner, and stops there. Each is watched from outside by liveness and telemetry of its own.

## Linear is the backbone

Work and decisions go through Linear tickets. The stewards also take alarms, phone answers and peer messages
directly, but what they do about them lands on a ticket:

- **One inbox for everyone.** You, the assistant, the stewards and every agent file work in the same place.
  Every start of work gets an In Progress ticket first, and every ticket sits in the outcome project it serves.
- **Labels are the routing.** One `for:` label says who takes a ticket (`for:codex`, `for:claude`, `for:ds`,
  `for:kimi`, `for:assistant`, `for:operator`); `for:infrastructure` may stand beside it. `laptop` and `vps`
  pin where it runs. Routing is never guessed from the text.
- **Comments are the conversation.** Every agent signs its comments. The Linear Steward reads every comment and
  answers there.
- **The ticket is the job's state.** The dispatcher claims, the worker posts milestones, and the ticket is done
  when a signed result is posted, not when a process exits. A quiet worker hands the ticket back; a second
  failure brings it to you.
- **Instant reaction.** Every ticket, comment and label change lands in a durable event log
  ([linear-hook](work/linear-hook/README.md)).
- **Approvals happen on the ticket too.** Four things always need your tap: spending money, messages sent as
  you, secrets or privacy disclosures, and destruction that cannot be undone ([approve-gate](work/approve-gate/README.md)).
- **Plain words.** Ticket text is written in Simplified Technical English, so any agent reads it the same way.

The Linear client every agent uses is [brain-linear](work/linear/README.md). All of the machinery is in [work/](work/README.md).

## The pieces

**Assistant → your laptop.** A personal AI assistant you talk to by chat, with no API. Through the
[bridge](assistant-bridge/README.md) it reads a published copy of the team vault, suggests vault edits as pull
requests and files Linear tickets for you; the work system routes them.

**The chat agent.** Keeps your chat with the system and files or changes a ticket on your word. It no longer
routes; that is the Linear Steward's job.

**Dispatcher and workers.** The [dispatcher](work/dispatcher/README.md) is the only thing that claims tickets,
and it starts what the Linear Steward orders. For each ticket it starts a fresh worker, on a key that can only
start a worker. Alerts reach your phone through ntfy ([work/alarms/](work/alarms/README.md)).

**Delegation.** Any main session can pass work down ([delegation/](delegation/README.md)):

| Route | Model | Use |
|---|---|---|
| `opencode-fast` | DeepSeek Flash via OpenCode Go | First route for bulk and groundwork |
| `codex-fast` | Codex, cheap tier | Mechanical work that needs Codex |
| `codex-strong` | Codex, strong tier | Hard work and reviews that try to break things |
| `ds-pro`, `ds-flash`, `dsh-agent` | DeepSeek | Another provider's view |
| Free models | A free model, in a sandbox with no view of the machine | Web research on public inputs only; every quote is checked by `quote-check` |
| Claude [orchestrator](claude/agents/orchestrator.md) | Claude | Plans, fans out to the routes above, checks and combines |

**Rules with sources.** [AGENTS.md](AGENTS.md) is read by all four runtimes. Among its rules: no limit (cap,
timeout, budget, threshold) goes into a config or prompt without its source beside it; heavy work runs on the
server, the laptop only runs quick checks; every secret lives in one secret store and files are generated from
it. Each ruling has its date and reason in [decisions/](decisions/README.md).

**Shared memory, kept forever.** Agents write one-line notes ([OptMem](memory/optmem/README.md)) that a hook
shows at each session start. Team knowledge lives in an Obsidian [vault](memory/brain/README.md). Every message
between agents is kept, backed up and never pruned ([memory/](memory/README.md)). Live sessions on one machine
talk through hcom ([agent communication](reference/agent-communication.md)).

## Not in this copy

The live setup has more parts than this copy. Some are here as a design only; others are named here and left
out, because a public copy of them would help an attacker more than a builder, or would not stay true:

- **Guards.** Hooks that check a command before it runs and refuse the dangerous ones. Each runtime has them.
- **Server operations.** How the machines are set up, deployed to, watched and backed up. On the live setup
  the Infrastructure Steward owns this work.
- **Rented compute.** Notes on renting GPU machines and hosted inference. Vendors and prices change too fast
  for a copy to stay correct.
- **Outreach.** Methods that find the right people for a research question and write a first note to them.
- **Session launch.** A small helper that starts each operator session already joined to hcom.
- **Free-model sandbox.** The isolation around free models; the design is in
  [delegation/wrappers/](delegation/wrappers/README.md).

## Repo layout

| Folder | Contents |
|---|---|
| [stewards/](stewards/README.md) | The three stewards and how to build one (design) |
| [work/](work/README.md) | The Linear client; the design of the receiver, dispatcher, phone approvals and alerts |
| [assistant-bridge/](assistant-bridge/README.md) | Assistant ↔ vault and tickets (design) |
| [delegation/](delegation/README.md) | Routes to other models |
| [AGENTS.md](AGENTS.md) | Shared instructions |
| [claude/](claude/README.md), [codex/](codex/README.md), [deepseek/](deepseek/README.md), [kimi/](kimi/README.md) | Each runtime's agents, hooks and config |
| [memory/](memory/README.md) | Notes, the team vault, agent message records |
| [skills/](skills/README.md), [reference/](reference/README.md), [decisions/](decisions/README.md) | Methods, how-tos, and why each rule exists |

## Using it

Take whichever piece you want; each folder's README says what it needs, and the `.example` files show the values
to fill in. Cloning installs nothing. Linear, Obsidian, the model clients and the assistant are separate
services. "The operator" is the owner, and the machines are `laptop` and `vps`.

```sh
python3 scripts/check_setup.py     # structure and links
python3 scripts/test_adapters.py   # offline tests of the launch adapters
```

## License

[MIT](LICENSE)
