# How Strata works

This page holds the longer explanation behind the [README](README.md). Snapshot of 2026-11-12.

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

A steward is a persistent owner agent. It is one long-lived resident on the server, with its own account,
login, standing instructions and memory. It owns exactly one thing and acts on it without a request. Their
design, and how to build another one, is in [stewards/](stewards/README.md).

| Steward | Owns | What it does |
|---|---|---|
| **Linear Steward** | the record | Reads every Linear event as it occurs. Triages, labels, routes, links and reconciles tickets. Keeps the current state of each ticket. Decides which tickets the dispatcher starts. Asks you ready decisions with options on a phone page and wakes on your answer. |
| **Privacy Steward** | the public boundary | Everything bound for a public destination (pushes, GitHub text) goes to this independent reviewer first. It runs on the server and signs its verdicts. The laptop refuses to publish without a valid signature. What it checks and how is private by design. |
| **Infrastructure Steward** | the machines | Works on every alarm while the alarm also goes to your phone. Owns failed units, disks, backups and updates. Repairs what it can undo, and asks before a reboot or a planned stop. |

Each domain has one owner. A steward that sees work outside its domain sends the owner one ticket or one
message. It then stops. Each steward has its own liveness checks and telemetry, which watch it from outside.

## Linear is the backbone

Work and decisions go through Linear tickets. The stewards also take alarms, phone answers and peer messages
directly, but what they do about them goes on a ticket:

- **One inbox for everyone.** You, the assistant, the stewards and every agent file work in the same place.
  Every start of work gets an In Progress ticket first, and every ticket sits in the outcome project it serves.
- **Labels are the routing.** One `for:` label says who takes a ticket (`for:codex`, `for:claude`, `for:ds`,
  `for:kimi`, `for:assistant`, `for:operator`). `for:infrastructure` may stand beside it. `laptop` and `vps`
  pin where it runs. The system never guesses the route from the text.
- **Comments are the conversation.** Every agent signs its comments. The Linear Steward reads every comment and
  answers there.
- **The ticket is the job's state.** The dispatcher claims the ticket. The worker posts milestones. The ticket
  is complete when the worker posts a signed result, not when a process exits. A quiet worker returns the
  ticket. Repeated failures bring the ticket to you.
- **Instant reaction.** Every ticket, comment and label change goes into a durable event log
  ([linear-hook](work/linear-hook/README.md)).
- **Approvals happen on the ticket too.** Four things always need your tap: spending money, messages sent as
  you, secrets or privacy disclosures, and destruction that cannot be undone ([approve-gate](work/approve-gate/README.md)).
- **Plain words.** Agents write ticket text in Simplified Technical English, so that other agents read it the same way.

The Linear client every agent uses is [brain-linear](work/linear/README.md). All of the machinery is in [work/](work/README.md).

## The pieces

**Assistant to your laptop.** A personal AI assistant that you talk to by chat, with no API. Through the
[bridge](assistant-bridge/README.md) it reads a published copy of the team vault, suggests vault edits as pull
requests and files Linear tickets for you. The work system routes them.

**The chat agent.** Keeps your chat with the system and files or changes a ticket on your word. It no longer
routes. Routing is the job of the Linear Steward.

**Dispatcher and workers.** The [dispatcher](work/dispatcher/README.md) is the only thing that claims tickets,
and it starts what the Linear Steward orders. For each ticket it starts a fresh worker, on a key that can only
start a worker. Alerts go to your phone through ntfy ([work/alarms/](work/alarms/README.md)).

**Delegation.** Any main session can give work to another model ([delegation/](delegation/README.md)):

| Route | Model | Use |
|---|---|---|
| `opencode-fast` | DeepSeek Flash via OpenCode Go | First route for bulk and groundwork |
| `codex-fast` | Codex, cheap tier | Mechanical work that needs Codex |
| `codex-strong` | Codex, strong tier | Hard work and reviews that try to break things |
| `ds-pro`, `ds-flash`, `dsh-agent` | DeepSeek | The view of another provider |
| Free models | A free model, in a sandbox with no view of the machine | Web research on public inputs only. `quote-check` checks every quote. |
| Claude [orchestrator](claude/agents/orchestrator.md) | Claude | Plans, sends work to the routes above, checks and combines |

**Rules with sources.** All four runtimes read [AGENTS.md](AGENTS.md). Among its rules:

- No limit (cap, timeout, budget, threshold) goes into a config or prompt without its source beside it.
- Heavy work runs on the server. The laptop runs only quick checks.
- Every secret lives in one secret store. The system generates secret files from that store.

Each ruling has its date and reason in [decisions/](decisions/README.md).

**Shared memory, kept forever.** Agents write one-line notes ([OptMem](memory/optmem/README.md)) that a hook
shows at each session start. Team knowledge lives in an Obsidian [vault](memory/brain/README.md). The system keeps
every message between agents, makes backup copies and never prunes them ([memory/](memory/README.md)). Live sessions on one machine
talk through hcom ([agent communication](reference/agent-communication.md)).

## Not in this copy

The live setup has more parts than this copy. Some are here as a design only. This page names the others but
omits them. A public copy would help attackers more than builders, or would not remain accurate:

- **Guards.** Hooks that check a command before it runs and refuse the dangerous ones. Each runtime has them.
- **Server operations.** Machine configuration, deployment, monitoring and backups. On the live setup the
  Infrastructure Steward owns this work.
- **Rented compute.** Notes on renting GPU machines and hosted inference. Vendors and prices change too fast
  for a copy to stay correct.
- **Outreach.** Methods that find the right people for a research question and write a first note to them.
- **Session launch.** A small helper that starts each operator session already joined to hcom.
- **Free-model sandbox.** The isolation around free models. The design is in
  [delegation/wrappers/](delegation/wrappers/README.md).
