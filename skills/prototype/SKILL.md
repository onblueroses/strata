---
name: prototype
description: "Build throwaway code that answers one design question, capture the answer, then delete the code. Two branches: a runnable terminal app for state/business-logic questions ('does this state model feel right?'), or several radically different UI variations toggleable from one route ('what should this look like?'). The artifact is disposable; the captured answer (ADR / NOTES / commit message) is the only thing worth keeping. Manual: invoke when a design call hinges on something easier to feel by running than to reason about on paper, or when /decision-mapping emits a Prototype ticket."
disable-model-invocation: true
---

# Prototype

A prototype is throwaway code that answers a question. The question decides the shape; the answer is the only durable output.

```
Goal: Answer one specific design question by building the smallest runnable thing
      that makes the answer feel obvious, then capture the answer and delete the code.

Success means:
  - The question is stated explicitly at the top of the prototype
  - One command runs it; state is visible after every action or variant switch
  - The answer is captured somewhere durable (ADR / NOTES.md / commit message / issue)
    paired with the question it answered
  - The throwaway code is deleted or its validated decision folded into real code

Stop when: the answer is captured durably and the prototype is deleted or absorbed.
```

## Pick a branch

Identify which question is being answered, from the user's prompt, the surrounding code, or by asking the user if reachable (use the AskUserQuestion tool, gated by `/ask-better`):

- **"Does this logic / state model feel right?"** -> go to the **Logic branch**. Build a tiny interactive terminal app that pushes the state machine through cases that are hard to reason about on paper.
- **"What should this look like?"** -> go to the **UI branch**. Generate several radically different UI variations on a single route, switchable via a URL search param and a floating bottom bar.

The two branches produce very different artifacts; getting this wrong wastes the whole prototype. When the question is genuinely ambiguous and the user is unreachable, default to whichever branch matches the surrounding code: a backend module leans logic, a page or component leans UI. State the assumption at the top of the prototype.

## Rules for both branches

1. **Throwaway from day one, and marked as such.** Place the prototype code next to the module or page it prototypes for, so context is obvious; name it so any casual reader sees it is a prototype, not production (a `_prototype` suffix, a `PROTOTYPE` header comment, a clearly-temporary route). For throwaway UI routes, obey the project's existing routing convention; reuse the structure already there.
2. **One command to run.** Whatever the project's task runner already supports: `pnpm <name>`, `python <path>`, `bun <path>`, `cargo run --example <name>`. You start it without thinking.
3. **No persistence by default.** State lives in memory. Persistence is the thing the prototype is checking, not something it depends on. When the question genuinely involves a database, hit a scratch DB or a local file with a clear `PROTOTYPE-wipe-me` name; per the repo-local rule, drop it under a `.local/` directory.
4. **Skip the polish.** No tests, no error handling beyond what makes the prototype runnable, no abstractions. The point is to learn something fast and then delete it.
5. **Surface the state.** After every action (logic) or on every variant switch (UI), print or render the full relevant state so the change is visible.
6. **Delete or absorb when done.** Once the prototype has answered its question, delete it (move to `~/to-delete/` per the deletion rule, never `rm` directly) or fold the validated decision into the real code. Leave nothing rotting in the repo.

## Logic branch

Use this branch when the open question is about a state machine, a reducer, a business-rule sequence, or any flow whose correctness is easier to feel by stepping through it than to verify on paper.

Build a tiny interactive terminal app that:

- Holds the candidate state model in memory as a plain data structure.
- Exposes the transitions as numbered menu actions or single-key commands, so you drive the machine by hand.
- Prints the full relevant state after every action, including derived values, so each transition's effect is legible.
- Seeds a few hard-to-reason cases up front (the boundary, the concurrent edit, the double-submit, the out-of-order event) and lets you walk each one.

The win is watching the model behave under the awkward cases, not building a polished CLI. Keep it under one file when you can. When the model survives the awkward cases, the answer is "this shape holds"; when it buckles, the answer is the specific transition that broke and why.

## UI branch

Use this branch when the open question is visual or interaction-shaped: layout, hierarchy, density, a component's affordances, the feel of a flow.

Generate several radically different variations on a single route, switchable at runtime:

- One route renders the variant selected by a URL search param (`?variant=a`, `?variant=b`, ...).
- A floating bottom bar lists the variants and switches between them in place, so you compare without navigating away.
- Make the variants genuinely different (different layout, different information hierarchy, different interaction model), not three shades of the same thing. Divergence is where the answer lives.
- Render the full relevant state in each variant so the comparison is honest across them.

Prefer a side-by-side explorer in context over text descriptions or bare hex values: a visual decision is easier to make when the options sit next to each other in the real layout. Reach for the dedicated skills to do it well:

- `/frontend-design` for generating and refining the variations themselves.
- `/mobile-preview` to view the route at phone widths when the decision is responsive or mobile-first.

## Capture the answer

The answer is the only thing worth keeping from a prototype. Capture it somewhere durable, paired with the question it answered:

- A commit message, an ADR, a tracker issue, or a `NOTES.md` next to the prototype.
- For a surprising or hard-to-reverse decision, prefer an ADR so the reasoning survives; for a routine confirmation, a `NOTES.md` line or commit message is enough.

When the user is around, the capture is a quick conversation; when they are not, leave the placeholder (question stated, verdict slot empty) so the next pass can fill in the answer before the prototype is deleted. Capture first, delete second; an undocumented prototype that gets deleted loses the entire point of building it.

## Pairs with

- **/decision-mapping** (upstream): its Prototype ticket invokes this skill; the ticket names the question, this skill answers it and feeds the captured answer back into the decision map.
- **/frontend-design** and **/mobile-preview** (UI branch): generate and preview the variations.
- **/decision-mapping** (alternative path): when the question is walkable by reasoning it through rather than running it, resolve it as a Discuss ticket in the decision map instead of building a prototype.
