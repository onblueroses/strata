# Avoid a runtime-specific vault root

Decided: 2026-08-14

Rule: Put durable runtime specifications in the existing specification hierarchy rather than
      adding a top-level vault directory for one client.

Reason: Several files had accumulated in a local runtime folder; tracking it would create a
        second canonical home and expand the vault layout for no distinct artifact class.

Reopen when: An artifact class cannot fit the existing hierarchy and its vault use justifies a
             new root without duplicating ownership.

Effect: Specifications retain one home.
