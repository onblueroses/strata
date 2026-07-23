---
name: grill
description: "Walk the user down a design decision tree one question at a time, anchored to nearby docs (CLAUDE.md, $KB_DIR/, project style docs, ADRs). Use when an open question stands about implementation approach, architecture, API shape, data model, or schema. Triggers on: 'grill me', 'should I X or Y', 'help me decide', 'one question at a time', 'I'm torn between'. Manual: /grill [topic] | --bare."
allowed-tools:
  - AskUserQuestion
  - Read
  - Grep
  - Glob
  - Edit
  - Write
---

# Grill

Goal: Reach shared understanding between user and agent on a design, plan, or architecture decision by walking the relevant decision tree one question at a time.

Success means:
  - Every branch of the decision tree carries a resolved choice or an explicit "deferred, criteria for resolution: X"
  - Doc-anchored (default) mode: nearby ADR / CONTEXT.md / glossary files reflect the crystallized decisions inline
  - The user explicitly signals alignment, or the agent has nothing left to ask

Stop when: every unresolved branch is named, every named branch is resolved or deferred-with-criteria, and the user confirms alignment.

## When to invoke

Invoke grill the moment a design or implementation question opens up. The Auto-trigger description above is the primary signal. Fire on:

- Open questions about architecture, API shape, data model, or technical approach
- User phrases that invite discussion: "what do you think", "should I X or Y", "how should we", "let's think about"
- Before /spec writes phases when user-provided context is thin
- Before /hammock enters contemplation when the problem statement is fuzzy
- Any non-trivial decision tree where the user has not walked every branch

When a trigger overlaps with /spec or /hammock: run /grill first to crystallize the intent, then return to /spec or /hammock with the sharpened question.

The bar is "would another round of questions improve the plan?" not "is this load-bearing." Cost of an extra grill round stays low. Cost of a half-baked plan stays high. Bias to fire.

## Default mode: doc-anchored

Default behavior reads from the local doc surface before asking. Check sources in this order:

1. CLAUDE.md (project root and ancestors)
2. Project ADRs and CONTEXT.md (find with Glob for `**/ADR*.md`, `**/CONTEXT.md`, `**/decisions/**/*.md`)
3. `$KB_DIR` entity files (`summary.md`, `items.json`) when the topic maps to a known entity
4. Project style docs when the topic touches writing or external-facing content
5. Project-local glossary or domain-model files

When asking a question, anchor it to what the docs already say. Surface terminology conflicts against existing glossaries. Sharpen vocabulary inline. Create ADRs only for hard-to-reverse, surprising decisions resulting from genuine trade-offs; keep routine implementation choices out of the ADR record.

## Bare mode

Pass `--bare` to skip doc anchoring and run the naked one-question-at-a-time interview. Use bare when:

- No docs exist yet (greenfield project)
- The user explicitly wants to think out loud without doc surface
- The decision is small enough that doc updates would be churn

## Codebase substitution rule

If a question can be answered by exploring the codebase, explore the codebase instead.

Read the code first, then anchor the question to what you found:

> Read `src/auth/index.ts`. Report: "Your auth module uses JWT with 1h expiry via httpOnly cookies. The next question presumes that pattern stays. Is there a reason to deviate?"

The user's attention costs more than a file read. Default to reading.

## One question at a time

Ask one question, present your recommended answer, wait for confirmation or correction. Resolve the current question before opening the next.

For each question:
- State the question
- Provide your recommended answer with reasoning anchored to the doc surface (or the code, if you read it)
- Surface the alternative(s) that would change the answer
- Wait for confirmation or correction

When the user corrects, integrate the correction and ask the next question down the tree.

Each question still passes through /ask-better's 4-gate Confidence Check before going to the user. Grill organizes the walkdown; ask-better gates the quality of each individual question.

## Composition with /spec, /hammock, /ask-better

- **/spec**: the "Creating a Spec" workflow invokes /grill when user-provided context is thin. /grill surfaces uncertainty; the strong lane (`bin/strong`) then writes against a sharpened brief.
- **/hammock**: /hammock Phase 1 references /grill as an optional pre-step when the problem statement is fuzzy or has unresolved branches. /grill structures the walkdown; /hammock contemplates the sharpened question.
- **/ask-better**: orthogonal. /ask-better gates whether to ask at all (4-gate Confidence Check). /grill organizes the questions you do ask into a tree walkdown. Grill is the outer loop; ask-better is the inner filter.

Standalone invocation: /grill works without /spec or /hammock. Invoke /grill directly to walk down a design tree before any planning skill enters the picture.

## Quality self-check

Before declaring alignment and stopping:

1. **Every branch named**: enumerate the branches of the decision tree you walked. Each one resolved or deferred-with-criteria.
2. **Recommendations given**: every question carried your recommended answer, not the bare question.
3. **Codebase substitution applied**: every question that the code could answer was answered by reading.
4. **Docs updated (default mode)**: hard-to-reverse, surprising decisions captured as ADRs. Routine decisions stay out of the ADR record.
5. **Composition respected**: when invoked from /spec or /hammock, the sharpened question returns to the calling skill.
