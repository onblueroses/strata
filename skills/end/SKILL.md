---
name: end
description: |
  Close a work session into a restartable handoff: reconcile relevant repository and
  task ledger state, preserve durable knowledge under the current role's authority, and
  leave user changes intact. Auto-trigger when the user ends or wraps up a session.
---

# End Session

Goal: leave completed work, remaining work, and their durable records in agreement.
Apply only the parts relevant to this session. Ordinary conversation needs no ledger update or handoff; save a brief when unfinished work has context worth carrying forward.

Success means:

- relevant issues have truthful signed outcomes; finished work is moved to Done only after its outcome is recorded;
- a future session can identify the working-tree state, verification evidence, and strongest next action;
- durable knowledge is judged, recorded by its authorized writer, and remains findable;
- pre-existing or another session's changes remain untouched.

Does not count: a generic recap; closing an issue before its outcome is recorded; treating a transient outcome as durable fact; writing frozen daily-note data; or a delegated agent settling operator-supplied memory.

Stop when the handoff states what is complete and open, every in-scope ledger update has either succeeded or has a named blocker, and `git status` has been read again.

## Close the loop

1. Read the applicable `AGENTS.md`, active spec or task brief, relevant task ledger issues and comments, the current diff, and `git status`. Identify the work this session actually owns; do not claim unrelated dirty files.
2. Run the smallest verification that supports the outcome. Shared `CLAUDE.md` governs independent review; project instructions govern additional checks. Keep evidence with the result, including unrun checks and their reason.
3. Commit this session's own verified work under the standing authorization. Preserve existing user changes. Push only to a destination and scope already authorized in the active conversation; publication remains ask-first.
4. For tracked work, reconcile the live ledger using `<operator-config>/followup-convention.md`: post a signed outcome on each materially worked issue before moving completed work to Done; file material follow-ups needing ownership or later action; leave failed writes visible and the issue open.
5. Read `<operator-config>/knowledge-management.md` before handling proposals or durable memory. Apply its current grammar, duplicate checks, proposal dispositions, and verification rules. Record only material outcomes, current state, durable propositions, or find-again documents; never mutate the frozen daily-note layer.
6. Authority is role-specific: a user-facing primary judges and writes accepted operator-supplied memory records; a delegated agent returns canonical candidates to its primary and never settles operator-supplied memory. Honor a field-dispatch result contract when one exists, without inventing one for ordinary work.
7. Re-read `git status`. Report completed and open work, verification, commits/pushes (or why absent), ledger/memory outcomes, remaining working-tree state, and the exact restart action.

When a check, ledger write, memory judgment, or push is blocked, keep the artifact and report the evidence rather than declaring a clean close.
