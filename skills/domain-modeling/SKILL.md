---
name: domain-modeling
description: "Build and sharpen a project's domain model during design: map bounded contexts, test precise concept boundaries with edge cases, compare stated behavior with code, surface contradictions, and write the glossary as terms crystallize. This is the write-side counterpart to /decision-mapping; use it when the model changes, a ubiquitous language needs definition, a bounded context needs naming, or an architectural decision needs an ADR. Triggers on: 'domain model', 'ubiquitous language', 'bounded context', 'context map', 'glossary', 'name this concept', 'model the domain', 'is this term right', and 'write an ADR'. Also triggers when a design reuses a fuzzy term, a subsystem needs a context boundary, or stated behavior and code disagree about a concept. Pairs with /decision-mapping, /spec, and /recon. Manual: /domain-modeling [topic]."
allowed-tools:
  - Read
  - Grep
  - Glob
  - Edit
  - Write
---

# Domain Modeling

Actively build and sharpen the project's domain model while you design. This is the *write-side* discipline: invent edge-case scenarios, cross-reference behavior against the code, and write the glossary and decisions down the moment they crystallize. Merely *reading* a `CONTEXT.md` for vocabulary is a one-line habit any skill can do; this skill fires when you are changing the model, not just consuming it.

```
Goal: Leave the domain model sharper than you found it: precise canonical terms, the right
      context boundaries drawn, and every crystallized decision written to disk inline.

Success means:
  - Every term resolved this session is captured in the right CONTEXT.md (glossary only)
  - Multi-context repos route each term to its owning context via CONTEXT-MAP.md
  - Edge-case scenarios were used to force boundary precision, not glossed over
  - Every "this is how it works" claim was checked against the code; contradictions surfaced
  - Hard-to-reverse, surprising trade-off decisions captured as ADRs; routine choices left out

Stop when: the terms touched this session are written down, the code-vs-claim contradictions
           are surfaced and resolved, and any qualifying decision has an ADR.
```

## Relationship to /decision-mapping

/decision-mapping is the upstream decision-resolution interview: it walks open design questions down to resolved tickets one at a time, sharpens vocabulary against existing glossaries as decisions crystallize, and is where the design calls get made before /spec presumes them. Domain-modeling is where that interview lands when the model itself starts changing. These read-side sharpening moves belong upstream; reach for /decision-mapping when a decision still needs walking, rather than re-running it here:

- **Challenge against the glossary** when a term conflicts with the existing language.
- **Sharpen fuzzy language** when an overloaded term ("account", "user") needs splitting into precise canonical terms.
- **Resolve the open question** that gates the model before you write it down.

This skill adds the write-side moves the interview does not have: the multi-context CONTEXT-MAP structure, edge-case scenario invention, code cross-referencing, the glossary-only discipline for CONTEXT.md, and the ADR gate applied at write time.

## File structure

Most repos have a single context:

```
/
├── CONTEXT.md
├── docs/
│   └── adr/
│       ├── 0001-event-sourced-orders.md
│       └── 0002-postgres-for-write-model.md
└── src/
```

When a `CONTEXT-MAP.md` sits at the root, the repo has multiple bounded contexts. The map routes each one to where it lives:

```
/
├── CONTEXT-MAP.md
├── docs/
│   └── adr/                          ← system-wide decisions
├── src/
│   ├── ordering/
│   │   ├── CONTEXT.md
│   │   └── docs/adr/                 ← context-specific decisions
│   └── billing/
│       ├── CONTEXT.md
│       └── docs/adr/
```

Create files lazily, only when you have something to write. When no `CONTEXT.md` exists, create one as the first term resolves. When no `docs/adr/` exists, create it as the first ADR is needed. When a second context appears and no `CONTEXT-MAP.md` exists yet, create the map and move the existing glossary into its owning context.

## The new moves

### Map multiple contexts (CONTEXT-MAP.md)

When a term means different things in different parts of the system, that is the signal for separate bounded contexts. A "Customer" in `ordering` (someone with a cart) is not the "Customer" in `billing` (an entity with a payment method and a balance). Route each meaning to its own context instead of forcing one overloaded definition.

`CONTEXT-MAP.md` is a routing table, not a glossary. Keep it to: one row per context, where its `CONTEXT.md` lives, a one-line description of what the context owns, and the shared terms that cross the boundary with how each side names them. Inline format:

```markdown
# Context Map

| Context  | Glossary path           | Owns                                    |
|----------|-------------------------|-----------------------------------------|
| ordering | src/ordering/CONTEXT.md | Carts, line items, order lifecycle      |
| billing  | src/billing/CONTEXT.md  | Invoices, payment methods, balances     |

## Shared terms across the boundary
- **Customer**: `ordering` = a session with a cart; `billing` = an entity with a balance.
  Linked by customer_id; the two are not the same aggregate.
```

When the same term appears in two glossaries with the same meaning, that is a smell: either it belongs to one context the other references, or the boundary is drawn in the wrong place. Surface it.

### Invent edge-case scenarios

When domain relationships are being discussed, stress-test them with concrete scenarios that probe the boundaries between concepts. Invent the awkward case on purpose and make the user be precise about it.

- "An Order has Line Items. What happens to the Order when its last Line Item is removed: does it become an empty Order, or cease to exist?"
- "A subscription renews at midnight while a refund for last month is mid-flight. Which balance does the renewal charge see?"
- "Two contexts both say 'cancel'. Cancel an Order before fulfillment and cancel an Invoice after payment are different operations; are they the same word by accident?"

The scenario does the work the abstract question cannot: it forces a yes/no at a real boundary, and the answer is a glossary entry or a context split.

### Cross-reference code and surface contradictions

When the user states how something works, check whether the code agrees. Read the cited or implied code before accepting the claim. When you find a contradiction, surface it with both sides:

> You said partial cancellation is possible, but `src/ordering/order.ts:88` cancels the whole Order in one transaction with no line-item granularity. Which is the real model: the code, or the intent you just described?

A contradiction is a fork: either the code is wrong (a bug to file) or the stated model is wrong (a vocabulary or design correction). Name which one, then resolve it. Do not let the glossary record an intent the code contradicts without flagging the gap.

### Write CONTEXT.md inline, glossary only

When a term resolves, write it into the owning `CONTEXT.md` right then. Capture decisions as they happen rather than batching them; batched glossary updates rot before they get written.

`CONTEXT.md` is a glossary and nothing else. Keep implementation details, specs, and decision rationale out of it; those live in code, specs, and ADRs respectively. Inline glossary-entry format:

```markdown
# Ordering: Glossary

## Order
A customer's request to purchase, holding one or more Line Items through a lifecycle
(draft → placed → fulfilled → closed). An Order with zero Line Items cannot be placed.

## Line Item
A single product-and-quantity within an Order. Removing the last Line Item returns the
Order to draft; it does not delete the Order.

## Cancellation
Terminating a placed Order before fulfillment. Distinct from a billing Refund, which acts
on an Invoice after payment. Partial cancellation is not modeled; cancel acts on the whole Order.
```

One term per `##` heading, a precise definition, and the boundaries against neighbouring terms. No code snippets, no "we chose Postgres because", no TODOs.

## The ADR gate

Whether a decision earns an ADR comes down to a three-part test. Offer an ADR only when all three hold:

1. **Hard to reverse**: the cost of changing your mind later is meaningful.
2. **Surprising without context**: a future reader will wonder "why did they do it this way?"
3. **The result of a real trade-off**: genuine alternatives existed and you picked one for specific reasons.

When any of the three is missing, skip the ADR; routine implementation choices stay out of the record. When all three hold, write the ADR with this inline format (numbered sequentially in the owning `docs/adr/`):

```markdown
# NNNN. <short decision title>

Status: accepted
Date: <YYYY-MM-DD>

## Context
What forces the decision: the constraint, the conflict, the thing that makes this non-obvious.

## Decision
The choice, stated as a present-tense fact ("We model Orders as event-sourced aggregates").

## Consequences
What this makes easy, what it makes hard, and what a future reader should know before reversing it.
```

## Quality self-check

Before declaring the model sharper and stopping:

1. **Terms written down**: every term resolved this session is in the right `CONTEXT.md`, not still in conversation.
2. **Routing correct**: in a multi-context repo, each term landed in its owning context, and `CONTEXT-MAP.md` reflects any new boundary or shared term.
3. **Boundaries stress-tested**: at least the load-bearing relationships were probed with a concrete edge-case scenario, not accepted abstractly.
4. **Code agrees**: every "how it works" claim was checked against the code; contradictions were surfaced and resolved, not buried.
5. **CONTEXT.md stayed a glossary**: no implementation details, specs, or rationale leaked in.
6. **ADRs earned, not sprayed**: each ADR passed all three gate tests; routine decisions stayed out.
