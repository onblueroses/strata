# Ask before paid CPU or GPU allocation

Decided: 2026-10-13

Rule: Obtain the operator’s tap before starting paid CPU or GPU capacity, then run refusal
      checks before long jobs and close paid capacity after completion.

Reason: Compute launch can create external charges even when the task itself is authorized.
        Long jobs also need a durable completion and teardown path.

Reopen when: A bounded allocation mechanism proves no new external charge can occur without
             prior owner authorization.

Effect: A running paid instance has an explicit lifecycle and teardown owner.
