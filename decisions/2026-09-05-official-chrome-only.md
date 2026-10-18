# Use only the official Chrome integration

Decided: 2026-09-05

Rule: All browser interaction goes through the official Chrome integration. If it is
      unavailable, continue work that does not need browser control and report the gap.

Reason: The operator set a single browser-control boundary; the instruction records no
        specific incident. Multiple control routes would make authorization and observed
        browser state inconsistent across sessions.

Reopen when: A replacement has the same operator authorization and browser-state visibility,
             and the operator changes the browser rule.

Effect: Research by search or HTTP retrieval remains separate from browser control.
