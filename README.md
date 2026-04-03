# strata

**Agent harness for AI coding tools.** 51 skills, 13 hooks, one bootstrap prompt.

Not a framework. Not a CLI. A curated collection of markdown and shell scripts - refined over hundreds of hours of real AI-assisted development - that make your coding agent work the way an experienced practitioner would.

> Frontier models are smart enough that the bottleneck is not code generation. It is the quality of instructions they receive.

## Quick Start

```
git clone <this-repo>
```

Open your AI agent. Paste the contents of [`SETUP.md`](SETUP.md). Done.

The agent detects your project, selects skills, wires hooks, generates a CLAUDE.md. No install, no build, no dependencies.

## What's Inside

```
skills/           51 procedural workflows in plain markdown
hooks/            13 shell scripts for quality gates and context management
reference/        Code quality principles, skill design guide
examples/         Annotated CLAUDE.md pattern, settings.json template
SETUP.md          Bootstrap prompt (the entry point)
ARCHITECTURE.md   Five-layer navigation model
cli/              Optional Rust CLI for structural validation
```

## Skills

Plain markdown files the agent reads and follows. Each one: steps, quality checks, anti-patterns, trigger conditions.

| | Selected skills |
|-|----------------|
| **Core** (23) | review, verify, commit, debug, test, plan, spec, explore, end, pickup, deploy, research, deep-understand, security, optimize, pr, release, status, tidy, reconcile, trace, learn, get-to-work |
| **Domain** (21) | frontend-design, react-best-practices, ship, security-review, n8n (7 skills), obsidian (4 skills), copywriting, browser-automation, mobile-preview, latex-presentation |
| **Meta** (7) | skill-creator, autooptimize, visualize, context-resume, context-save, evaluate, browser-automation |

The bootstrap prompt selects domain skills based on your project type. See [`skills/INDEX.md`](skills/INDEX.md) for descriptions.

## Hooks

Shell scripts that fire at agent lifecycle events. Wire them via [`examples/settings.json`](examples/settings.json).

| Hook | Event | What it does |
|------|-------|-------------|
| `quality-lint-on-write` | PostToolUse | Runs ruff/eslint after every edit |
| `quality-crlf-check` | PostToolUse | Catches Windows line endings |
| `quality-search-path-guard` | PreToolUse | Blocks broad home-dir searches |
| `gate-codex-pre-push` | PreToolUse | Code review before git push |
| `gate-verify` | Stop | Enforces verification before session end |
| `context-nudge` | UserPromptSubmit | Reminds to save context |
| `context-suggest-compact` | PostToolUse | Suggests compaction at thresholds |
| `context-pre-compaction-save` | PreCompact | Auto-saves state before compaction |
| `observe-track-edits` | PostToolUse | Tracks edited files per session |
| `observe-track-session-events` | PostToolUse | JSONL event log |
| `observe-track-skill-runs` | PostToolUse | Skill invocation tracking |
| `session-check-dev-servers` | SessionStart | Warns about runaway dev servers |
| `allow-claude-dir-edits` | PreToolUse | Auto-approves .claude/ edits |

## Five-Layer Navigation

The structural model behind strata. Any project that implements these gives AI agents reliable orientation:

1. **Constitution** - `PROJECT.md` - purpose, constraints, non-negotiables
2. **Global Index** - `INDEX.md` - flat map of every file
3. **Domain Boundaries** - `RULES.md` per directory - what belongs where
4. **Crosslink Mesh** - See Also sections - lateral navigation
5. **Per-File Descriptions** - frontmatter/headings - retrieval without loading

Details in [`ARCHITECTURE.md`](ARCHITECTURE.md).

## Optional: Rust CLI

`cli/` contains a Rust CLI for structural validation, context generation, and skill evaluation. Entirely optional - the text layer works without it.

```bash
cd cli && cargo install --path .
strata check      # structural integrity
strata lint       # 20 quality diagnostics
strata generate   # context files for claude-code/opencode/pi
```

## Works With

**Claude Code** (primary) / **OpenCode** / **Pi** / any agent that reads markdown

## License

MIT
