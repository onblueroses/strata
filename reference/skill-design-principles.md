<!-- keywords: skill, slash command, skill design, instruction quality, skill.md, auto-trigger, skill description, leading word, progressive disclosure, completion criteria, skill failure modes, split a skill, routing, prune the skill, write a skill -->
# Skill Design Principles

Distilled from perfecting /end across 3 iterations, 135-note quality analysis, 3 research tracks, and Anthropic's official skill-creator patterns. Apply when creating or improving any skill.

**Tooling**: The skill-creator skill at `$STRATA_HOME/skills/skill-creator/` provides automated description optimization, eval runners, grading agents, and A/B comparison. Use `/skill-creator` or ask to create/improve a skill to invoke it.

## Quick Nav

| Task | Section |
|------|---------|
| Write good skill instructions | Instruction Quality |
| Structure a skill file | Structure |
| Test/measure skill quality | Quality Assurance |
| Optimize skill token cost | Token Efficiency |
| Write skill description for triggering | Description Optimization |
| Run evals and iterate | Evaluation & Iteration |
| Understand skill architecture | Skill Architecture |

## Instruction Quality

### Anti-examples are useful - with reasoning
"DO NOT start the summary with 'In this session, we...'" prevents more failures than "Write a good summary." Listing the 3-6 most common failure modes for a skill's output is high-impact - but pair each with WHY it's bad, not just a bare prohibition. A model that understands the reasoning generalizes to novel situations; a model following rigid DON'T lists only avoids the exact cases listed. Source anti-examples from real data when possible.

### Concrete tests beat abstract rules
Bad: "The takeaway must be different from the summary."
Good: "**Test:** cover the summary with your hand and read the takeaway alone - does it teach something useful on its own?"

Give the AI a physical/mechanical test it can apply, not a judgment call it can rationalize away.

### Format templates with fill-in-the-blank patterns
Bad: "Write decisions with alternatives considered."
Good: "Formats: 'Chose X over Y because Z.' / 'Left X unchanged because Y.' / 'Deferred X because Z.'"

Multiple format templates cover more real-world cases than a single abstract instruction.

### Good/bad examples table
Side-by-side field-level comparison is the highest-impact few-shot format. 2-3 good examples + 1-2 bad ones. Bad examples should be things the AI would plausibly write, not strawmen.

### Controlled vocabularies prevent drift
When a field has a finite set of good values (tags, status codes, entity types), enumerate them. Open-ended fields drift - 69% of /end's tags were unique before adding a vocabulary, making them useless for search.

### Leading words and the two loads

The root virtue a skill chases is **predictability**: the agent taking the same *process* every run, not producing the same output; every lever below serves that. Adapted from the open-source `writing-great-skills` skill (mattpocock/skills).

Two costs trade off when placing a skill:
- **Context load**: a model-invoked skill's `description` sits in the window every turn. Pay it only when the agent, or another skill, must reach the skill autonomously.
- **Cognitive load**: a user-invoked skill (`disable-model-invocation: true`) costs zero context but makes *you* the index that must remember it exists. Cure piled-up cognitive load with a router skill that names the others.

A **leading word** is a compact concept already in the model's pretraining that the agent thinks with while running the skill (e.g. *tight*, *red*, *fog of war*, *tracer bullet*); it anchors execution in the body and invocation in the description. Collapse restatements into one pretrained word: "fast, deterministic, low-overhead" becomes a *tight* loop; "a loop you believe in" becomes the loop going *red*.

Five failure modes to diagnose against: **premature completion** (ending a step before it is genuinely done; sharpen the completion criterion before splitting), **duplication** (one meaning in more than one place), **sediment** (stale layers that accrete because adding feels safe and removing feels risky), **sprawl** (too long even when every line is live; cure with progressive disclosure), **no-op** (a line the model already obeys by default, so you pay load to say nothing).

**Completion criteria - checkable and, where it matters, exhaustive.** Each step ends on the condition that tells the agent it is done. The checkable test: can the agent tell done from not-done? "Every modified file accounted for" beats "produce a change list", because a vague criterion invites *premature completion*. A demanding criterion also drives thorough legwork whether the skill is steps or flat reference: "every rule applied" binds reference the way "every step done" binds a sequence.

### Routing reality

A skill's `Triggers on:` / `Auto-trigger when` phrasing is advisory authoring metadata, not a routing guarantee. The skill router auto-surfaces only the skills listed in its curated catalog, and it keys on the catalog's embeddings, not the literal trigger tag. For any skill outside the catalog, the description still earns its keep through the model's own skill-scan, but the router will not fire it; promote a skill into the catalog when it should auto-trigger reliably.

## Structure

<details>
<summary>Structure</summary>

### Ordered by recoverability
The most valuable artifact should be written first. If the session crashes mid-/end, the daily note (step 3) is saved. Entity reconciliation (step 4) can be recovered later. Structure steps so that partial execution still produces the most valuable output.

### Skip conditions first
Put "**Skip if** [condition]" as the first line of optional steps, not buried in the middle. The model reads top-down - if skip conditions come after the instructions, it may start executing before discovering it should skip, wasting tokens and sometimes producing side effects.

### Guard clauses for idempotency
If the skill might run twice (after compaction, by accident), check existing state before overwriting. Specify the merge strategy: "keep the more detailed summary, union decisions and outputs, keep the more specific takeaway." Without this, re-runs destroy data.

### Priority Mode with activation criteria
Every multi-step skill should have a fast path for constrained situations. Define:
1. **When to use it** (concrete triggers, not "when appropriate")
2. **Which steps are essential** (never skip) vs deferrable
3. **What catches deferred work later** (next reconcile, next session, staleness check)

### Cross-references between steps
When a later step needs output from an earlier one, say so explicitly: "**Save the commit hashes** - you'll need them for step 3's outputs field." Don't rely on the AI remembering to carry forward context.

### Degrees of freedom: match specificity to fragility

Not every part of a skill needs the same level of prescription.

- **Low freedom** (exact scripts, specific commands): Use when the operation is
  fragile and error-prone. Example: `/xbow`'s nginx directives are exact - "use
  these directives, do not improvise" - because a wrong nginx config breaks production.
- **Medium freedom** (pseudocode, parameterized patterns): Use when a preferred
  approach exists but details vary by context. Example: `/security-review`'s
  threat model step - structured process, but the specific threats depend on the codebase.
- **High freedom** (text guidelines, heuristics): Use when multiple approaches
  are valid and context determines the best one. Example: `/humanizer`'s
  "add personality" section - can't be scripted, depends on text type.

The test: "If someone follows these instructions incorrectly, how bad is the
outcome?" Catastrophic (data loss, security hole, broken deploy) = low freedom.
Suboptimal but recoverable (less polished output) = high freedom.

### The information-hierarchy ladder

A skill is built from **steps** (ordered actions in SKILL.md) and **reference** (definitions, rules, facts). Rank every piece by how immediately the agent needs it:
1. **In-skill step** - the primary tier: what the agent does, in order, each ending on a completion criterion.
2. **In-skill reference** - consulted on demand; often a legitimately flat peer-set (every rule of a review on one rung), not a smell.
3. **External reference** - pushed into a linked file behind a *context pointer*, loaded only when the pointer fires. The pointer's *wording*, not its target, decides when and how reliably the agent reaches it.

Push too little down and the top bloats; push too much and you hide material the agent needs; that tension is the whole decision. Progressive disclosure is the move down the ladder. A **branch** (a distinct way the skill gets used) is the cleanest disclosure test: inline what every branch needs, push behind a pointer what only some branches reach. Once a piece has its rung, **co-location** decides what sits beside it: keep a concept's definition, rules, and caveats under one heading so reading one part brings its neighbours.

### Granularity: when to split a skill

Each cut spends one of the two loads, so split only when the cut earns it:
- **By invocation** - split off a model-invoked skill when it has a distinct leading word that should trigger on its own, or another skill must reach it. You pay context load for the always-loaded description, so that independent reach has to be worth it.
- **By sequence** - split a run of steps when the steps still ahead tempt the agent to rush the one in front of it (*premature completion*). Keeping later steps out of view pushes more legwork onto the current one.

</details>

## Quality Assurance

### Quality self-check after the main output
Add a 3-5 point checklist that the AI verifies after writing but before moving on. Target the highest error rates. For /end: takeaway independence (60%+ overlap rate), entity completeness (19% miss rate), output descriptions, commit hashes.

### Measure from real data, not intuition
The 135-note analysis drove every /end improvement. Before optimizing a skill:
1. Look at real outputs (10+ examples)
2. Categorize failures (what goes wrong, how often)
3. Target the highest-frequency failures first
Run research agents in parallel to compile findings into a permanent reference document.

### Post-implementation review
After writing the skill, re-read it as a hostile reviewer. Check: do cross-references point to real steps? Are template placeholders replaced? Do examples match the rules? Are step numbers consistent after renumbering?

## Token Efficiency

### Conditional reads save the most tokens
"**Only read items.json if** this session produced new structured facts" saves ~2,000 tokens per entity. Always ask: does this step need to read this file for THIS session, or just in general?

### Parallel tool call hints
"Read all needed entity summaries in a single parallel tool call." The AI can parallelize, but explicitly saying so ensures it does.

### Trim rarely-used templates
A 27-line entity creation template used once a month costs tokens every session. Replace with "Model structure after existing entities in X/" - 2 lines, same outcome.

### Skill text budget
Only the description (~100 words) is always in context. The SKILL.md body loads only when the skill triggers - so body size matters for per-invocation cost, not idle cost. Budget for the SKILL.md body:
- Under 200 lines: lightweight, no concern
- 200-500 lines: moderate, every section should earn its place
- 500+ lines: push detail into `references/` files with clear pointers about when to read them
For large reference files (>300 lines), include a table of contents so the model can skip to the relevant section.

### Prune sentence by sentence

Keep each meaning in a **single source of truth**: one authoritative place, so a behaviour change is a one-place edit. Then run the no-op test on each *sentence* in isolation, not just each line: does it change behaviour versus the model's default? When a sentence fails, delete the whole sentence rather than trim words from it; most failing prose should go, not be rewritten. This is "compress, don't accumulate" at the sentence level.

## Naming & Mapping

### Naming patterns with examples
"Format: `{noun}-{verb}` or `{target}-{action}` - e.g. vault-move, api-deploy, devserver-cleanup" is far more effective than "Pick a descriptive name." The pattern + 4 examples create a strong prior.

### Explicit scope-to-entity mapping
When the skill touches a knowledge system, provide a lookup table. Don't rely on the AI inferring which entity owns which directory. Include a cross-check: "Deployed to VPS? Include `infrastructure`."

## Meta-Process

### Three-track research for critical skills
For skills used daily, invest in parallel research:
1. **Quality analysis** - Analyze real outputs for patterns and failure rates
2. **Best practices** - External research on the skill's domain (session journaling, structured output, etc.)
3. **Edge cases** - Failure modes, race conditions, data loss scenarios

Compile findings into a permanent reference document the skill can cite.

### Iterate against real data
Each iteration should fix measurable problems. "Feels better" is not a metric. "entities_touched miss rate dropped from 19% to 0%" is.

## Skill Architecture (from Anthropic's skill-creator)

<details>
<summary>Skill Architecture (from Anthropic's skill-creator)</summary>

### Progressive disclosure - three loading levels
1. **Metadata** (name + description) - always in context (~100 words). This is the trigger mechanism.
2. **SKILL.md body** - loaded when skill triggers (see "Skill text budget" above for size guidance)
3. **Bundled resources** (scripts/, references/, assets/) - loaded on demand (unlimited size)

### Progressive disclosure - collapsible sections in markdown
All skill SKILL.md files, reference docs, specs, and long project docs use HTML `<details>`/`<summary>` for collapsible sections. This is mandatory for files over ~100 lines.

**Pattern:** `## Heading` stays above `<details>`. `<summary>` text matches heading exactly.
```markdown
## Section Name

<details>
<summary>Section Name</summary>

Content here...

</details>
```

**Never collapse:** Quick Nav tables, intros, sections under 10 lines, orientation sections.
**Always collapse:** Sections over 15 lines, implementation details, appendices, task breakdowns.

**Why:** Reduces token load when the model only needs specific sections. Makes long skill files navigable. Applies to all new skills and major edits to existing ones. See global CLAUDE.md "Progressive Disclosure" section for full rules.

### Domain organization
When a skill supports multiple domains/frameworks, organize by variant in `references/`:
```
my-skill/
├── SKILL.md (workflow + selection logic)
└── references/
    ├── variant-a.md
    ├── variant-b.md
    └── variant-c.md
```
Claude reads only the relevant reference file, saving tokens.

### Description field is the primary trigger
All "when to use" info goes in the YAML frontmatter `description:` field, not in the body. Claude decides whether to consult a skill based solely on name + description. The body is only read after triggering.

**Make descriptions pushy.** Claude tends to undertrigger - it won't invoke skills when it should. Instead of "How to deploy to a VPS", write "Use this skill whenever deploying, updating, restarting, or checking status of any service on the VPS, even if the user doesn't explicitly mention 'deploy'."

Description constraints: max 1024 characters, no angle brackets, kebab-case name max 64 characters.

### Explain the why, not just the what
When given reasoning, LLMs generalize beyond rote instructions. ALL-CAPS ALWAYS/NEVER/MUST is a yellow flag - it usually means the instruction hasn't earned its compliance through understanding. Reframe: explain why it matters, and the model will follow it in novel situations too. This principle underlies every other section in this document - anti-examples with reasoning, skip conditions with justification, format templates with the problem they solve.

### Bundle repeated work as scripts
Read transcripts from test runs. If subagents consistently write the same helper script or take the same multi-step approach, that's a signal to bundle that script in `scripts/`. Write it once, reference it from SKILL.md. Saves every future invocation from reinventing the wheel.

### Keep the prompt lean
Remove instructions that aren't pulling their weight. If transcripts show the skill making the model waste time on unproductive steps, cut the parts causing that. Generalize from feedback - don't overfit to specific test cases with fiddly changes or oppressively constrictive MUSTs.

</details>

## Description Optimization (automated)

The skill-creator includes a pipeline for optimizing skill descriptions for trigger accuracy. Located at `$STRATA_HOME/skills/skill-creator/scripts/`.

### Process
1. **Create eval queries** - 20 queries: ~10 should-trigger + ~10 should-not-trigger. Must be realistic and detailed (file paths, personal context, casual speech). Focus on edge cases, not clear-cut matches.
2. **Run optimization** - `run_loop.py` splits 60/40 train/test, runs `claude -p` per query (3x for reliability), uses extended thinking to improve the description, iterates up to 5 times. Selects best by test score to prevent overfitting.
3. **Apply** - Take `best_description` from output and update SKILL.md frontmatter.

### Good vs bad eval queries
Bad (too obvious): `"Format this data"`, `"Create a chart"`
Good (realistic): `"ok so my boss just sent me this xlsx file (its in my downloads, called something like 'Q4 sales final FINAL v2.xlsx') and she wants me to add a column that shows the profit margin"`

For should-not-trigger queries, the most valuable are near-misses - queries that share keywords but actually need something different. `"Write a fibonacci function"` as a negative for a PDF skill tests nothing.

### How triggering works
Skills only trigger for tasks Claude can't easily handle on its own. Simple one-step queries may not trigger even with a perfect description. Eval queries should be substantive enough that Claude would benefit from consulting the skill.

## Evaluation & Iteration

### Eval viewer for qualitative review
`eval-viewer/generate_review.py` serves a browser-based comparison UI. Shows with-skill vs without-skill (or old vs new) outputs side by side. Use `--static <path>` for environments without a browser. Always get human eyes on outputs before revising.

### Grading beyond assertions
The grader agent (`agents/grader.md`) goes beyond pass/fail on predefined assertions:
- **Extract and verify implicit claims** from outputs (catches things assertions miss)
- **Critique the evals themselves** (flags assertions that would pass for wrong outputs)
- **Report execution metrics** (tool calls, timing, tokens)

### Blind A/B comparison
For rigorous comparison between skill versions, use the comparator agent (`agents/comparator.md`). Gives two outputs to an independent judge without revealing which is which. Prevents bias toward the newer version. Optional - human review is usually sufficient.

### Iteration loop
1. Improve the skill based on feedback (generalize, don't overfit)
2. Rerun all test cases into a new iteration directory
3. Launch viewer with `--previous-workspace` for before/after comparison
4. Repeat until feedback is all empty or no meaningful progress

### Validation
Run `quick_validate.py <skill-dir>` to check frontmatter schema, naming conventions, and description length limits before shipping.
