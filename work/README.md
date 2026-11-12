# One work system

The issue tracker is the ledger. The [Linear Steward](../stewards/README.md) owns the record: it triages, labels,
routes, links and reconciles tickets, and decides what starts; it never claims. The dispatcher is the only
claimer. The chat agent keeps the operator's chat and files or changes a ticket on their word. Ticket conventions
are in [followup-convention.md](../reference/followup-convention.md).

```text
operator / assistant / chat agent / agents ──file or reply──▶ Linear
                                                      │
                                                      ▼
                                              linear-hook ──▶ event log
                                                                  │
                                            Linear Steward ──orders──▶ dispatcher
                                                                          │
                                                    ┌─────────────────────┴───────────┐
                                                    ▼                                 ▼
                                              worker on vps                     worker on laptop
                                                    └──── signed milestones and outcome ┘
                                                                      │
                                         phone ── approve-gate ───────┘
```

A ticket carries one `for:` label that says who takes it; `laptop` and `vps` pin where it runs. Routing is never
inferred from prose. The worker signs every milestone and ends with one signed outcome; the ticket is done when
that outcome is posted, not when a process exits. A ticket without an outcome goes back to the queue, and a second
time to the operator.

Four actions always require the operator's phone tap (ruling of 2026-10-13): spending money; sending messages or
shares as the operator; disclosing secrets or private information; and destruction that cannot be
undone.

The single-claimer rule came from two claimers racing for the same work.

| Part | Role |
|---|---|
| [linear](linear/README.md) | `brain-linear`, the Linear client every agent uses (code in this tree) |
| [linear-hook](linear-hook/README.md) | receives Linear's change notifications and writes them to a durable log |
| [dispatcher](dispatcher/README.md) | the one claimer; starts one fresh worker per ticket |
| [approve-gate](approve-gate/README.md) | the phone page for the four tap-only actions |
| [op-wrapper](op-wrapper/README.md) | a narrow helper for service restarts |
| [alarms](alarms/README.md) | failure alarms and the phone channels |

The code, units, configs and worker instructions of all parts except the Linear client are private.
