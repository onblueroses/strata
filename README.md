# strata

**Agent harness for AI coding tools.** 51 skills, 13 hooks, one bootstrap prompt.

Not a framework. Not a CLI. A curated set of markdown files and shell scripts - refined over hundreds of hours of real AI-assisted development - that make your coding agent work the way an experienced practitioner would.

> Frontier models are smart enough that the bottleneck is not code generation. It is the quality of instructions they receive.

## Quick Nav

| I want to... | Go to |
|--------------|-------|
| Set up strata on my project | [Quick Start](#quick-start) |
| Browse available skills | [`skills/INDEX.md`](skills/INDEX.md) |
| See the hook wiring template | [`examples/settings.json`](examples/settings.json) |
| Understand the CLAUDE.md pattern | [`examples/CLAUDE.md`](examples/CLAUDE.md) |
| Use the optional Rust CLI | [Rust CLI](#optional-rust-cli) |

## Quick Start

```bash
git clone https://github.com/onblueroses/strata.git
```

Open your AI agent. Paste the contents of [`SETUP.md`](SETUP.md). Done.

The agent detects your project, selects skills, wires hooks, and generates a CLAUDE.md. No install, no build, no dependencies.

## What's Inside

```
skills/       51 procedural workflows in plain markdown
hooks/        13 shell scripts for quality gates and context management
examples/     CLAUDE.md pattern, settings.json template, reference docs
SETUP.md      Bootstrap prompt - the single entry point
cli/          Optional Rust CLI for structural validation and generation
```

## Skills

Plain markdown files the agent reads and follows. Each skill: steps, quality checks, anti-patterns, trigger conditions.

| Tier | Count | Examples |
|------|-------|---------|
| **Core** | 23 | review, verify, commit, debug, test, plan, spec, deploy, research |
| **Domain** | 21 | frontend-design, react, n8n (7), obsidian (4), security-review |
| **Meta** | 7 | skill-creator, autooptimize, visualize, context-resume |

The bootstrap prompt auto-selects domain skills based on your project type. Full list: [`skills/INDEX.md`](skills/INDEX.md)

## Hooks

Shell scripts that fire at agent lifecycle events. Wire them via [`examples/settings.json`](examples/settings.json).

| Hook | Event | What it does |
|------|-------|-------------|
| `quality-lint-on-write` | PostToolUse | Runs ruff/eslint after every edit |
| `gate-verify` | Stop | Enforces verification before session end |
| `gate-codex-pre-push` | PreToolUse | Code review before git push |
| `context-pre-compaction-save` | PreCompact | Auto-saves state before compaction |
| `observe-track-edits` | PostToolUse | Tracks edited files per session |

<details>
<summary>All 13 hooks</summary>

**Quality gates** (blocking):
`quality-lint-on-write`, `quality-crlf-check`, `quality-search-path-guard`, `gate-codex-pre-push`, `gate-verify`

**Context management** (advisory):
`context-nudge`, `context-suggest-compact`, `context-pre-compaction-save`

**Observability** (advisory):
`observe-track-edits`, `observe-track-session-events`, `observe-track-skill-runs`

**Session lifecycle**:
`session-check-dev-servers`, `allow-claude-dir-edits`

</details>

## Five-Layer Navigation

The structural model behind strata. Projects that implement these five layers give AI agents reliable orientation:

1. **Constitution** (`PROJECT.md`) - purpose, constraints, non-negotiables
2. **Global Index** (`INDEX.md`) - flat map of every file
3. **Domain Boundaries** (`RULES.md` per directory) - what belongs where
4. **Crosslink Mesh** (See Also sections) - lateral navigation
5. **Per-File Descriptions** (frontmatter/headings) - retrieval without loading

<details>
<summary>Why five layers</summary>

AI agents waste tokens navigating unfamiliar codebases. They re-read the same files each session, lose state at context boundaries, and drift toward inconsistent conventions.

Research backs this up:
- **ETH Zurich (2026)**: Naive context files can reduce agent performance and increase cost 20%+.
- **"Codified Context" paper (2026)**: Single-file manifests don't scale. Tiered memory needed for large projects.
- **AGENTS.md (Linux Foundation)**: 28.6% faster agents in one study, but structure matters more than presence.

</details>

## Optional: Rust CLI

`cli/` contains a Rust CLI for structural validation, context generation, and skill evaluation. Entirely optional - the text layer works without it.

<details>
<summary>CLI commands</summary>

```bash
cd cli && cargo install --path .

strata init           # scaffold project structure
strata check          # structural integrity validation
strata lint           # 20 quality diagnostics (+ custom rules)
strata generate       # context files for claude-code/opencode/pi
strata fix            # auto-repair issues
strata diff           # show what would change
strata update         # regenerate stale files
strata watch          # auto-regenerate on changes
strata spec           # manage implementation specs
strata session        # track agent sessions
strata skill eval     # test skill trigger accuracy
strata skill optimize # iterative skill improvement
```

</details>

## Works With

**Claude Code** (primary) / **OpenCode** / **Pi** / any agent that reads markdown

## License

MIT
