# Skill Creator

Build skills that AI agents can execute reliably.

## Step 1: Define the skill

Before writing anything:

1. **What task does this skill automate?** (one sentence)
2. **What triggers it?** Auto-trigger conditions or manual invocation only?
3. **What does "done" look like?** Observable output or state change.
4. **What can go wrong?** Common failure modes and edge cases.

## Step 2: Write the skill file

Create `skills/[skill-name]/SKILL.md`:

```markdown
---
name: skill-name
tier: core | domain | meta
description: >
  One paragraph. First sentence: what it does. Remaining: when to use it,
  what it prevents. Include auto-trigger conditions if applicable.
---

# Skill Name

[One-line purpose statement]

## Steps

[Numbered steps with concrete actions. Each step should be independently executable.]

## Anti-Examples

| Bad | Why | Better |
|-----|-----|--------|

## Quality Self-Check

[Numbered checklist the agent runs before reporting "done"]
```

## Step 3: Description optimization

The description is the most important part - it determines whether agents invoke the skill.

**Rules:**
- First sentence: what the skill DOES (verb phrase)
- Second sentence: WHEN to use it (trigger conditions)
- Third sentence: what it PREVENTS (cost of not using it)
- Include `Auto-trigger:` or `Manual:` at the end
- Under 280 characters total for the trigger sentence

**Test:** Read only the description. Would an agent correctly decide to invoke this skill
for the right tasks and NOT invoke it for wrong tasks?

## Step 4: Instruction quality

Each step in the skill must be:

- **Concrete** - "Run `strata check`" not "Verify the project structure"
- **Observable** - Agent can verify it completed ("output contains X", "file exists at Y")
- **Idempotent** - Running the step twice doesn't break anything
- **Ordered correctly** - Dependencies between steps are explicit

**Anti-pattern to avoid:** Steps that say "check if X" without saying what to do if X is true or false.
Always include both branches.

## Step 5: Test the skill

1. Invoke the skill on a real project
2. Check: did the agent follow the steps in order?
3. Check: did the agent produce the expected output?
4. Check: did the agent handle edge cases (missing files, empty data)?

## Eval System

For skills that need performance measurement:

```bash
strata skill eval [skill-name]           # Run eval set
strata skill eval [skill-name] --report  # Generate HTML report
```

Create eval sets in `skills/[skill-name]/eval.json`:

```json
{
  "queries": [
    {
      "input": "Description of the scenario",
      "expected": "What the skill should do",
      "criteria": ["Criterion 1", "Criterion 2"]
    }
  ]
}
```

## Anti-Examples

| Bad | Why | Better |
|-----|-----|--------|
| "Do the thing correctly" as a step | Not concrete, not observable | "Run `npm test` - expect 0 failures" |
| Description: "A useful skill" | Doesn't help agents decide when to invoke | "Pre-commit code review. Checks staged changes against project constraints." |
| 15 steps in one skill | Too complex, agents lose track | Split into multiple skills or phases of 4-6 steps |
| No anti-examples section | Agents repeat the same mistakes | Include 3-5 concrete bad/better pairs |
| No quality self-check | No verification before reporting done | Always end with a checklist |

## Quality Self-Check

1. Description passes the "would an agent invoke this correctly?" test?
2. Every step is concrete, observable, and idempotent?
3. Anti-examples cover the most common failure modes?
4. Quality self-check covers the skill's key success criteria?
5. Tier is correctly assigned (core/domain/meta)?
