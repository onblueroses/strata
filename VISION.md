# strata - Vision

> Battle-tested agent harness. Text over tooling.

## Problem

AI coding agents waste tokens navigating unfamiliar codebases. They re-read
the same files each session, lose state at context boundaries, and drift toward
inconsistent conventions when multiple agents touch the same project.

Context files (CLAUDE.md, AGENTS.md) help, but they are freeform, unvalidated,
and rot silently. Most setups are either too minimal (a few paragraphs of
instructions) or too rigid (compiled tooling that breaks when the model
gets smarter).

## Research Findings

- **ETH Zurich (Feb 2026)**: Naive context files can reduce agent performance
  and increase cost 20%+. Quality and relevance matter more than quantity.
- **"Codified Context" paper (Feb 2026)**: Single-file manifests don't scale.
  Three-tier memory (hot/warm/cold) needed for 100k+ line projects.
- **AGENTS.md (Linux Foundation)**: 28.6% faster agents in one study, but
  mixed results overall - structure matters more than presence.

## Thesis

Frontier models are smart enough that the bottleneck is not code generation -
it is the quality of instructions they receive. A well-written markdown file
beats a compiled tool because:

1. **Text is universal.** Any agent can read markdown. Compiled tools lock you
   into one ecosystem.
2. **Text is auditable.** You can read every instruction the agent follows.
   Compiled tools are black boxes.
3. **Text evolves with models.** When models get smarter, you update a sentence.
   Compiled tools need code changes, releases, and version management.
4. **Text compounds.** Battle-tested instructions from hundreds of hours of
   real agent sessions are more valuable than any scaffolding tool.

## What strata Is

strata is a curated collection of:

- **51 skills** - procedural knowledge for development workflows (review,
  verify, commit, debug, deploy, security, and more)
- **13 hooks** - shell scripts that enforce quality gates and preserve context
  automatically
- **Reference docs** - code quality principles, skill design guidelines
- **Examples** - annotated CLAUDE.md pattern, settings.json hook wiring
- **Architecture** - the five-layer navigation model as documentation
- **A bootstrap prompt** - single entry point that configures everything

The optional Rust CLI in `cli/` adds structural validation and context
generation for power users. It is not required.

## What strata Is Not

- Not a framework with runtime dependencies
- Not a code generator
- Not specific to one AI agent (works with Claude Code, OpenCode, Pi, or any
  agent that reads markdown)
- Not a replacement for your project's documentation - it is the layer that
  makes your documentation navigable to agents

## Distribution

Clone the repo, read SETUP.md, and let the bootstrap prompt configure your
project. Remove skills you don't need. Add your own. The repo is the product.

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Format | Plain markdown + shell | Universal, auditable, no runtime dependencies |
| Entry point | Single bootstrap prompt (SETUP.md) | One file to read, agent does the rest |
| CLI | Optional, in subdirectory | Power users get validation; text users lose nothing |
| Skills | Plain .md, no frontmatter | Zero preprocessing, any agent can read them |
| Hooks | Shell scripts with env vars | Portable across Linux/macOS, configurable per project |
| Distribution | Clone and prune | Users see everything, remove what they don't need |

## Future

- MCP server mode for the CLI (task-aware context loading)
- Community skill contributions with quality bar
- Multi-agent coordination patterns
- Project-type-specific starter kits (detected from SETUP.md bootstrap)

---

*Living document. Updated as the project evolves.*
