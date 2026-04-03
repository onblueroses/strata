# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- `miette` diagnostics with diagnostic codes, source spans, and actionable help text
- SARIF v2.1.0 output (`strata lint --format sarif`) for GitHub Code Scanning and VS Code
- Snapshot tests with `insta` for JSON and SARIF output
- Parallel file scanning with `rayon`
- Source span tracking for lint diagnostics (`file:line:col`)
- Project type detection (Rust, JS/TS, Python, Go, Next.js, SvelteKit, etc.)
- `minijinja` template engine replacing `{{KEY}}` string replacement
- `strata diff` - show what would change on regeneration
- `strata update` - selectively regenerate stale context files
- `strata watch` - file watching with configurable debounce
- `strata completions` - shell completions via `clap_complete` (bash, zsh, fish, powershell)
- Custom lint rules via `[[custom_rules]]` in strata.toml (4 check types)
- Monorepo workspace support with per-member config and aggregated results
- Temporal lint rules: `stale-dates` and `waiting-markers` with configurable thresholds
- Skill eval system (`strata skill eval|optimize|eval-set init`) with parallel runner, train/test split, HTML reports
- 48 skill templates across three tiers: 23 core (Standard+), 7 meta (Full), 18 domain (Full, project-type-matched)
- Enforcement hooks on by default (`[hooks] enforce = true`)
- Getting-started reference doc in Full preset
- 3 new skill templates: `evaluate`, `mycelium`, `xbow`
- 19 updated skill templates from live use
- `.gitattributes` for consistent line endings

### Changed
- Repositioned as "agent harness layer"
- Lint engine: 6 to 20 built-in rules plus user-defined custom rules
- Agent targets narrowed to Claude Code, OpenCode, Pi (removed Generic, Cursor, Copilot)
- CLI expanded from 9 to 13 subcommands
- Standard preset: 23 core skills; Full preset: 48 total (was 2)

## [0.2.0] - 2026-03-04

### Added
- **Memory system** - context generation with character budget enforcement
  - `strata generate` - tiered context generation (project overview + per-domain files)
  - `strata fix --index` - full INDEX.md regeneration
  - `skills/` directory scaffolding and validation (SKILL.md frontmatter)
  - 5 new lint rules: `context-budget`, `skill-structure`, `context-freshness`, `memory-budget`, `memory-structure`
  - 2 new config sections: `[context]` (char budgets), `[memory]` (memory files + budget)
- **Workspace manager expansion** - full AI-agent workspace management
  - `strata init --preset minimal|standard|full` - tiered project scaffolding
    - minimal: structure only (PROJECT.md, INDEX.md, domains)
    - standard: +lifecycle hooks, starter skills (review/commit), MEMORY.md
    - full: +specs directory, sessions directory
  - `strata spec new|list|status|complete` - implementation spec lifecycle management
    - Specs track status, session ownership, phases, steps, decisions
    - `>> Current Step` section for post-compaction recovery
  - `strata session start|list|save` - session tracking with daily notes and context saves
    - Session IDs via timestamp hash (no uuid dependency)
    - `.strata/current-session` marker for active session
  - `strata generate --target claude|cursor|copilot` - agent-specific output generation
    - Claude: writes `CLAUDE.md`
    - Cursor: writes `.cursorrules`
    - Copilot: writes `.github/copilot-instructions.md`
    - Generic (default): writes `.strata/context.md` only
  - `strata generate --skills` - install starter skill templates
  - 7 new lint rules: `hook-structure`, `hook-budget`, `spec-structure`, `spec-stale`, `spec-ownership`, `session-structure`, `starter-skills`
  - 4 new config sections: `[hooks]`, `[specs]`, `[sessions]`, `[targets]`
- 10 new embedded templates (3 hooks, 1 spec, 2 skills, 1 memory, 3 targets)
- `is_meta_file()` now covers entire `.strata/` subtree

### Changed
- `strata generate` now accepts `--target` and `--skills` flags
- Lint engine expanded from 6 to 18 rules (12 new)

## [0.1.0] - 2026-02-25

### Added
- `strata init` - Interactive project scaffolding with five-layer architecture
- `strata check` - Structural integrity validation (pass/fail)
- `strata lint` - Quality diagnostics with 6 rules (Error/Warning/Info severity)
- `strata fix` - Auto-repair for common structural issues
- `strata install-hooks` - Git pre-commit hook for drift prevention
- Template system with embedded templates (no runtime file dependencies)
- Configuration via `strata.toml`
