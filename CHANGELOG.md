# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **miette rich error diagnostics** - `StrataError` now derives `miette::Diagnostic` with diagnostic codes and actionable help text
- **SARIF v2.1.0 output** - `strata lint --format sarif` for CI integration (GitHub Code Scanning, VS Code)
- **Snapshot tests** with `insta` for JSON and SARIF lint output
- **Parallel file scanning** with `rayon` in `scan_project()`
- Diagnostic struct extended with optional `line`, `column`, `end_line`, `end_column` fields for source spans
- `LinkInfo` struct in scanner with line/column tracking for crosslinks
- Lint text output now shows `file:line:col` when span info is available
- `dead-links` lint rule now reports the line/column of the broken link
- **10 starter skills** in standard/full presets (was 2: review, commit)
  - debug, test, plan, pr, explore, release, security, optimize
  - Each follows skill-design-principles: pushy descriptions, anti-examples with reasoning, concrete mechanical tests, quality self-checks
- Skill validation enhancements in `skill-structure` lint rule:
  - Name must be kebab-case and <= 64 characters
  - Description warns if > 1024 characters (Claude Code truncation limit)
  - Body > 500 lines without `references/` subdirectory warns
- `SkillMeta` now tracks `line_count` and `has_references_dir`
- Improved starter skill templates (review, commit) with anti-example tables and concrete tests
- Enhanced `skills/README.md` template with progressive disclosure tiers and size budget guidance

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
