# Stewards

A steward is a persistent owner agent: one long-lived Connectome resident on the server, with its own account,
its own model login, standing instructions and a memory, that owns exactly one thing and acts on it without being
asked. Three run in production. This folder describes them at the level of their roles; their code, recipes and
standing instructions are not part of this tree.

| Steward | Owns | Reached by | Signs |
|---|---|---|---|
| [Linear Steward](#linear-steward) (2026-11-10) | the record: every work and decision ticket, and what is dispatched | Linear events; hcom `linear-steward` | `(linear-steward, date)` |
| [Privacy Steward](#privacy-steward) (2026-11-11) | the public boundary | everything bound for a public destination | signed verdicts |
| [Infrastructure Steward](#infrastructure-steward) (2026-11-12) | the health of the machines: alarms, failed units, disks, backups, updates | alarms on the server; label `for:infrastructure`; hcom `infrastructure-steward` | `(infrastructure-steward, date)` |

One owner per domain is a sealed decision ([record](../decisions/2026-11-12-one-owner-per-steward-domain.md)).
A steward that sees something outside its post files one ticket or sends one message to the owner and stops.
How the stewards fit into the rest of the setup: [work/](../work/README.md) and
[reference/agent-communication.md](../reference/agent-communication.md) (hcom, Connectome).

```text
                   Linear events              alarms               public publishing
                        │                       │                         │
                        ▼                       ▼                         ▼
                ┌───────────────┐      ┌────────────────┐       ┌─────────────────┐
                │ Linear Steward│      │ Infrastructure │       │ Privacy Steward │
                │               │      │    Steward     │       │                 │
                └──┬─────────┬──┘      └───────┬────────┘       └────────┬────────┘
         orders ◀──┘         └──▶ phone page ◀─┘                         │ signed verdict
      (dispatcher)            (questions, answers)                       ▼
                                                              laptop publishes or refuses
```

## What every steward has

- **A post.** Three sentences ruled by the operator: what it owns, what it does not own and who does, what it
  does with something that is not its own.
- **Its own identity.** One account, one model login, one signature, one hcom name.
- **Standing instructions** read on every turn: who it is, its post, how events reach it, how it judges, what
  binds it.
- **A memory** that keeps the whole record and folds older conversation into summaries.
- **Tool servers** that push events to wake it and keep them until it has handled them.
- **Phone questions.** It asks the operator a ready decision with options on a small phone page and wakes on the
  answer. The four tap-only actions (money, messages as the operator, secrets, irreversible destruction) never
  go through a steward's question.
- **Watching from outside.** Liveness, telemetry and a backup of its state, none of which go through the
  steward itself.

## Linear Steward

Owns the truth of the record in Linear: triage, labels, routes, pins, relations, outcome projects, each ticket's
current state, and which tickets the dispatcher starts. Every write it makes is recorded and can be undone where
Linear allows it. It orders the dispatcher; it never claims a ticket itself.

## Privacy Steward

Owns the public boundary. Everything bound for a public destination (pushes, GitHub text) passes an independent
reviewer first. The reviewer runs on the server, signs its verdicts, and the laptop refuses to publish without a
valid signature. What it checks and how is private by design.

## Infrastructure Steward

Owns the health of the machines: every alarm gets a cause and an end. It repairs what it can undo and asks the
operator on its phone page before a reboot or a planned stop. Today every alarm still reaches the operator's
phone, and the steward works beside it.

## Build another one

Read [docs/BUILDING-A-STEWARD.md](docs/BUILDING-A-STEWARD.md).
