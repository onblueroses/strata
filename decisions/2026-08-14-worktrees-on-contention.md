# Use worktrees when writers contend

Decided: 2026-08-14

Rule: Use separate worktrees when parallel agents may edit the same repository; do not make a
      worktree mandatory for every session.

Reason: The motivating large-scale contention was not measured in this estate. Default fan-out
        would add branch, merge, cleanup, and scratch coordination even for isolated work.

Reopen when: Measured same-repository contention costs more review time than the branch and
             coordination overhead of default isolation.

Effect: A dispatcher can still select worktree isolation for a concrete collision risk.
