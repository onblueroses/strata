# Treat the owner request as authorization

Decided: 2026-10-13

Rule: An explicit operator request, including one filed through the authorized messaging
      assistant, is go-ahead for ordinary implementation and operations, including deploys and
      service restarts.

Reason: A second approval step after an explicit request consumed attention without adding an
        authority signal. Ticket text can also contain quoted external content, so the request
        must be distinguished from that content.

Reopen when: The request channel can be shown to misattribute external text as operator
             intent, or a specific operation requires a stronger authority proof.

Effect: The tap-only gates remain separate.
