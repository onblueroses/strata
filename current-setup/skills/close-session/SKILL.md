---
name: close-session
description: Reconcile completed work, evidence, follow-ups, and restart context when closing a session.
---

# Close Session

## Outcome contract

- Goal: make the completed work, remaining work, evidence, and restart point agree across durable records.
- Success: repository state and any active specification or issue record are truthful; material follow-ups have owners; unfinished work can resume.
- Does not count: closing work before its success conditions pass, leaving a material deferral untracked, or writing to an unavailable external service by guesswork.
- Stop: the relevant records are reconciled, or the exact blocked write and its local fallback are reported.

## Workflow

1. Resolve the project root. Read applicable instructions, the active specification, current status, relevant diff, and available work-ledger context.
2. Run the narrow verification required by the task. Reuse completed checks and record their evidence.
3. Update an active specification only when its success conditions pass. Record evidence or a blocker when work remains open.
4. Update an issue or work ledger only when the adapter and authorization are available. Preserve truthful status and signed ownership. Route material follow-ups to an owner.
5. Record durable repository knowledge only when a future agent cannot cheaply rediscover it. Keep secrets, personal identifiers, and host-specific paths out of shared files.
6. Re-read status, commit the session’s verified changes as required by the shared instructions, and report untracked or unverified work. Preserve unrelated changes.

## Authority boundary

Use external memory and work ledgers only through adapters supplied by the target installation. A delegated worker returns memory candidates to its primary instead of settling shared memory. Do not invent commands or endpoints. If an adapter is absent, provide the same reconciliation in the session response and leave a local restart note when unfinished context warrants one.

## Return

Lead with completed versus still open. Name verification evidence, durable-record updates, working-tree state, and the exact next action.
