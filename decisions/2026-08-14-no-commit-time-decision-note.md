# Write decision notes at semantic boundaries

Decided: 2026-08-14

Rule: Do not require a decision note for every supposedly nontrivial commit. Record verdicts
      when they occur and meaningful work when it closes.

Reason: The source discipline itself rejected a commit gate: mechanical classification of
        triviality invites false positives and shallow compliance notes.

Reopen when: A measured classifier has acceptable false positives, or evidence shows
             semantic-boundary notes are missed where a commit gate would catch them.

Effect: Commit flow is free of notes that carry no decision.
