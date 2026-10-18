# One work system

The issue tracker is the ledger. A steering agent files, labels, pins and comments, but never claims. The dispatcher is the only claimer. The webhook receiver appends verified issue, comment and label events to a durable log; the dispatcher tails it and reconciles with Linear on a five-minute poll. Ticket conventions are in [followup-convention.md](../reference/followup-convention.md).

```text
operator / messaging assistant / agents ──file or reply──▶ Linear
                                                      │ webhook
                                                      ▼
                                              linear-hook ──▶ events.jsonl
                                                   │                │
                                                   ▼                ▼
                                            steering agent      dispatcher
                                            labels and pins       claims
                                                                      │ forced-command SSH
                                                    ┌─────────────────┴─────────────────┐
                                                    ▼                                   ▼
                                              worker on vps                       worker on laptop
                                                    └──── signed milestones and outcome ─┘
                                                                      │
                                    phone ── approve-gate ── record ──┘
                                             op-wrapper: bounded service restarts
                                             alarms/watchdog: ntfy to operator
```

A ticket with exactly one `for:codex` or `for:claude` label in Backlog or Todo is eligible. `laptop` and `vps` are explicit pins; routing is never inferred from prose. The dispatcher claims, posts `Starting run-xxxxxx`, and sends the ticket packet and brief over SSH. The target key has a forced `worker-run` command, so it cannot issue arbitrary commands over that key. The worker signs every milestone and ends with one signed outcome, such as `(worker-vps run-xxxxxx, YYYY-MM-DD)`. Completion means that run's own authenticated signed outcome comment, not process exit or a status change. Missing outcome hands the ticket back; a second hand-back routes it to the operator. A later unsigned reply within 14 days starts a follow-up. See [dispatcher](dispatcher/README.md).

An `APPROVAL NEEDED:` line ends a worker's ask. The phone page accepts only an identified phone on the tailnet and writes a durable record. The dispatcher replays a record once as `APPROVAL RECORD` only when the ticket, source comment and exact action still match; changed or closed asks revoke it. Linear text is not a phone approval, because comments and tickets can include relayed or quoted material. See [approve-gate](approve-gate/README.md).

The operator's own request, including one relayed by the messaging assistant as the operator, is the go-ahead for deploys, DNS, configuration, service restarts and root work (ruling of 2026-10-13). Four actions still require a phone tap even when requested: spending money; sending messages or shares as the operator; disclosing secrets or private information; and tier-3 destruction. Destruction has three tiers: (1) undoable work or artifacts we made need no tap; (2) a specific thing the operator names in their own words can be deleted without a tap, after quoting that request on the ticket; (3) production data, backups, whole servers or accounts, shared-history force pushes, anything without a backup path, and anything unasked always need a tap. The VPS worker has unrestricted root by the ruling of 2026-10-10; the approval record and request boundary govern that power, not the OS user. The bounded [op-wrapper](op-wrapper/README.md) remains a convenient allowlisted restart path.

The single claimer rule came from two keepers racing and claiming the same work. The dispatcher guards an interrupted claim and a tracker 401 between claim and launch by rereading or sweeping it back. A sleeping laptop waits without consuming an attempt or phone approval. Do not run `brain-linear` under the dispatcher account while its service is active: every CLI invocation mints then revokes that app token, and a concurrent call can turn the service's Linear requests into 401s. Read with a different identity. The [webhook](linear-hook/README.md), [Linear CLI](linear/README.md), and [alarms](alarms/README.md) document their interfaces.
