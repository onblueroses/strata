# Retire brittle deletion command guards

Decided: 2026-09-01

Rule: Do not restore the old deletion command guards. Keep the deletion handling convention
      and the independent privacy guards.

Reason: The command guards were easy to bypass, and one guard had previously failed open under
        the hook protocol. Their presence overstated protection.

Reopen when: A replacement catches realistic bypasses on the host entry path and demonstrates
             a meaningful safety gain without false confidence.

Effect: Deletion handling relies on an explicit workflow, while privacy scanning remains
        active.
