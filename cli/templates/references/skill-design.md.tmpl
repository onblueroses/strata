# Skill Design Principles

How to write effective skills (reusable procedural knowledge for AI agents). Read when creating or improving a skill, writing skill descriptions, or evaluating skill quality.

---

## Quick Nav

| Task | Section |
|------|---------|
| Write good skill instructions | 1. Instruction Quality |
| Structure a skill file | 2. Structure |
| Manage token costs | 3. Token Efficiency |
| Write trigger descriptions | 4. Description Optimization |

---

## 1. Instruction Quality

<details>
<summary>1. Instruction Quality</summary>

### Anti-examples with reasoning

"DO NOT start the summary with 'In this session, we...'" prevents more failures than "Write a good summary." List the 3-6 most common failure modes for a skill's output - but pair each with WHY it's bad. A model that understands the reasoning generalizes to novel situations; bare prohibitions only cover exact cases.

### Concrete tests beat abstract rules

| Abstract (fails) | Concrete (works) |
|-------------------|------------------|
| "The output must be high quality" | "Cover the summary with your hand - does the takeaway teach something on its own?" |
| "Use good formatting" | "Every section has a heading. No section exceeds 20 lines." |
| "Be thorough but concise" | "Between 3-5 bullet points. Each under 15 words." |

Give the AI a mechanical test it can apply, not a judgment call it can rationalize.

### Format templates with fill-in-the-blank

Bad: "Write decisions with alternatives considered."
Good: Formats: `Chose X over Y because Z.` / `Left X unchanged because Y.` / `Deferred X because Z.`

Multiple format templates cover more real-world cases than a single abstract instruction.

### Good/bad examples table

Side-by-side field-level comparison is the highest-impact few-shot format. 2-3 good examples + 1-2 bad ones. Bad examples should be things the AI would plausibly write, not strawmen.

### Controlled vocabularies

When a field has a finite set of good values (tags, status codes, entity types), enumerate them. Open-ended fields drift rapidly. Before adding a new value to a vocabulary, check if an existing value covers the same meaning.

</details>

---

## 2. Structure

<details>
<summary>2. Structure</summary>

### Skip conditions first

Put "**Skip if** [condition]" as the first line of optional steps, not buried in the middle. The model reads top-down - if skip conditions come after instructions, it may execute before discovering it should skip.

### Guard clauses for idempotency

If a skill might run twice (after compaction, by accident), check existing state before overwriting. Specify the merge strategy: "keep the more detailed version, union the lists, keep the more specific value."

### Priority mode

Every multi-step skill should have a fast path for constrained situations:
1. **When to use it** (concrete triggers: "context below 20%", "session under 15 min")
2. **Which steps are essential** (never skip) vs deferrable
3. **What catches deferred work later** (next session, staleness check)

### Degrees of freedom match fragility

- **Low freedom** (exact scripts, specific commands): Use when errors are catastrophic. Wrong deploy config breaks production.
- **Medium freedom** (pseudocode, parameterized patterns): Use when a preferred approach exists but details vary.
- **High freedom** (text guidelines, heuristics): Use when multiple approaches are valid. Can't be scripted, depends on context.

The test: "If someone follows these instructions incorrectly, how bad is the outcome?" Catastrophic = low freedom. Suboptimal but recoverable = high freedom.

### Ordered by recoverability

Write the most valuable artifact first. If the session crashes mid-skill, partial execution should still produce the most valuable output.

### Cross-references between steps

When a later step needs output from an earlier one, say so explicitly: "**Save the commit hashes** - you'll need them for step 3." Don't rely on the AI carrying forward context.

</details>

---

## 3. Token Efficiency

<details>
<summary>3. Token Efficiency</summary>

### Progressive disclosure - three loading levels

1. **Metadata** (name + description) - always in agent context (~100 words). This is the trigger mechanism.
2. **SKILL.md body** - loaded when skill triggers. See size budget below.
3. **Bundled resources** (scripts/, references/, assets/) - loaded on demand. Unlimited size.

### Size budget

| Lines | Guidance |
|-------|----------|
| < 200 | Lightweight, no concern |
| 200-500 | Every section should earn its place |
| 500+ | Push detail into `references/` files with pointers about when to read them |

### Conditional reads save the most tokens

"**Only read config.json if** this task modifies configuration" saves thousands of tokens per invocation. Always ask: does this step need this file for THIS task, or just in general?

### Collapsible sections in markdown

For skills over ~100 lines, use HTML `<details>`/`<summary>` for sections the agent may not need every invocation. `## Heading` stays above `<details>`. `<summary>` text matches heading.

Never collapse: Quick Nav tables, intros, sections under 10 lines.
Always collapse: Sections over 15 lines, implementation details, reference tables.

</details>

---

## 4. Description Optimization

<details>
<summary>4. Description Optimization</summary>

### Descriptions are the trigger mechanism

The agent decides whether to consult a skill based solely on name + description. The body is only read after triggering. All "when to use" info goes in the description, not the body.

### Make descriptions pushy

Agents tend to undertrigger - they won't invoke skills when they should. Instead of "How to deploy to a server", write "Use this skill when deploying, updating, restarting, or checking status of services, even if the user doesn't mention 'deploy'."

### Description constraints

- Max 1024 characters
- No angle brackets (interferes with XML parsing)
- Kebab-case name, max 64 characters

### Testing trigger accuracy

Create 20 realistic eval queries: ~10 should-trigger + ~10 should-not-trigger. The most valuable negatives are near-misses - queries that share keywords but need something different.

Bad query: `"Create a chart"` (too generic)
Good query: `"my boss sent this xlsx and wants a profit margin column added"` (realistic, specific)

### Explain why, not just what

When given reasoning, models generalize beyond rote instructions. ALL-CAPS ALWAYS/NEVER is a yellow flag - it usually means the instruction hasn't earned compliance through understanding. Explain why it matters.

</details>
