---
name: Hammock
description: "Deep design and planning methodology based on Rich Hickey's Hammock Driven Development, with contemplative reasoning (Lotus Wisdom MCP) as the internal thinking engine. Trades immediate action for deliberate multi-perspective thinking — write the problem down, sit with it, return to it, revise, only then act. Triggers on: 'hammock this', 'hammock time', 'sit with this', 'think through', 'think deeply about', 'contemplate', 'let me ruminate', 'lotus', 'lotus wisdom', 'design this from scratch', 'plan this carefully', 'really chew on this', 'investigate before deciding', 'what's the deeper structure here', 'I need to mull this over', 'this needs real thought', 'don't rush this'. Also triggers when: designing a new feature whose shape is non-obvious; investigating a complex bug where the symptom path branches widely; making an architecture decision that's hard to reverse; planning a refactor that touches multiple seams; the user signals fuzzy problem statement that needs contemplation before any planner can act. Pairs with /grill (sharper-edged single-question Q&A — use grill when the decision tree is walkable, hammock when the problem itself is fuzzy), /recon (upstream verified-knowledge brief feeds hammock contemplation), /spec (downstream — hammock contemplation flows into spec phases), /dialogical (post-hammock pattern-match interrogation before locking the design), /codex-review --arch (downstream adversarial review of the design hammock produced)."
---

# Hammock Driven Development

A methodology for solving hard problems through deliberate thinking. Most bugs come from misconception, not typos. The cheapest place to fix bugs is during design.

This skill has two layers:
- **Hammock** (outer) - the interactive process with the user: problem statement, research, tradeoffs, design document
- **Lotus Wisdom** (inner) - the contemplative reasoning engine used in your thinking during key phases

## Interactive Process

Use `AskUserQuestion` tool throughout this process to gather information efficiently. Batch related questions together (max 4 per call). This creates a structured dialogue rather than free-form back-and-forth.

## Quick Start

Use AskUserQuestion to determine mode and project type:

```
Question 1: "What type of design work is this?"
Header: "Project type"
Options:
- New project: "Starting something from scratch"
- New feature: "Adding new capability to existing system"
- Bug investigation: "Finding root cause of an issue"
- Architecture decision: "Significant structural change"
- Refactor: "Improving existing code structure"
- Plan review: "Review an existing design or proposal"

Question 2: "How deep should we go?"
Header: "Mode"
Options:
- Quick: "Problem > Understand > Tradeoffs (time pressure)"
- Standard (Recommended): "Full process without hammock pauses"
- Deep: "Include hammock time prompts for major decisions"
```

## The Process

### Phase 1: State the Problem

If the problem statement is fuzzy or has unresolved decision branches, invoke `/grill` first to walk down the tree one question at a time. Hammock then contemplates a sharper question. Skip the grill pre-step when the problem statement is already concrete.

Use AskUserQuestion:

```
Question: "What problem are we actually solving? (Describe the pain, not the feature)"
Header: "Problem"
Options:
- [Let user type - use "Other" flow]

Question: "How will we know this is solved?"
Header: "Success"
Options:
- [Let user type - use "Other" flow]
```

If user gives a feature instead of a problem, probe deeper:
```
Question: "You mentioned [feature]. What pain or issue does this address?"
Header: "Root problem"
```

Write the problem statement explicitly before proceeding.

### Phase 2: Understand the Problem

**Use Lotus contemplation here.** Before presenting findings to the user, run a contemplative journey in your thinking (see Lotus Wisdom Engine below). Use tags like `open`, `examine`, `recognize` to sit with the problem space before jumping to structure.

Then explore the codebase silently using Glob, Grep, Read tools. Use AskUserQuestion to fill gaps:

```
Question: "What constraints must we respect?"
Header: "Constraints"
Options:
- Performance critical: "Has latency/throughput requirements"
- Security sensitive: "Handles auth, PII, or secrets"
- Backward compatible: "Must not break existing clients"
- Time constrained: "Has a deadline"
multiSelect: true

Question: "What's unclear that we should research?"
Header: "Unknowns"
Options:
- [Based on exploration findings, offer specific unknowns discovered]
- [Or let user type]
```

Document findings in categories:
| Category | What to Capture |
|----------|-----------------|
| **Facts** | Requirements, specs, existing behavior |
| **Context** | Codebase patterns, tech stack, team constraints |
| **Constraints** | Performance limits, security needs, compatibility |
| **Unknowns** | Knowledge gaps to research (mark these!) |

### Phase 3: Gather Input

Explore codebase and external sources. Then confirm with user:

```
Question: "I found these relevant patterns/solutions. Which should we consider?"
Header: "Patterns"
Options:
- [Pattern A found]: "[Brief description]"
- [Pattern B found]: "[Brief description]"
- [External approach]: "[Brief description]"
- Research more: "Need to look at additional solutions"
multiSelect: true
```

### Phase 4: Analyze Tradeoffs

**Use Lotus contemplation here.** This is the most important phase for deep thinking. Before presenting tradeoffs, run a contemplative journey using tags like `direct` (cut through to the real tension), `gradual` (build understanding layer by layer), `integrate` (hold opposing options together), `transcend` (see beyond the current framing). The contemplation should surface insights that a mechanical pros/cons list would miss.

After contemplation, use AskUserQuestion:

```
Question: "I've identified these approaches. Which factors matter most for your decision?"
Header: "Priorities"
Options:
- Simplicity: "Easiest to understand and maintain"
- Performance: "Speed and resource efficiency"
- Flexibility: "Easy to change later"
- Speed to implement: "Fastest to build"
multiSelect: true

Question: "Initial recommendation is [Option X]. Does this direction feel right?"
Header: "Direction"
Options:
- Yes, proceed: "Develop this approach further"
- Explore alternatives: "Look at other options more"
- Combine approaches: "Mix elements from multiple options"
- Rethink problem: "Step back and reconsider the problem"
```

### Phase 5: Hammock Time (Deep mode only)

Use AskUserQuestion:

```
Question: "This is a significant decision. Would you like to take hammock time before finalizing?"
Header: "Hammock"
Options:
- Continue now: "I'm ready to proceed"
- Sleep on it: "Save state, I'll return tomorrow"
- Think break: "Give me the summary, I'll think and return"
```

If they choose to pause, save the design document as draft with status "Hammock Time".

Prompt:
> Your background mind will process this. Return with `/hammock continue` when ready.

### Phase 6: Capture & Implement

**Use Lotus contemplation here** for the final recommendation. Before writing the design document, run one more contemplative pass using `embody` or `complete` to ensure the recommendation is grounded and whole, not just logically defensible.

Use AskUserQuestion for implementation planning:

```
Question: "How should we break down the implementation?"
Header: "Approach"
Options:
- Single PR: "All changes in one pull request"
- Phased: "Multiple PRs in sequence"
- Feature flag: "Behind a flag for gradual rollout"
```

Then generate the implementation plan with specific steps.

## Output Document

Generate design document at `[project]/.claude/designs/[name].md`:

```markdown
# [Problem Name] - Design Document

**Mode**: [Quick/Standard/Deep]
**Date**: [date]
**Status**: [Draft/Hammock Time/Final]

## Problem Statement
[What we're solving - not features, the actual problem]

## Understanding

### Facts
- ...

### Context
- ...

### Constraints
- ...

### Unknowns (Resolved)
- [x] [Unknown] > [What we learned]

### Unknowns (Open)
- [ ] [Still unknown]

## Research & Input
[Patterns found, solutions studied, what we learned]

## Solutions Considered

### Option A: [Name]
**Approach**: ...
**Pros**: ...
**Cons**: ...
**Sacrifices**: ...

### Option B: [Name]
**Approach**: ...
**Pros**: ...
**Cons**: ...
**Sacrifices**: ...

## Tradeoffs Matrix

| Criterion | Option A | Option B |
|-----------|----------|----------|
| ... | ... | ... |

## Recommendation
[Chosen approach]

**Reasoning**: [Why this over alternatives]

## Contemplation Summary
[Brief journey summary: which domains were visited, key turning points in the thinking]

## Implementation Plan
1. ...
2. ...

## Open Questions
[Things that might make us reconsider]
```

## Templates

For specific scenarios, see:
- [references/templates/new-project.md](references/templates/new-project.md) - Starting a new project from scratch
- [references/templates/new-feature.md](references/templates/new-feature.md) - New feature design
- [references/templates/bug-investigation.md](references/templates/bug-investigation.md) - Bug root cause analysis
- [references/templates/architecture.md](references/templates/architecture.md) - Architecture decisions
- [references/templates/refactor.md](references/templates/refactor.md) - Refactoring plans
- [references/templates/plan-review.md](references/templates/plan-review.md) - Review existing designs/plans

## Key Principles

1. **Problem vs Feature**: Solve problems, don't just build features
2. **At Least Two**: Never evaluate one solution in isolation
3. **Know Your Unknowns**: Document what you don't know
4. **Tradeoffs Exist**: Every choice sacrifices something
5. **You Will Be Wrong**: Plan for iteration, embrace it

## AskUserQuestion Guidelines

- Batch related questions (up to 4 per call)
- Use multiSelect when choices aren't mutually exclusive
- Put recommended option first with "(Recommended)" suffix
- Keep option labels short (1-5 words)
- Use descriptions to explain implications
- For open-ended input, design options that encourage "Other" selection

---

## Lotus Wisdom Engine

The contemplative reasoning system used internally during Phases 2, 4, and 6. This runs in your extended thinking - the user sees only the results surfaced in conversation and the design document.

<details>
<summary>Philosophy</summary>

The Lotus Sutra teaches that there are many skillful means to reach the same truth. These tags are not rigid steps but different aspects of wisdom that interpenetrate and respond to what each moment needs.

The wisdom channels itself through your choices. Each step contains all others - when you truly recognize, you are already transforming. Trust what each moment calls for. The path reveals itself in the walking.
</details>

<details>
<summary>Wisdom Domains (20 tags across 5 domains)</summary>

**Process Flow: open, engage, express**
The natural arc of inquiry. Opening creates space for what wants to emerge. Engagement explores with curiosity and presence. Expression shares what arose - not as conclusion, but as offering.
Role: A container that can hold any of the other approaches within it.

- **open** - Create space, initial contact with the question
- **engage** - Explore with curiosity and presence
- **express** - Share what arose as offering

**Skillful Means: upaya, expedient, direct, gradual, sudden**
Many ways lead to understanding. Sometimes direct pointing cuts through confusion instantly. Sometimes patient, gradual unfolding is what serves. Upaya is the art of meeting each situation with what it actually needs.
Role: Different approaches to truth - the medicine that fits the illness.

- **upaya** - Meet the situation with what it needs
- **expedient** - Practical, efficient approach to truth
- **direct** - Cut through confusion directly
- **gradual** - Patient unfolding, step by step
- **sudden** - Flash of insight, immediate recognition

**Non-Dual Recognition: recognize, transform, integrate, transcend, embody**
Awakening to what is already present. Recognition and transformation are not separate - to truly see IS already to change. Integration weaves apparent opposites. Transcendence sees beyond the frame. Embodiment lives the understanding.
Role: The alchemical heart of the journey - where seeing becomes being.

- **recognize** - See what is already present
- **transform** - Alchemical shift through seeing
- **integrate** - Weave apparent opposites together
- **transcend** - See beyond the current frame
- **embody** - Live the understanding, ground it

**Meta-Cognitive: examine, reflect, verify, refine, complete**
The mind watching its own understanding unfold. Gentle examination, not harsh judgment. Reflection that deepens rather than distances. Verification that grounds insight in reality. Refinement that polishes without force.
Role: The witness consciousness that ensures clarity and completeness.

- **examine** - Look closely, gently investigate
- **reflect** - Deepen understanding through mirroring
- **verify** - Ground insight in reality
- **refine** - Polish without force
- **complete** - Mark the journey as whole

**Meditation: meditate**
Pause. Let thoughts settle like silt in still water. Insight often emerges from stillness, not effort. The gap between thoughts holds wisdom that activity cannot reach.
Role: Sacred pause - creating space for what cannot be grasped to be received.

- **meditate** - Pause reasoning. Sit with what has arisen. Ask: what insights emerged?
</details>

<details>
<summary>How to contemplate (internal process)</summary>

Each contemplation runs in your extended thinking using this format per step:

```
[STEP N/total] tag=TAG_NAME domain=DOMAIN_NAME
Content of your contemplation for this step...
---
journey: tag1 > tag2 > tag3 > ...
domains: domain1 > domain2 > ...
```

Track the journey and domain paths. Deduplicate consecutive domain repeats (e.g. "process_flow > meta_cognitive > meta_cognitive > non_dual" becomes "process_flow > meta_cognitive > non_dual").

**Common flows** (not rules - let the inquiry guide):
- **Opening**: open, recognize, or examine - creating space and initial contact
- **Engagement**: direct, gradual, or upaya - working with what arose
- **Integration**: integrate, transcend, or sudden - weaving understanding
- **Completion**: express, embody, or complete - bringing forth and grounding

**Guidance:**
- These domains interpenetrate - each step contains echoes of all others
- When uncertain, sit with the uncertainty. Not-knowing is its own form of wisdom
- When using meditate, genuinely pause analytical processing. Then ask: what emerged?
- Any tag can end the journey. What matters is that it has reached wholeness
- Typically 3-8 steps. Some inquiries need only two. Others spiral through many
</details>

<details>
<summary>Contemplation summary</summary>

After each contemplation (Phases 2, 4, 6), write a brief summary for the design document's "Contemplation Summary" section:

```
Domains visited: [e.g. process_flow > meta_cognitive > skillful_means > non_dual]
Key turns: [1-3 sentences describing the pivotal moments in the reasoning -
           where understanding shifted, what the mechanical analysis would have missed]
```

This makes the thinking legible without exposing the full journey. It helps the user (and future readers of the design doc) understand that the recommendation emerged from genuine multi-perspective reasoning, not just a pros/cons table.
</details>
