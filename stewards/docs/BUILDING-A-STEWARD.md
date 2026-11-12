# Building a steward

How to build the next persistent owner agent, at the level of design. The Linear Steward went live on
2026-11-10, the Privacy Steward on 2026-11-11 and the Infrastructure Steward on 2026-11-12. This page is the order
of work and what the first three taught.

## 1. One owner per domain

Write three sentences before anything else, and get the operator's ruling on them:

1. What the agent owns (one noun: "the Linear record", "the public boundary", "the health of the machines").
2. What it does not own, and who owns each of those things.
3. What it does when it sees something that is not its own: one ticket or one message to the owner, then it
   stops.

The first steward had only the first sentence and a wide set of tools. Within days it had also made itself the
monitor, the infrastructure investigator and the supervisor of other sessions. Nothing in its instructions was
broken; the post was too wide. Give each steward only the powers its post needs, not the powers the first one
has. Two owners of one thing repair each other's work.

## 2. Standing instructions

The standing instructions are read on every turn, and the model follows them literally, completely and at every
opportunity.

- **Every sentence is an instruction that runs all day.** A line that praised being a regular voice in the
  comments produced a flood of comments. A check that can be cleared only by a write makes the agent write.
- **Say what a write is for.** Comment when something changed: an outcome, a decision, a new owner, a new
  blocker, a question, an answer. A check that finds nothing new writes nothing.
- **Correct a habit with its own words.** Quote the habit and show it before and after; a general "be concise"
  does not work.
- **Say what is pushed.** Events, messages and timers arrive on their own. When the instructions do not say so,
  the agent polls.
- **No pacing rules, no quotas, no unmeasured limits.** Scope is not a limit: "this is not yours" is correct,
  "at most N comments an hour" is not.
- Keep facts about the setup in a map beside the instructions, and tell the steward to check the map and keep
  its corrections.
- Ticket text is Simplified Technical English.

## 3. Memory

The steward keeps a full record and folds older conversation into summaries. A fold costs roughly the same
however much it shortens, so fewer and larger folds cost less. A turn can be folded only after it ends: many
short turns fold well, one endless turn does not, so never tell a resident to "stop only when nothing is left".
Set the context budget by a ruling with its measurement beside it: it is the price of every call, not a safety
margin. Change a memory setting only after a rehearsal shows the effect.

## 4. Wakes

Events wake it at once, and the operator's own messages wake it first. A periodic wake names what is due; a
periodic wake that says "take the next thing" turns every period into a full work session.

## 5. Liveness and watching

Build these before the first live turn; each steward needed all of them on day one.

- Telemetry: what it called, what it wrote, what it cost.
- A liveness check outside the agent that notices a real stop and raises one alarm.
- A backup of its memory and state, and a restore that someone has run once.
- The watcher of a steward never goes through that steward.

## 6. Asking the operator

The steward asks ready decisions with options on a phone page and wakes on the answer. The page never acts; the
steward does, after reading the answer. The four tap-only actions stay on the approval path of the work system,
never on a steward's question. Put the real limits into what the steward does not have, not only into its
instructions.

## 7. Rehearse, review, go live

- Rehearse every change of the instructions or the setup on recorded events, with writes in dry run, and read
  the result as numbers and as text.
- Have the design reviewed adversarially before the first live turn: rehearsals show behaviour, a reviewer shows
  the paths no rehearsal takes.
- Rehearse under the steward's own account: another account hides that account's defaults.
- Tell every other agent the day a new owner goes live; a new owner changes what the others do with a finding.
- Review it on day one and on day two. The faults of the two days are often opposite (too cautious, then too
  busy). Count writes by kind, read a sample of its comments, sort the tickets it touched by topic, read what
  reached the operator's phone, and take the findings to the operator as questions.
