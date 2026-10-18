# Keep one Codex login per OS user

Decided: 2026-09

Rule: Each OS user keeps its own Codex login; never copy one login state into a second runtime
      or isolation silo.

Reason: Two copies of one session invalidated one another during token refresh. Copying
        credentials also enlarged the material available to a lower-trust route.

Reopen when: The authentication mechanism supports independent copies without refresh races
             and the isolation boundary remains intact.

Effect: Separate users authenticate independently and isolated routes use a narrow bridge.
