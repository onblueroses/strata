---
name: cold-email
description: "Draft or review cold outreach with one house template: a short, honest note from a sender whose identity and frame the operator supplies, one sourced detail about the recipient, one fork question only they can answer, and a 15-minute call or written-reply option. Trigger on cold email or contact-a-stranger work. Outreach-atlas owns people data; this skill owns the mail."
---

# Cold Email

Use one template. The operator supplies the sender's truthful identity, frame, and sending address before drafting. Fill the bracketed fields per recipient; keep the surrounding prose stable. A sending implementation may parse this fence as its format string, so change it only together with that implementation and its build check.

## The template

```text
Subject: [SUBJECT: their specific thing, 40 to 60 characters, a label rather than a question]

Hi [FIRST: the recipient's first name, titles dropped],

[FRAME: the operator-supplied, truthful sender identity and purpose, put plainly in the recipient's world.]

[ANCHOR: one named thing this recipient did, and what it means. Its own paragraph.]

I am exploring [SIM_SCOPE: the other side of their exact situation, with two or three concrete unknowns] before [EVENT: the real decision moment]. [FORK: would that have helped in their case, or does their direct experience reveal something the proposed method would miss?] Your answer would shape the work.

Could I ask for 15 minutes on a call? A written answer works too.

Thank you,
[SENDER: the name on the From address]
```

Six recipient-specific slots are subject, plainly phrased frame, anchor, sim_scope, event, and fork. The operator supplies the frame's factual basis; the drafter adapts its wording. `FIRST` and `SENDER` come from the recipient row and sending identity. The email must never claim an identity, affiliation, qualification, or project the sender did not supply and verify.

## Worked structural example

```text
Subject: Your decision on the shared test protocol

Hi [first name],

[Truthful sender identity and purpose, supplied by the operator, expressed in this recipient's terms.]

Your published note on [specific decision] explains why [specific constraint] changed the protocol.

I am exploring how the other side would evaluate that choice (which requirement controls, what evidence changes the answer, and when the choice becomes binding) before the next review. Would seeing those responses have helped, or did working through the review reveal something a rehearsal would miss? Your answer would shape the work.

Could I ask for 15 minutes on a call? A written answer works too.

Thank you,
[sender name]
```

## Rules and reasons

- **Truthful frame** (the ruling of 2026-09-08): a real sending identity must corroborate the body. The earlier mismatch between claimed identity and address made a short note look forged. Use a sender frame the operator actually supplies; a campaign persona cannot substitute for it. Keep internal plans out of the copy.
- **One fork** (the ruling of 2026-09-08): one branch should credit the recipient's experience as potentially better than the proposed method. Write a fresh fork and subject for each person, even when several share an organization or subject.
- The anchor names a specific hearing, filing, decision, release, or similar act and is supported by a fetched source page. A title alone is not an anchor. Never invent one.
- No em dashes. Use commas, colons, or periods.
- The subject is a 40 to 60 character label with no question mark or trailing tag. Vary the moment or object across a batch; never pad it.
- The signature matches the From address. Set `SENDER_NAME` per run when multiple sending identities exist.
- Offer a call first and a written reply as the easy alternative. Plain text, no attachments, tracking, or sign-off block beyond the name.
- One follow-up at most, 7 to 10 days later, in the same thread, only with one genuinely new fact.
- The sender's jurisdiction governs any required disclosure or opt-out wording; verify it before sending. Every batch still needs the operator's approval under the outreach workflow.
