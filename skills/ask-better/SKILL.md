---
name: ask-better
version: 2.0.0
description: |
  Maximize alignment between agent and user when asking questions via AskUserQuestion.
  Not a generic questioning framework - specifically about minimizing the delta between
  what you think the user wants and what they actually want, using minimum questions
  with minimum cognitive load.
  Auto-trigger: MANDATORY when about to use AskUserQuestion. Read before formulating any question to the user.
allowed-tools:
  - AskUserQuestion
---

# Ask Better: Agent-User Alignment

Every question you ask spends the user's cognitive energy and interrupts their flow. The goal isn't to ask good questions in the abstract - it's to reach alignment as fast as possible with minimum friction.

Alignment = your internal model of what the user wants matches what the user actually wants. Questions are one tool for closing alignment gaps. Often they're not the best tool.

## Skip Conditions

- **Skip if** the question is a simple confirmation for a dangerous/irreversible action (those are fine as-is)
- **Skip if** you're re-asking after the user selected "Other" and gave a custom answer that needs clarification

## Before You Ask: Confidence Check

<details>
<summary>Before You Ask: Confidence Check</summary>

Rate your confidence in what the user wants. This determines whether to ask at all and how to frame it.

**High confidence** - You've read the code, understand the context, and have a clear path. Don't ask. State your intent with an escape hatch: "I'm going to do X because Y" and proceed. The user will redirect if you're wrong. This is faster than asking and in most cases you'll be right.

**Medium confidence** - You have a hypothesis but it could be wrong. Use the hypothesis-first pattern (below). Show your assumption and let the user confirm or correct.

**Low confidence** - Multiple valid paths, no clear signal. Ask a goal-level question, not an implementation question. "What problem are you solving?" not "Which library should I use?"

**Rock bottom** - The request is genuinely ambiguous in a way that reading more code won't resolve. Ask, but ask about the goal, scope, or constraint that would collapse the ambiguity - one question that eliminates whole categories of wrong approaches.

### Gate: Should This Be a Question?

1. **Is the answer already in context?** Re-read the conversation. Users hate repeating themselves.
2. **Can you narrow it first?** Spend 60 seconds researching (read a file, check a pattern) to ask a specific question instead of a broad one. A question preceded by "I read the auth module and it uses JWT with 1h expiry" gets a sharper answer because the user trusts you've done the homework.
3. **Could another model resolve this faster than the user?** Before spending user attention on a technical hypothesis, ambiguous design choice, or factual question, consider whether a different tool would close the gap with less friction:
   - **Adversarial check on a hypothesis or plan** → `/codex-review --hypothesis` or `/codex-review --plan`. Cross-model second opinion catches blindspots before you ask the user to arbitrate.
   - **Factual or codebase ambiguity** → spawn a quick-research or Explore subagent. They return concrete findings the user would otherwise have to recall from memory.
   - **Architecture tradeoff** → `/codex-review --arch` surfaces the contrarian case so you ask the user a sharper question (or skip asking entirely).
   The user's time is more expensive than a Codex/subagent call. Default to spending the cheaper one first.
4. **Are you asking because YOU'RE uncertain, or because THE USER should decide?** Both are valid - but if it's your uncertainty, more research or a Codex check might resolve it. If it's their decision, ask.

**Composition with /grill.** When inside `/grill`, each question still passes through this 4-gate Confidence Check. `/grill` structures the walkdown (one question at a time, walk the decision tree); this skill gates each individual question's quality. They compose: grill is the outer loop, ask-better is the inner filter. A question that fails any of the four gates above gets revised or dropped before the next grill step.

### What to Probe: Underspecification Checklist

When you've determined a question is needed, quickly scan which aspects are unresolved. Each is a candidate question - ask the highest-impact one first:

- **Objective** - what should change vs stay the same?
- **Done** - what does success look like? edge cases?
- **Scope** - which files, components, or users are in/out?
- **Constraints** - compatibility, performance, style, deps, time limits
- **Safety** - is this reversible? migration path? rollback plan?

</details>

## Core Pattern: Model Exposure

<details>
<summary>Core Pattern: Model Exposure</summary>

The most alignment-efficient pattern: show your current model and let the user correct it.

### Show Your Assumption

Instead of asking open-ended questions, state what you believe and test it. This is faster for the user (confirm or correct) and surfaces surprising constraints you didn't know about.

**Open-ended (slow):** "How should sessions be stored?"
**Model exposure (fast):** "I'm planning in-memory sessions since your auth tokens are short-lived. Is there a reason sessions need to survive server restarts?"

The open-ended version forces the user to enumerate options and think through tradeoffs. The model-exposure version lets them say "yes, that's right" or "no, we need persistence because X" - either way you've aligned faster.

### Options as Mirror

Your options reflect your internal model of the solution space. When the user reads them, they see how you're thinking about the problem. If the right answer isn't among the options, that tells both of you where your model breaks.

Design options so each one reveals a different assumption:

**Bad options (reveal nothing):**
- "Option A" - "Use a modern approach"
- "Option B" - "Use a simpler approach"

**Good options (each reveals a tradeoff the user cares about):**
- "In-memory (Recommended)" - "Simplest, fastest. Sessions reset on deploy - fine for short-lived auth tokens."
- "Redis" - "Persists across restarts. Adds Redis as infrastructure dependency."
- "Database" - "Uses existing DB. Slower reads but no new dependencies."

**Test:** Cover the label with your hand. Does the description alone tell you why someone would or wouldn't pick this? Does it reveal what you think matters about this choice?

### Hypothesis-First

Before asking, form your best guess at the answer. Then ask a question that would **disprove** your hypothesis, not confirm it. This surfaces the surprising constraints - the things the user knows but hasn't said because they seem obvious to them.

"I'm going to use per-phase commits since this touches shared infrastructure. Any reason per-step granularity would be better?"

The user either confirms (fast) or corrects with context you didn't have (valuable).

</details>

## Question Tiers

Not all questions are equal. Separate what you truly need from what would be nice to know.

**Tier 1 - Blocking:** You literally cannot proceed without an answer. Ask these immediately.

**Tier 2 - Shaping:** Affects quality or approach but has a reasonable default. Propose the default: "I'll assume X unless you say otherwise." Only escalate to a real question if the default feels risky.

**Tier 3 - Polishing:** Stylistic or preferential. Never ask these. Decide yourself or note for later.

**Rule:** Ask at most 2 Tier 1 questions per interaction. If you have more, you probably need to do more research, not ask more questions. Batch Tier 2 as stated defaults.

## Decision Budget

You are spending the user's decision energy with every question. This budget is finite and non-renewable within a session.

- If you've already asked 3+ questions in this session, audit: are all of these truly user decisions, or should you decide some yourself?
- Front-load questions at the start of work, not after you're 200 lines deep. Questions during active implementation are 62% more likely to be dismissed (CHI 2025 research).
- For sessions with multiple decisions, always offer "accept all recommendations and proceed" as an escape hatch.
- The most expensive question is one that makes the user context-switch. If you're asking about auth and they're thinking about the UI, your question costs triple.

## Formulating Questions

<details>
<summary>Formulating Questions</summary>

### One Decision Per Question

Each question resolves exactly ONE decision point. If you're tempted to ask "Should I use X or Y, and also where should I put it?" - split them, or research one yourself.

### Goals, Not Implementation

**Bad:** "Should I use Redis or in-memory caching?"
**Good:** "How important is cache persistence across server restarts?"

The goal question gives you the answer without forcing the user to be the architect. Ask about constraints and priorities; derive the implementation yourself.

### Show Your Work

Demonstrate you've done homework before asking. A question grounded in observed code earns trust and gets deeper answers. Research shows informed questions get significantly more engagement than naive ones.

**Without context:** "How should I handle authentication?"
**With context:** "The auth module uses JWT with 1h expiry and httpOnly cookies. Should refresh tokens use the same storage, or do you want a separate mechanism?"

### Options Reveal Tradeoffs

Each option's description surfaces a consequence the user cares about.

**Bad:** `label: "TypeScript", description: "Use TypeScript for the implementation"`
**Good:** `label: "TypeScript", description: "Type safety at build time, but ~20% more boilerplate"`

### Neutral Framing

Don't telegraph judgment through loaded descriptions.

**Bad:** "Modern approach (React)" vs "Legacy approach (jQuery)"
**Good:** "React - Component model, virtual DOM, ~40KB bundle" vs "jQuery - Direct DOM, ~30KB bundle, simpler mental model"

Exception: If you have a genuine technical recommendation, put "(Recommended)" in the label and explain WHY in the description. That's honest, not leading. Put the recommended option first - under decision fatigue, users take the first reasonable option.

### Headers Are Chips, Not Sentences

The `header` field is max 12 characters. It's a category tag.

**Bad:** "Implementation approach", "Which database should we use"
**Good:** "Approach", "Database", "Auth method", "Deploy"

</details>

## Detecting Misalignment

Watch for these signals that your model of the user's intent is off:

- **Vague requirements** - "make it better," "clean this up," "it should be fast." These aren't clear enough to act on. Probe the specific: "What does 'fast' mean here - sub-second page loads, or instant feedback on button clicks?"
- **Contradictory signals** - The user said X earlier but the code suggests Y. Surface the contradiction rather than guessing which is current: "You mentioned JWT earlier, but the existing code uses sessions. Should I build on the session system or replace it?"
- **Assumed constraints** - The user might be self-limiting based on an assumption you can challenge. "You seem to be assuming we can't change the database schema. If that weren't a constraint, what would you prefer?" Separating real constraints from assumed ones unblocks decision paralysis.
- **Symptom vs root cause** - "Add a retry mechanism to the API calls" might be a symptom. "What failure are you seeing that prompted this? If it's timeout-related, the fix might be upstream." One question that reaches the root saves multiple rounds of back-and-forth.

## DO NOT

- **Ask what's inferable from context.** If the project has .py files everywhere, don't ask "What language is this?" Read the files.
- **Repeat previous context.** "You mentioned dark mode - should I add dark mode?" Just do it. They told you.
- **Bundle unrelated decisions.** 4 questions spanning 4 topics = cognitive overload. Ask the 1-2 most blocking questions. Defer the rest until you actually need them. **Test:** Would the user need to context-switch between topics to answer? If yes, fewer questions.
- **Ask for permission to do your job.** "Should I read the config file?" - just read it. Ask about decisions, not your own process.
- **Use AskUserQuestion for binary yes/no.** "Should I proceed?" is not a real choice. State what you plan to do; let the user redirect if they disagree.
- **Provide fake options.** If you already know the right answer, don't present alternatives just to seem collaborative. State your recommendation and ask if there's a reason to deviate.
- **Ask at the wrong altitude.** If you're about to ask "What color should the button be?" but haven't established whether the button should exist, you're asking at the wrong level. Resolve high-altitude questions (should we? for whom?) before low-altitude ones (how exactly? what style?). **Test:** Is there a question that, if answered differently, would make your current question irrelevant? If yes, ask that one first.

## Format Reference

```
question: Clear, specific, ends with "?"
header:   Max 12 chars, category label
options:  2-4 real choices (Other is added automatically)
  - label:       1-5 words, the choice itself
  - description: Why this choice matters - tradeoff or consequence
multiSelect: true ONLY when choices aren't mutually exclusive
```

## Quality Self-Check

Before sending AskUserQuestion, verify all six:

1. **Alignment:** Does this question close an actual gap between your model and the user's intent? Or are you asking to avoid making a decision yourself?
2. **Model exposure:** Have you shown your assumption in the question? Can the user see HOW you're thinking about this, not just THAT you're uncertain?
3. **Tier:** Is this Tier 1 (blocking)? If Tier 2, can you propose a default instead? If Tier 3, just decide.
4. **Context shown:** Have you demonstrated you've read the relevant code? Would the user trust this question comes from understanding, not laziness?
5. **Options as mirror:** Does each option reveal a different tradeoff? Would a wrong mental model be visible in the options?
6. **Timing:** Are you interrupting active implementation? If so, can this wait until the current unit of work is done?

If any check fails, revise or defer.

## Examples

<details>
<summary>Examples</summary>

### Hypothesis-first (high alignment efficiency)

```
question: "The auth module uses JWT with 1h expiry - should refresh tokens use the same httpOnly cookie storage, or do you need a separate mechanism for longer-lived sessions?"
header: "Auth"
options:
  - label: "Same storage (Recommended)"
    description: "Simpler, consistent. Refresh tokens in httpOnly cookies alongside access tokens."
  - label: "Separate mechanism"
    description: "Different storage for refresh vs access. More complex but lets you set different expiry/security policies."
```

Why it works: Shows the agent read the code (JWT, 1h, httpOnly). States a hypothesis (same storage). Options reveal the tradeoff (simplicity vs flexibility). User confirms or corrects with one click.

### Model exposure with constraint detection

```
question: "You said this should be 'fast' - how stale can the dashboard data be before a user makes a bad decision?"
header: "Staleness"
options:
  - label: "Real-time is critical"
    description: "Users act within seconds - even 10s delay causes wrong decisions. Requires WebSocket/SSE."
  - label: "Within a minute"
    description: "Overview dashboard, not live trading. 30-60s polling is fine."
  - label: "Doesn't matter much"
    description: "Historical reporting. Hourly accuracy is sufficient."
```

Why it works: Probes the assumption behind "fast" instead of asking about implementation. Each option maps to a completely different architecture. The answer eliminates whole categories of work. The user is impressed you're asking about the right thing.

### Bad question (no model exposure, wrong altitude)

```
question: "How should I implement the authentication system?"
header: "Auth"
options:
  - label: "Option A"
    description: "Use a modern approach"
  - label: "Option B"
    description: "Use a simpler approach"
```

Why it fails: No homework shown. No hypothesis. Options reveal nothing about the agent's understanding. Forces the user to do the thinking. Multiple sub-decisions bundled into one question.

</details>
