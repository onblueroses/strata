---
name: cold-email
description: "Write a cold outreach email using the one house template (v2, the master's-student reframe): a short honest note from a master's student whose thesis simulates organisational decision-making, grounded in the recipient's world, anchored on one named specific about them, then ONE fork question only that person can answer, offering a 15-minute call or a written reply. Auto-trigger when drafting, reviewing, or planning any cold or outreach email or contact-a-stranger message. /outreach-atlas owns the people data layer (atlas, waves, ledgers); this skill owns the mail itself."
---

# Cold Email

One template. Fill the [bracketed] parts per recipient; keep everything else. The complete
template is included below, so this skill has no required private campaign file.

## The template

```
Subject: [SUBJECT: their specific thing, written as a question]? (Master's thesis question!)

Hi [FIRST: the recipient's first name, titles dropped],

I'm a master's student; my thesis is on hardware-accelerated simulation of organisational decision-making, put plainly: [PLAINLY: the thesis in their world, one clause].

[ANCHOR: the named specific about them, and what it means. Its own paragraph.]

We simulate [SIM_SCOPE: the counterparty's side of their exact situation, closing with two or three concrete unknowns from their world in parentheses] before [EVENT: the real moment]. [FORK: would that have helped you X, or does doing Y at their scale teach a read no model matches?] The thesis needs the answer.

Could I ask for 15 minutes on a call? I'd rather hear it live, but a written answer works too.

Thank you,
[SENDER: the name on the From address]
```

Six variable slots: subject, plainly, anchor, sim_scope, event, fork. Nothing else varies.

That fence is the template itself, not a picture of it. A local campaign tool may parse the
slots into a format string, but this skill does not require that tool. `SENDER` and `FIRST`
are filled from the sending identity and the recipient row, so only the six above are ever
written by a drafter.

## Filled example

```
Subject: What does the price committee do with a dossier once you are in the room? (Master's thesis question!)

Hi Jordan,

I'm a master's student; my thesis is on hardware-accelerated simulation of organisational decision-making, put plainly: running the payer's side of a French price negotiation through software before you sit down.

You carried a mid-sized manufacturer's pricing function through a reimbursement assessment, so you have run that file live, not in theory.

We simulate the committee's side of a round like that (which comparator it anchors on, where evidence moves the price corridor, what a counter-offer is really signalling) before the tables open. Would that have helped you in that assessment, or does sitting across from the payer teach a read no model matches? The thesis needs the answer.

Could I ask for 15 minutes on a call? I'd rather hear it live, but a written answer works too.

Thank you,
Alex
```

## The few rules

- Persona is "a master's student" only when that is true of the actual sender. Otherwise adapt
  the premise to the sender's verified role before drafting; never borrow the example persona.
  No school, field, or company belongs in the generic copy.
- One fork question, and one branch must credit their experience possibly beating the model.
  Write a fresh fork and a fresh subject for each recipient, never the same across a batch.
- The anchor names a specific thing they did (the hearing, the filing, the deal, the round)
  and is supported by the source page. A job title alone is not an anchor. Never invent.
- No em-dashes anywhere. Use commas, colons, or periods.
- The subject is their specific thing as a question, then `(Master's thesis question!)`.
- The signed name matches the From address. Two senders run now, so the wrong name reads as
  forgery to the recipient; `SENDER_NAME` sets it per run.
- Call first, a written reply always offered as the easy alternative.
- Plain text. No opt-out footer, no attachments, no tracking, no sign-off block beyond the name.
- One follow-up at most, 7 to 10 days later, in the same thread, only when it carries one genuinely new thing.
