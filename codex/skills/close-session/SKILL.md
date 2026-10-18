---
name: close-session
description: Reconcile a Codex run into a restartable close across repository state, active spec, Linear, repo AGENTS.md, and OptMem. Use when the user says wrap up, end session, close this out, leave a handoff, record what matters, or asks to finish a work session cleanly.
---

# Close Session

Close the work actually done under the authority of the current role. Apply only the relevant steps: ordinary conversation needs no ledger update or handoff, and small completed tasks need no restart brief.

## Outcome contract

- Goal: make the completed work, remaining work, evidence, and restart point agree across their durable ledgers.
- Success: repository, spec, and issue state is reconciled; meaningful non-mechanical knowledge is routed correctly; the user receives a self-contained outcome and restart point.
- Does not count: an issue closed before success, a mechanical repo AGENTS.md breadcrumb, a material deferral left untracked, or a delegated agent settling OptMem.
- Stop: issues actually worked have truthful outcomes, material follow-ups have owners, and unfinished work has enough context to resume.

## Workflow

1. Resolve the project root. Read applicable `AGENTS.md`, the active spec, `git status`, the relevant diff, and the current Linear issue and comments.
2. Run the narrow verification required by the task, reusing checks already completed. Shared `CLAUDE.md` governs independent review. Keep collectors scoped to this project and explicit paths.
3. If there is an active spec, update it truthfully: close the current Frontier only when its success conditions pass; otherwise record evidence or blocker. Save a brief when unfinished work has context worth carrying forward.
4. Comment the result on issues actually worked, signed `(codex, YYYY-MM-DD)`. Move an issue to Done only when its objective is achieved. Track material deferrals and unresolved decisions under `$HOME/.claude/reference/followup-convention.md`; passing ideas and quick questions need no ticket.
5. Read repo AGENTS.md constraints, warnings, and notes for changed files. Add a signed decision, warning, constraint, context, or observation only when it carries knowledge a future agent cannot cheaply rediscover.
6. For each durable memory candidate, read `$HOME/.claude/reference/knowledge-management.md` and apply the current role boundary:
   - A user-facing primary Codex session judges the candidate, appends each accepted note with `python3 $HOME/Work/optmem/memo note "$note"`, and verifies it by an exact identity recall with complete coverage. Run `memo nap` only when OptMem reports a specific pending block and the summary has been judged under that contract.
   - Delegated Codex agents never settle OptMem. Return canonical candidates inline to the primary; use `$HOME/.local/bin/optmem-proposals append codex/subagent "$note"` only when a detached dispatch contract explicitly requires the inbox. Repeat detached candidates under `PROPOSED-NOTES:`.
   Keep each line in the required `TYPE ENTITY SCOPE KEY PAYLOAD` grammar and measured UTF-8 byte bound. If none qualifies, omit the memory section.
7. Re-read `git status`. Preserve unrelated changes and report what remains uncommitted, untracked, or unverified.

## Authority boundary

- User-facing primary Codex has the same canonical OptMem authority as user-facing primary Claude. Delegated agents have proposal-only authority.
- Commit this session's verified work under the standing user authorization, preserving unrelated changes. Push only within a destination and scope already authorized by the user; publication remains ask-first.
- Avoid automatic cleanup or deletion; follow the repository's recoverable archive convention when deletion is explicitly in scope.
- Keep incomplete work open and leave its strongest next route.

## Return

Lead with completed versus still open. Name verification evidence, ledger updates, working-tree state, and the exact next action. Include `PROPOSED-NOTES:` only when candidates were appended or an append failed.
