# Make a blocking hook verdict irrevocable

Decided: 2026-08-16

Rule: For a blocking hook, enforce the host protocol result before optional telemetry or
      formatting can fail. Test the assembled entry path and exact exit codes.

Reason: A shell nounset error in a shared telemetry helper occurred after a refusal was
        printed but before exit status 2. The host treated status 1 as a nonblocking hook
        error; a test had wrongly classified every nonzero status as blocked.

Reopen when: An alternative proves the real host blocks despite late helper failures,
             concurrent live edits, and unexpected process exits, with both allow and deny
             controls.

Effect: Visible refusal text is never treated as proof that the host refused.
