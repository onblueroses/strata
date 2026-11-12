# Open an In Progress ticket when work starts

Decided: 2026-11-11

Rule: When an agent starts work that has no ticket, it creates one in the work team in state In
      Progress before the first change. When a ticket exists, the agent claims it and moves it to In
      Progress. The agent keeps the ticket current with signed comments at start, at material changes
      and at stop.

Reason: Work done without a ticket leaves no trace that the record's owner can reconcile, and the
        operator cannot see what is running. The Linear Steward reconciles only what the record
        holds, so the record has to hold the work from its first change.

Reopen when: A cheaper record captures the same start, owner and outcome for every piece of work.

Effect: Every session that changes something has a ticket that says who works on it, what is done and
        where the result lives.
