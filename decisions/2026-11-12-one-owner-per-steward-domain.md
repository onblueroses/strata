# Give each standing domain one steward

Decided: 2026-11-12

Rule: Each standing domain of the estate has exactly one persistent steward that owns it: the Linear
      Steward the record (from 2026-11-10), the Privacy Steward the GitHub boundary (from 2026-11-11), and
      the Infrastructure Steward the machines (from 2026-11-12). Other agents report into the owner of a
      domain with a ticket or a message and do not make side repairs there. No steward holds one of the
      four tap-only approvals.

Reason: Before the stewards, every session touched the record, the boundary and the machines a little,
        and nobody finished anything there: alarms went to the operator's phone without a cause or an end,
        and tickets drifted. One owner per domain
        gives every fault, ticket and push one place where it is finished.

Reopen when: A domain's owner cannot keep up with its domain in a measured period, or two domains prove
             inseparable in practice.

Effect: Machine faults go to the Infrastructure Steward with the `for:infrastructure` label; tickets are
        filed and left to the Linear Steward; public pushes wait for the Privacy Steward's signature.
