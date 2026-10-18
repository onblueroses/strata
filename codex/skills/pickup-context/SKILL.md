---
name: pickup-context
description: Orient a Codex run from the operator's current OptMem, Linear queue, repo AGENTS.md constraints, active repository spec, decision corpus, and working tree. Use when the user says pick up, resume, orient, catch up, what should I work on, or asks Codex to continue prior project work without re-deriving settled context.
---

# Pickup Context

Build a compact, evidence-backed starting picture. Keep OptMem read-only and leave all external state unchanged.

## Outcome contract

- Goal: identify the live task, binding constraints, present repository state, and safest next action.
- Success: every claim points to its source; truncated memory is narrowed before use; unknowns stay unknown.
- Does not count: a generic summary, stale issue title, guessed session state, or any write to OptMem, Linear, repo AGENTS.md, or git.
- Stop: return one orientation brief once the sources agree, or name the exact contradiction or blocker.

## Workflow

1. Resolve the working directory and repository root. Read every applicable `AGENTS.md`; then inspect `git status`, branch, and active `.codex/specs/*.md` files from that repository.
2. Run the read-only memory entry point:

   ```bash
   python3 $HOME/Work/optmem/memo wake
   ```

   When one claim matters, use case-insensitive regex recall with an anchored type/entity/scope/key pattern. Read the final status line and narrow a truncated result before relying on it.
3. Read the live ledger with `brain-linear pickup codex`. Treat issue status and signed comments as current work evidence, not as a replacement for repository facts. The unattended Sol workers take unclaimed `for:codex` issues within minutes; an issue signed `worker-vps` or `worker-laptop` is theirs until its outcome comment.
4. In a git repository, read the repo AGENTS.md before proposing edits. Inspect the instructions that govern each file likely to change.
5. Search `~/lore/decisions/` before recommending or reopening an architectural direction. Apply a sealed reopening bar as a constraint.
6. Reconcile disagreements in this order: current files and executable state; active spec decisions; current Linear status/comments; repo AGENTS.md constraints; OptMem orientation. Surface any unresolved contradiction.

## Return

Return a brief with:

- live objective and its evidence;
- active issue/spec and working-tree state;
- binding warnings, decisions, and unknowns;
- the next concrete action.

Do not run `memo note` or `memo nap`, drain proposals, change issue state, write notes, edit files, commit, or push during pickup.
