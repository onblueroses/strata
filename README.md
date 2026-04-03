# strata

Battle-tested agent harness for AI coding tools. 51 skills, 13 hooks,
one bootstrap prompt.

strata is not a framework or a CLI you install. It is a collection of
markdown files and shell scripts, refined over hundreds of hours of real
AI-assisted development, that configure your coding agent to work the way
an experienced practitioner would.

The thesis: frontier models are smart enough that the bottleneck is not
code generation - it is the quality of instructions they receive. A
well-written skill file beats a compiled tool every time.

## What's Inside

```
skills/         51 plain markdown skills (review, verify, commit, debug, ...)
hooks/          13 shell scripts (lint gates, context management, session lifecycle)
reference/      Code quality principles, skill design guide, getting started
examples/       Annotated CLAUDE.md pattern, settings.json hook wiring template
SETUP.md        Bootstrap prompt - the single entry point
ARCHITECTURE.md Five-layer navigation model + harness design
cli/            Optional Rust CLI for structural validation
```

## Quick Start

1. Clone this repo
2. Open your AI agent (Claude Code, or any agent that reads markdown)
3. Paste `SETUP.md` into the first message
4. The agent detects your project type, selects skills, wires hooks, and
   generates a CLAUDE.md

That's it. No installation, no build step, no dependencies.

## Skills

Skills are procedural knowledge in plain markdown. Each one is a self-contained
workflow the agent follows - steps, quality checks, anti-patterns.

<details>
<summary>Core Skills (23)</summary>

| Skill | What it does |
|-------|-------------|
| review | Pre-commit code review against project constraints |
| verify | Post-implementation integrity check |
| commit | Smart multi-commit grouping |
| debug | Structured debugging methodology |
| test | Test-first development workflow |
| plan | Implementation planning |
| spec | Specs that survive context compaction |
| explore | Codebase familiarization |
| end | Session closure with context preservation |
| pickup | Load project context quickly |
| pr | Pull request creation |
| release | Release workflow |
| security | Security-focused code review |
| optimize | Performance optimization |
| deploy | Deployment workflow |
| status | System health check |
| tidy | Knowledge base hygiene |
| research | Adaptive research |
| trace | Entity history across sessions |
| learn | Capture patterns mid-session |
| reconcile | Documentation drift detection |
| get-to-work | Autonomous maintenance |
| deep-understand | Deep codebase familiarization |

</details>

<details>
<summary>Domain Skills (21)</summary>

Project-type-specific. The bootstrap prompt selects relevant ones automatically.

Frontend, React/Next.js, security review, n8n workflows (7 skills),
Obsidian vault (4 skills), copywriting, browser automation, mobile preview,
LaTeX presentations.

See `skills/INDEX.md` for the full list.

</details>

<details>
<summary>Meta Skills (7)</summary>

| Skill | What it does |
|-------|-------------|
| skill-creator | Create and optimize new skills |
| autooptimize | Iterative skill improvement |
| visualize | SVG diagrams and data visualization |
| context-resume | Post-compaction recovery |
| context-save | Pre-compaction state preservation |
| evaluate | Deep evaluation of repos/articles/content |
| browser-automation | Browser interaction for agents |

</details>

## Hooks

Shell scripts that fire at specific points in the agent session. Wire them
into your agent's settings (see `examples/settings.json`).

<details>
<summary>All 13 Hooks</summary>

**Quality gates (blocking):**
- `quality-lint-on-write.sh` - runs ruff/eslint after every edit
- `quality-crlf-check.sh` - catches Windows line endings
- `quality-search-path-guard.sh` - prevents broad home-dir searches
- `gate-codex-pre-push.sh` - code review before git push
- `gate-verify.sh` - enforces /verify before session end

**Context management (advisory):**
- `context-nudge.sh` - reminds to save context before compaction
- `context-suggest-compact.sh` - suggests compaction at thresholds
- `context-pre-compaction-save.sh` - auto-saves state before compaction

**Observability (advisory):**
- `observe-track-edits.sh` - tracks edited files per session
- `observe-track-session-events.sh` - JSONL event log
- `observe-track-skill-runs.sh` - skill invocation tracking

**Session lifecycle:**
- `session-check-dev-servers.sh` - warns about runaway dev servers
- `allow-claude-dir-edits.sh` - auto-approves .claude/ directory edits

</details>

## The Five Layers

strata's navigation model. Any project that implements these five layers
gives AI agents reliable orientation:

1. **Constitution** (PROJECT.md) - purpose, constraints, non-negotiables
2. **Global Index** (INDEX.md) - flat map of every file
3. **Domain Boundaries** (RULES.md per directory) - what belongs where
4. **Crosslink Mesh** (See Also sections) - lateral navigation
5. **Per-File Descriptions** (frontmatter/headings) - retrieval without loading

See `ARCHITECTURE.md` for full details.

## Optional: Rust CLI

The `cli/` directory contains a Rust CLI that implements structural validation,
context generation, and skill evaluation programmatically. Entirely optional.

```bash
cd cli && cargo install --path .
strata check      # structural integrity
strata lint       # 20 quality diagnostics
strata generate   # generate context files
strata fix        # auto-repair issues
```

See `cli/README.md` for full CLI documentation.

## Works With

- **Claude Code** - primary target, all features supported
- **OpenCode** - skills and hooks work, target generation available
- **Pi** - skills and hooks work, target generation available
- **Any markdown-reading agent** - skills are plain text, hooks are shell

## License

MIT
