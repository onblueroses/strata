# Leave Git hooks with each repository

Decided: 2026-08-13

Rule: Do not set one mutable global Git hook path for the estate; each repository owns its
      hook chain.

Reason: A third-party installer replaced the global path and silently bypassed legitimate
        repository hooks. A before-and-after check showed those hooks firing again after the
        global setting was removed.

Reopen when: A global mechanism survives repository installers, preserves every local hook in
             an end-to-end test, and supplies a capability local hooks lack.

Effect: Repository tooling can no longer clobber the shared hook dispatcher.
