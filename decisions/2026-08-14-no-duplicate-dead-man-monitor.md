# Keep the proven failure alarm path

Decided: 2026-08-14

Rule: Do not add a second dashboard push monitor merely to duplicate a working failure
      notification chain.

Reason: A live failure probe reached the phone through the existing service-failure alarm. A
        co-location residual had already been accepted, so the proposed monitor supplied no
        distinct evidence.

Reopen when: A failure the existing chain cannot surface is demonstrated, and the new monitor
             catches it without duplicating that chain.

Effect: Alerting remains on one verified path.
