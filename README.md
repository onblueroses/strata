# strata

Markdown files and shell scripts that configure AI coding agents. 52 skills, 13 hooks.

I use Claude Code for everything. Over time, my setup accumulated skills (procedural workflows the agent follows), hooks (shell scripts that fire at lifecycle events), and patterns for structuring projects so agents don't get lost. strata is that setup, extracted and genericized.

There's no code to install. You clone the repo, paste SETUP.md into your agent, and it configures itself for your project.

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

Open your AI agent. Paste the contents of [`SETUP.md`](SETUP.md).

The agent figures out your project type, picks relevant skills, wires up hooks, and writes a CLAUDE.md. No build step.

## What's Inside

```
skills/       52 workflows in plain markdown
hooks/        13 shell scripts (quality gates, context management, session lifecycle)
examples/     CLAUDE.md pattern, settings.json template, reference docs
SETUP.md      Bootstrap prompt - paste this into your agent
cli/          Rust CLI for structural validation (optional, you don't need it)
```

## Skills

Each skill is a markdown file the agent reads and executes. Steps, quality checks, anti-patterns, trigger conditions.

| Tier | Count | Examples |
|------|-------|---------|
| **Core** | 24 | review, verify, commit, debug, test, plan, spec, deploy, research |
| **Domain** | 21 | frontend-design, react, n8n (7), obsidian (4), security-review |
| **Meta** | 7 | skill-creator, autooptimize, visualize, context-resume |

The bootstrap prompt picks domain skills based on what it detects in your project. Full list: [`skills/INDEX.md`](skills/INDEX.md)

## Hooks

Shell scripts that fire at agent lifecycle events. See [`examples/settings.json`](examples/settings.json) for wiring.

| Hook | Event | What it does |
|------|-------|-------------|
| `quality-lint-on-write` | PostToolUse | Runs ruff/eslint after every edit |
| `gate-verify` | Stop | Blocks session end until verification passes |
| `gate-codex-pre-push` | PreToolUse | Runs code review before git push |
| `context-pre-compaction-save` | PreCompact | Saves state before context compaction |
| `observe-track-edits` | PostToolUse | Logs which files were edited |

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

This is the structural model I use. When a project has these five things, agents stop wasting tokens on orientation:

1. **Constitution** (`PROJECT.md`) - what the project is, what it can't do
2. **Global Index** (`INDEX.md`) - flat list of every file with one-line descriptions
3. **Domain Boundaries** (`RULES.md` per directory) - what goes where
4. **Crosslink Mesh** (See Also sections) - links between related files
5. **Per-File Descriptions** (frontmatter/headings) - lets agents find files without opening them

<details>
<summary>Why this matters</summary>

Agents re-read the same files every session, lose state when context compacts, and drift toward inconsistent patterns when multiple instances touch the same project. These five layers give them something stable to orient against.

Some research backing:
- ETH Zurich (2026) found that bad context files actually hurt agent performance and increase cost by 20%+. Quality matters more than having something.
- The "Codified Context" paper (2026) showed single-file manifests don't scale past ~100k lines. You need tiered structure.
- Linux Foundation's AGENTS.md study got 28.6% faster agents, but results were mixed overall because structure matters more than just having a file.

</details>

## Optional: Rust CLI

There's also a Rust CLI in `cli/` if you want programmatic validation, context generation, or skill evaluation. I built it before the text-first pivot and it still works. You don't need it.

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

Claude Code (primary), OpenCode, Pi, or anything that reads markdown.

## License

MIT
