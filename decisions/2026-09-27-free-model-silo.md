# Confine free-model routes to a silo

Decided: 2026-09-27

Rule: Run free model harnesses only inside an isolated filesystem view with explicit public
      inputs and controlled outputs; verify the boundary after harness updates.

Reason: The harnesses automatically attached private instructions and memory, and file-capable
        models could inspect the home directory. Prompt hygiene alone had already failed.

Reopen when: A changed route proves, with canary and positive controls, that it cannot read
             private context while keeping the required task capability.

Effect: Private login material stays outside the free route.
