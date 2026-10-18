# Reserve taps for four action classes

Decided: 2026-10-13

Rule: Require a fresh owner tap before paid spend, messages or shares sent as the operator,
      secrets or privacy disclosures, and tier-three destruction.

Reason: Until this ruling every ask-first action waited for an approval record even when the
        operator had requested it, which stalled routine deploys and restarts for hours. The
        operator's own request now settles everything except these four, because each crosses a
        financial, identity, privacy, or irreversible-loss boundary that a relayed or quoted
        request cannot be trusted to settle: ticket text can come from an assistant that reads
        mail and the web.

Reopen when: An alternate authorization proves the same identity, scope, and one-action
             consent at each boundary.

Effect: Routine authorized work proceeds without a second tap.
