# Keep every secret in one secret store

Decided: 2026-11-04

Rule: Every secret lives in one hosted secret store. Never write or edit a key in a file by hand: every
      secret file on the laptop and the server is generated from the store. A new key goes into the
      store first; a tool that needs it runs under the store's runner or gets a generated file. Each
      credential has one canonical value; every copy is a reference to it.

Reason: With one canonical value and generated files, a rotation is one change that the machines then
        follow, and no hand-edited copy can drift from it.

Reopen when: The store becomes unavailable for a period the machines cannot cover from their local
             cache, or a measured incident shows that the generated files diverge from the store.

Effect: Machines pull generated files and report drift; rotation changes only the canonical key.
