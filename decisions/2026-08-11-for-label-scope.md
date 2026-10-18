# Scope the owner label to execution work

Decided: 2026-08-11

Rule: Give each non-decision issue exactly one `for:` owner label. A formal decision issue
      uses its deliberation state; an owner label there is only an attention flag.

Reason: Applying the same label mandate to the decision queue would create a second,
        conflicting pickup path. Execution work still needed a single explicit owner.

Reopen when: The decision queue loses its effective pickup state, or a measured handoff
             failure shows that optional attention flags are insufficient.

Effect: Ownership stays explicit without duplicating decision routing.
