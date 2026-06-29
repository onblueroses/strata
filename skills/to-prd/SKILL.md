---
name: to-prd
description: "Turn the current conversation into a published PRD — the product-framing step upstream of /spec. Synthesizes what you and the user already discussed into a problem-and-solution document written from the user's perspective: problem statement, solution, an extensive user-story list, implementation decisions, testing decisions, out-of-scope, and notes. Reads the codebase to ground seams and vocabulary, gates its language on the project glossary (/domain-modeling) and architecture (/codebase-design), and writes the PRD as markdown the user designates. No interview — the conversation already happened; this is synthesis. Manual: invoke after a design conversation has converged and you want to capture it as a shareable PRD before /spec turns it into execution phases, or when the user says 'write this up as a PRD', 'turn this into a PRD', 'draft a PRD', 'publish a PRD', 'product spec for this', 'capture what we decided'. Pairs with /domain-modeling and /codebase-design (upstream — supply the glossary and seam vocabulary the PRD speaks in), /spec (downstream — the PRD frames the problem, /spec records the execution plan and state), /to-issues (downstream — splits a published PRD into tracked work items)."
disable-model-invocation: true
---

# To-PRD

Goal: Produce one PRD that captures the converged conversation from the user's perspective and writes it where the user designates.

Success means:
  - The PRD follows the template below, written in the project's domain vocabulary
  - The seams the feature tests against are sketched and confirmed with the user
  - Implementation and testing decisions are recorded as prose, no file paths or stale code
  - The PRD lands as markdown at the path the user names
  - The conversation supplied the content; this skill synthesized it, ran no interview

Stop when: the PRD is written to the designated path and the user has confirmed the seams.

## Position in the flow

`/to-prd` is the product-framing step. It sits upstream of `/spec`:

- **`/to-prd`** answers "what problem, for whom, solved how, and proven by what tests" from the user's perspective. The output is a shareable document.
- **`/spec`** answers "which phases, which files, which acceptance criteria, what we decided and why" from the implementer's perspective. The output is execution state that survives compaction.

Frame the problem with `/to-prd`, then hand the PRD to `/spec` to plan the build. Skip `/to-prd` when there is no product framing to capture and the work goes straight to a spec; reach for it when a design conversation converged and the shape of the feature deserves a document before any phase is written.

## No interview

This skill takes the conversation that already happened and synthesizes it. The discussion is the input; do not re-ask the user what they already told you. When a genuine gap blocks the PRD (an undecided branch, an ambiguous actor), surface that one gap and resolve it; otherwise write from what you have.

When the conversation never happened — the user wants a PRD from a cold start — walk the decision tree with `/decision-mapping` first, then return here to synthesize.

## Vocabulary gate

The PRD speaks the project's language, not generic product-speak. Before writing:

- Read the domain glossary from `/domain-modeling` (or the project's domain-model / glossary files). Use those exact terms for actors, entities, and operations throughout the PRD; surface any term the conversation introduced that conflicts with an existing glossary entry, and resolve it toward the glossary.
- Read the architecture vocabulary from `/codebase-design` (or the project's ADRs and CONTEXT docs). Respect any ADR that governs the area the feature touches; name modules and boundaries the way the codebase already names them.

When neither source exists yet, fall back to the names the codebase uses (read it) and flag in `Further Notes` that the project has no glossary or ADR record to anchor against.

## Process

1. **Explore the repo to ground the PRD.** Read the current state of the area the feature touches if it is not already in working memory. Pick up the domain glossary and the ADRs per the vocabulary gate above.

2. **Sketch the test seams.** Name the seams at which this feature gets tested. Prefer existing seams to new ones, and prefer the highest seam available — the fewer seams across the codebase, the better, and one is the ideal. When new seams are needed, propose them at the highest point you can. Confirm the seams with the user before writing the PRD; this is the one place the skill pauses for input, because a wrong seam choice propagates into every downstream test decision.

3. **Write the PRD and place it.** Fill the template below. Write the PRD as markdown to the path the user designates (a `docs/prd/` file, an entity doc under `$KB_DIR/`, wherever the user keeps PRDs). PRDs live as plain markdown the user owns; this skill creates no tracker entry and applies no triage label — handing the published PRD to `/to-issues` is what splits it into tracked work.

## Template

<details>
<summary>## PRD template</summary>

```markdown
## Problem Statement

The problem the user faces, from the user's perspective.

## Solution

The solution to that problem, from the user's perspective.

## User Stories

A long, numbered list of user stories, each in the form:

1. As an <actor>, I want a <feature>, so that <benefit>

Example:

1. As a mobile bank customer, I want to see the balance on my accounts, so that I can make better-informed decisions about my spending.

Make this list extensive; cover every aspect of the feature.

## Implementation Decisions

The decisions made during the conversation, as prose:

- Modules to build or modify
- Interfaces of those modules that change
- Technical clarifications from the user
- Architectural decisions
- Schema changes
- API contracts
- Specific interactions

Skip specific file paths and code snippets; they go stale fast.

Exception: when a prototype produced a snippet that encodes a decision more precisely than prose can (a state machine, reducer, schema, or type shape), inline that fragment within the relevant decision and note it came from a prototype. Trim to the decision-rich part; this is the load-bearing shape, not a working demo.

## Testing Decisions

The testing decisions made:

- What makes a good test here (test external behavior, not implementation details)
- Which modules get tested
- Prior art for the tests (similar test types already in the codebase)

## Out of Scope

What this PRD deliberately leaves out.

## Further Notes

Anything else worth recording about the feature.
```

</details>

## Quality self-check

Before declaring the PRD done:

1. **User perspective held**: the Problem Statement and Solution read from the user's view, not the implementer's.
2. **Glossary honored**: actors, entities, and operations use the project's domain terms; any conflict was surfaced and resolved.
3. **Seams confirmed**: the test seams were sketched, are as high and as few as the codebase allows, and the user agreed to them.
4. **No stale specifics**: implementation decisions carry no file paths and no code beyond a justified prototype fragment.
5. **Placed, not orphaned**: the PRD is written to the path the user designated, ready for `/spec` to plan or `/to-issues` to split.

Ported from mattpocock/skills (skills/engineering/to-prd), release mattpocock-skills@1.0.0.
