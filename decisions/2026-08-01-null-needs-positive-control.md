# A null result needs a positive control

Decided: 2026-08

Rule: Do not treat a null observation as a closed direction until a positive control fires in
      the same rig. Report the detection limit and strongest remaining route.

Reason: Without a working positive control, absence of signal can mean the instrument or test
        path failed. A session-level null cannot by itself retire a research direction.

Reopen when: A validated control establishes sensitivity in the same setup and the null then
             excludes the stated effect at a declared limit.

Effect: Retiring a direction remains the operator’s decision.
