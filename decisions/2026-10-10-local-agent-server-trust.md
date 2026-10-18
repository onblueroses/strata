# Trust operator agents on the server and fence third parties

Decided: 2026-10-10

Rule: The operator’s own agents may use local server resources needed for their work. Fence
      third-party agents from unrelated local services and private network paths.

Reason: A security sweep treated local readability by operator-controlled accounts as exposure
        without an outside path. The relevant boundary was third-party or internet reach into
        unrelated services.

Reopen when: A concrete outside path through an operator-controlled agent is demonstrated, or
             the trust model changes.

Effect: Internet-facing services still need their own access controls.
