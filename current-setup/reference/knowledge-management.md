# Knowledge Management

Use three separate layers:

| Layer | Purpose |
| --- | --- |
| Task ledger | Live ownership, decisions, questions, and follow-through |
| Append-only memory | Compact facts, current state, events, and document pointers |
| Document vault | Rich notes, research, handoffs, and other durable documents |

The operator supplies the locations and commands for these layers. This snapshot intentionally contains no private service command, account name, absolute path, or credential.

## Append-only memory

Each record is one line in the form:

```text
TYPE ENTITY SCOPE KEY PAYLOAD
```

Use `F` for durable facts, `S` for changeable current state, `E` for events, and `P` for document pointers. Use stable entity, scope, and key tokens. Keep records within the configured byte limit. Append corrections as newer records; do not edit or delete old records.

Read mutable state by recalling the exact entity, scope, and key, then selecting the greatest record id. Treat a truncated recall as incomplete and narrow the query until coverage is complete. Store rich content in a document first, then append a pointer with its absolute operator-supplied path and reason.

## Delegated candidates

Delegates return candidates for primary judgment. A detached dispatch may use the operator-supplied proposal inbox when its brief names that route. The primary validates grammar, byte limits, identity, and exact recall before accepting a candidate. The proposal queue is not live state until the primary settles it.

## Boundaries

Keep task state in the task ledger. Keep repository warnings in the repository's local instructions. Keep rich knowledge in documents. Treat legacy summaries and rendered dates as historical context unless current evidence confirms them.

