---
name: decision-mapping
description: "Turn a loose idea into a sequenced map of investigation tickets, then drive them to resolution one ticket at a time. A pre-plan, stateful open-question map that sits upstream of /spec: /spec presumes the decisions are already made, decision-mapping is where they get made. The whole map loads into every session, so it stays compact and git-tracked next to the project. Each ticket is Research, Prototype, or Discuss, sized to one ~100K-token session, and resolving it pushes back the fog of war until the path to the finish line is clear. Manual: invoke when a loose idea needs more than one agent session to become a plan, when open decisions span investigation + prototyping + discussion, when you want a resumable decision artifact that survives compaction, or with a map path + ticket number to resume one. v0 (upstream is in-progress)."
disable-model-invocation: true
---

# Decision Mapping

Goal: turn a loose idea into a compact, git-tracked map of investigation tickets, then drive those tickets to resolution one at a time until the path to a plan is clear.

Success means:
  - One compact Markdown map exists, git-tracked alongside the project, loadable whole into any session.
  - The frontier is identified, trivially-decidable questions are resolved inline, and everything beyond the frontier is honest fog.
  - Each ticket is typed (Research | Prototype | Discuss), carries its `Blocked by` edges, and is sized to one ~100K-token session.
  - On resume, the named ticket carries a recorded answer and any newly-discovered tickets are added with correct edges.

Stop when: the map is built (bootstrap) or the named ticket is resolved and its downstream tickets are added (resume). Building the map and resolving tickets are separate sessions; one session does one job.

This skill is for the moment a loose idea needs more than one agent session to turn into a plan. It builds a stateful decision map in a Markdown file and walks the user through a sequence of tickets that resolve the open questions; a ticket resolves by prototyping, research, or discussion.

decision-mapping sits **upstream of /spec**. /spec presumes the decisions are made and writes phases against them; decision-mapping is where those decisions get made. When the map reaches "done", hand its resolved decisions to /spec.

## The decision map

The decision map is a single compact Markdown file, one per planning effort, git-tracked alongside the project. It is the canonical artifact: the **whole map loads as context into every session**, so keep it compact.

Link to assets created during tickets; do not duplicate them inside the map. A prototype, a research summary, an ADR each live in their own file, referenced by path from the ticket that produced them.

### Structure

Numbered entries ("tickets"), each its own section keyed by its number:

```markdown
## #1: Relational Or Non-Relational Database?

Blocked by: #<ticket-number>, #<ticket-number>
Type: Research | Prototype | Discuss

### Question

<question-here>

### Answer

<answer-here>
```

Size each ticket to one ~100K-token agent session. A ticket that would not fit splits into two.

## Ticket types

Three types:

- **Research**: read documentation, third-party APIs, or local resources like knowledge bases. Produces a Markdown summary as a linked asset. Use this when the answer lives in knowledge outside the current working directory.
- **Prototype**: write UI or logic code to test a hypothesis or explore a design space. Uses the /prototype skill. Produces a prototype as a linked asset. Use this when "how should it look" or "how should it behave" is the key question.
- **Discuss**: a conversation with the agent. Uses /domain-modeling. The default case.

## Fog of war

The map is _deliberately_ incomplete beyond the frontier. Investigate the frontier, resolve tickets in order, and push the frontier forward. Push back the fog of war one node at a time.

At some point the fog has receded far enough that the path to the finish line is clear. At that point no more tickets are needed and the map is "done".

## Invocation

Two ways in: **bootstrap** and **resume**.

### Bootstrap

The user invokes with a loose idea.

1. Run a /domain-modeling session to surface the open decisions.
2. Write a new decision map: mostly fog, frontier identified, trivially-decidable entries resolved inline.
3. Stop. Map-building is one session's work; resolving tickets is a separate session.

### Resume

The user invokes with a path to an existing map and a ticket number.

1. Load the **whole map** as context.
2. Run a session to resolve the ticket, invoking skills as needed. When in doubt, use /domain-modeling.
3. Record what the session resolved in the ticket's `Answer` body.
4. Add newly-discovered tickets with correct `Blocked by` edges.
5. Stop.

When the decisions made invalidate other parts of the map, update or delete those nodes.

## Parallelism

The user may run tickets in parallel, so expect other agents to change the map between your reads. Reload the whole map before writing, and write only the ticket you own plus the new tickets it spawned.

## Skipping the decision map

Often the initial /domain-modeling interview surfaces no fog: no unresolved tickets, nothing to do except implement. In that case, offer the user the chance to skip the map; the map earns its cost only when multi-session decisions are in play.

When they skip it, recommend either implementing directly or using /spec (or /to-prd) to schedule a multi-session implementation.

## Provenance
