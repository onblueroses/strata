# Architecture

strata is a text-first agent harness. The value is battle-tested instructions
that configure AI coding agents - not compiled tooling. An agent reads these
files and configures itself for your project.

## Five Layers

Every well-structured AI workspace needs five layers of navigation context.
strata provides patterns and reference material for each:

### 1. Constitution (PROJECT.md)

The project's non-negotiable constraints. What this project is, what it must
never do, what standards apply. Agents read this first and treat it as law.

### 2. Global Index (INDEX.md)

Flat map of every important file with a one-line description. Agents use this
to navigate without scanning the filesystem. Stale indexes waste tokens;
missing indexes force exploration.

### 3. Domain Boundaries (RULES.md per directory)

What belongs in each directory and what doesn't. Prevents agents from putting
auth logic in the UI layer or test utilities in production code.

### 4. Crosslink Mesh (See Also sections)

Lateral references between related files. When an agent reads the auth
middleware, it should know about the JWT utility, the user model, and the
auth tests without searching.

### 5. Per-File Descriptions (frontmatter/headings)

One-line descriptions that enable retrieval without loading full file content.
The difference between an agent reading 50 files to find the right one and
going directly to it.

## Lifecycle Hooks

Hooks are shell scripts that fire at specific points in the agent session.
They enforce quality gates and preserve context automatically.

| Event | When it fires | Use for |
|-------|--------------|---------|
| PreToolUse | Before a tool runs | Blocking gates (search guards, push reviews) |
| PostToolUse | After a tool runs | Quality checks (lint, CRLF), tracking (edits, events) |
| UserPromptSubmit | When user sends a message | Context nudges, memory hints |
| PreCompact | Before context compaction | State preservation |
| SessionStart | When session begins | Cleanup, environment checks |
| Stop | When session ends | Verification gates, sync |
| Notification | On notifications | Alerting |

See `hooks/` for 13 ready-to-use hooks and `examples/settings.json` for
wiring them into Claude Code's settings.

## Skills

Skills are markdown files containing procedural knowledge that agents execute.
Each skill is a self-contained workflow with:

- **Description** with trigger conditions (when to auto-invoke)
- **Steps** with concrete, observable actions
- **Anti-patterns** showing what to avoid
- **Quality checks** for self-verification

Skills live in `skills/` as plain markdown. No compilation, no runtime - the
agent reads the file and follows the instructions.

### Skill Tiers

| Tier | Count | Purpose |
|------|-------|---------|
| Core | 23 | Universal development workflows (review, verify, commit, test, debug, plan) |
| Meta | 7 | Tooling skills (skill-creator, autooptimize, visualize) |
| Domain | 21 | Project-type-specific (frontend, n8n, security, obsidian) |

See `skills/INDEX.md` for the full categorized list.

## The Bootstrap Pattern

`SETUP.md` is the single entry point. An agent reads it and configures the
full harness for any project:

1. Detect project type and stack
2. Select relevant skills from the catalog
3. Wire hooks into settings
4. Generate a project CLAUDE.md
5. Set up memory structure

The bootstrap prompt handles all of this through text instructions - no CLI
required.

## Optional: Rust CLI

The `cli/` directory contains a Rust CLI that implements structural validation,
context generation, and skill evaluation programmatically. It is entirely
optional - the text layer works without it.

```bash
cd cli && cargo install --path .
strata check    # validate structure
strata lint     # quality diagnostics
strata generate # generate context files
```

## Excluded Hook Patterns

Seven hooks from the author's private setup are not included because they are
deeply personal, but the patterns are worth knowing:

| Pattern | What it does | Build your own with |
|---------|-------------|-------------------|
| Daily notes | Creates structured session journal entries | JSON file per session in a notes directory |
| Knowledge sync | Auto-commits knowledge base on session end | `git add -A && git commit` in a Stop hook |
| Memory routing | Surfaces relevant memories by keyword match | Grep memory file descriptions against prompt |
| Doc routing | Injects relevant reference docs per prompt | Match prompt keywords against doc metadata |
| Verify cleanup | Clears stale verification markers on start | Delete marker files in SessionStart hook |
| Departure notes | Writes per-file context when session ends abruptly | Git notes or sidecar files for edited paths |
| Unpushed check | Warns about uncommitted work across repos | `git status` across project directories in Stop hook |
