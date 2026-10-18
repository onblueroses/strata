# Route queued work by labels

Decided: 2026-10-10

Rule: Use one `for:` label to select the worker kind and optional machine labels to pin
      location. Do not infer routing from issue prose or unrelated metadata.

Reason: Text and secondary fields can disagree with the explicit route. A single visible label
        contract lets steering and dispatch observe the same instruction.

Reopen when: An alternate signal remains consistent under edits and concurrent updates and is
             clearer to both steering and dispatch.

Effect: New routes require a label and an explicit dispatcher mapping.
