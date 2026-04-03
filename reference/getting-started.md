# Getting Started

This project uses strata for AI-navigable
project structure and workflow management. This guide explains how the system works
and how to use it effectively.

## Quick Nav

| Section | What you'll find |
|---------|-----------------|
| [Project Structure](#project-structure) | What each file and directory does |
| [Skills](#skills) | How AI skills work and how to invoke them |
| [Enforcement Hooks](#enforcement-hooks) | Automatic quality gates |
| [Memory](#memory) | Persistent knowledge across sessions |
| [Specs](#specs) | Implementation plans that survive context loss |
| [Session Lifecycle](#session-lifecycle) | How a typical work session flows |

## Project Structure

<details>
<summary>Project Structure</summary>

```
PROJECT.md          # Project constitution - purpose, domains, constraints
INDEX.md            # Global file index with descriptions
RULES.md            # Domain boundaries and ownership
MEMORY.md           # Persistent knowledge, decisions, patterns
skills/             # AI skill definitions
  review/SKILL.md   # Pre-commit code review
  verify/SKILL.md   # Post-implementation verification
  commit/SKILL.md   # Smart multi-commit
  ...
references/         # Reference documentation
  code-quality.md   # Code quality principles
  skill-design.md   # How to write good skills
.strata/
  hooks/            # Session lifecycle hooks
  specs/            # Implementation specifications (Full preset)
  sessions/         # Session notes and context saves (Full preset)
strata.toml         # Configuration
```

**Key files to read first:**
1. `PROJECT.md` - what this project is about
2. `MEMORY.md` - persistent knowledge and decisions
3. This file - how the workflow system works

</details>

## Skills

<details>
<summary>Skills</summary>

Skills are documented workflows that AI agents can execute. Each skill has:
- A **description** that tells agents when to invoke it
- **Steps** with concrete, observable actions
- **Anti-examples** showing common mistakes
- **Quality self-checks** to verify completion

### Skill tiers

| Tier | Installed with | Purpose |
|------|---------------|---------|
| **Core** | Standard, Full | Universal development workflows (review, verify, commit, test, etc.) |
| **Domain** | Full (type-matched) | Project-type-specific skills (frontend, n8n, security, etc.) |
| **Meta** | Full | Tooling and meta-skills (skill-creator, autooptimize, visualize, etc.) |

### Invoking skills

Most AI agents that support skills will auto-invoke them based on the description's
trigger conditions. You can also invoke them explicitly:

```
/review          # Pre-commit code review
/verify          # Post-implementation verification
/commit          # Smart multi-commit
/end             # Session closure
```

### Key skills to know

| Skill | When | Why |
|-------|------|-----|
| `review` | Before any commit | Catches bugs, style issues, security problems |
| `verify` | After editing files | Ensures changes are consistent and correct |
| `commit` | When committing | Groups changes logically, writes good messages |
| `end` | When finishing work | Preserves context for the next session |
| `pickup` | When starting work | Loads project context quickly |
| `spec` | For multi-file work | Creates a plan that survives context loss |

</details>

## Enforcement Hooks

<details>
<summary>Enforcement Hooks</summary>

This project uses enforcement hooks to maintain quality automatically:

### Session Stop Hook
When you end a session, the stop hook checks:
- Has `/verify` been run? (checks for `.strata/.verify-passed` marker)
- If not, it blocks the session end until verification passes.

### Pre-Commit Hook
When you commit, the pre-commit hook checks:
- Has `/review` been run? (checks for `.strata/.review-passed` marker)
- If not, it blocks the commit until review passes.

### Disabling enforcement

If enforcement is too strict for your workflow:

```toml
# strata.toml
[hooks]
enforce = false
```

This converts hard blocks to warnings. The hooks still run but won't prevent
commits or session ends.

### Hook lifecycle

```
Session start -> clean stale markers
Work -> edit files -> /verify -> /review -> git commit
Session end -> /end -> stop hook checks markers
```

</details>

## Memory

<details>
<summary>Memory</summary>

`MEMORY.md` is persistent knowledge that survives across sessions. It's loaded
into every conversation context.

### What belongs in MEMORY.md

- **Gotchas** - surprising behaviors, workarounds
- **Decisions** - architectural choices and their rationale
- **Patterns** - recurring solutions worth remembering
- **Tech** - stack details, versions, configuration
- **Conventions** - naming, error handling, test structure

### What does NOT belong in MEMORY.md

- Code snippets (they go stale)
- Ephemeral task details (use specs or session notes)
- Anything derivable from reading the code
- Duplicates of what's in README or CLAUDE.md

### Updating memory

Use the `/learn` skill to add entries mid-session. It checks for duplicates
and maintains consistent formatting.

</details>

## Specs

<details>
<summary>Specs</summary>

Specs are implementation plans that survive context window compaction. Use them
for any non-trivial work (3+ files, multiple steps).

### When to use a spec

- Multi-file changes that take more than one session
- Complex features with architectural decisions
- Work that might be interrupted by context compaction

### Spec lifecycle

```
/spec feature-name    # Create spec with plan
  ... work ...
/spec update          # Update progress
  ... work ...
/spec close           # Mark complete, run conformance check
```

### After context compaction

If your context was compacted mid-work:
1. Read the spec at `.strata/specs/[feature].md`
2. `>> Current Step` tells you where you were
3. `Decisions` are settled - don't re-debate
4. Continue from where you left off

</details>

## Session Lifecycle

<details>
<summary>Session Lifecycle</summary>

A typical work session follows this pattern:

### Starting a session
1. `/pickup` - loads project context, checks for active specs
2. Check for stale documentation
3. Start working

### During work
1. Edit files
2. `/verify` - checks your changes (MANDATORY before reporting done)
3. `/review` - pre-commit review
4. `git commit` - commit with descriptive message

### Ending a session
1. `/end` - commits work, writes session notes, updates docs
2. Stop hook verifies `/verify` was run

### The enforcement flow
```
Implement -> /verify (MANDATORY) -> /review -> git commit -> /end -> stop
```

</details>

## Configuration

<details>
<summary>Configuration</summary>

`strata.toml` controls the project configuration:

```toml
[project]
name = "my-project"
description = "What this project does"
domains = ["api", "frontend", "infra"]

[hooks]
enforce = true    # true = hard blocks, false = warnings only

[lint]
strict = false    # true = warnings become errors

[targets]
active = ["claude-code"]    # Agent targets: claude-code, opencode, pi
```

### CLI commands

```bash
strata check          # Structural integrity check
strata lint           # Quality diagnostics
strata fix            # Auto-fix safe issues
strata update         # Regenerate stale context files
strata generate       # Generate context files from project scan
strata diff           # Show what would change
```

</details>
