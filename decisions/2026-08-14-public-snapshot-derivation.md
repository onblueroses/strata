# Publish a derived snapshot periodically

Decided: 2026-08-14

Rule: Treat the public estate copy as a deliberate periodic derivation, with review of
      abstraction and privacy, rather than a continuous synchronization pipeline.

Reason: Live operating files mix reusable mechanisms with private state. Blind syncing would
        carry private detail and turn each local change into an immediate public change.

Reopen when: A sync design proves equivalent privacy review and faithful abstraction at each
             update without making the public copy a second live authority.

Effect: Public material is revised deliberately.
