# strata - Vision & Roadmap

> The full AI navigation layer for software projects.

## Problem

AI coding agents waste tokens navigating unfamiliar codebases. Context files (CLAUDE.md, AGENTS.md, .cursorrules) exist but are freeform, unvalidated, tool-specific, and rot silently. No tool validates project structure for AI navigation, generates cross-tool context files from a single source of truth, or detects documentation drift.

## Research Findings

- **ETH Zurich (Feb 2026)**: Naive context files can *reduce* agent performance and increase cost 20%+. Quality and relevance matter more than quantity.
- **"Codified Context" paper (Feb 2026)**: Single-file manifests don't scale. Three-tier memory (hot/warm/cold) needed for 100k+ line projects.
- **AGENTS.md (Linux Foundation)**: 28.6% faster agents in one study, but mixed results overall.
- **Gap**: No existing tool does validation + generation + freshness tracking. Wide open.

## What strata Does

strata is an AI workspace manager. It encodes a five-layer navigation architecture and manages the full agent lifecycle:

1. **Constitution** (`PROJECT.md`) - Purpose, constraints, non-negotiables
2. **Global Index** (`INDEX.md`) - Flat map of every file with one-line descriptions
3. **Domain Boundaries** (`RULES.md` per folder) - What belongs here, what doesn't
4. **Crosslink Mesh** (See Also sections) - Lateral navigation between related files
5. **Per-File Descriptions** (frontmatter/headings) - Retrieval without loading full content

Additionally, strata manages the AI workspace:

6. **Lifecycle Hooks** (`.strata/hooks/`) - Shell scripts for session start/stop/compact events
7. **Specs** (`.strata/specs/`) - Implementation specs with phases, steps, decisions, session ownership
8. **Sessions** (`.strata/sessions/`) - Daily notes and context saves with session ID tracking
9. **Agent Targets** - Generate agent-specific files (CLAUDE.md, .cursorrules, copilot-instructions.md)
10. **Preset Tiers** - minimal (structure), standard (+hooks, skills, memory), full (+specs, sessions)

## Vision

strata becomes the full AI navigation layer: scaffold structure, generate project-level context files, validate integrity, watch for drift, and recursively improve as you work.

- **Audience**: Personal-first, then community (battle-tested before shared)
- **Identity**: Full AI navigation layer (scaffold + validate + generate + watch + smart-load)
- **CLAUDE.md**: Global CLAUDE.md untouched; strata owns project-level context generation
- **Projects**: Code-first, vault-aware (Obsidian as secondary mode)
- **Runtime**: CLI + files now; MCP server as separate feature
- **Distribution**: `cargo install` / clone repo

---

## Phased Roadmap

### Phase 0: Foundation (partially complete)

Fix false positives, modernize internals, make strata pleasant to use on real projects.

| Step | Summary | Status |
|------|---------|--------|
| 0.1 | Replace `walkdir`+`globset` with `ignore` crate (gitignore-aware, parallel-ready) | Done |
| 0.2 | Fix link resolution (wiki-name mode, implicit .md, URL path filtering, code block skipping) | Done |
| 0.3 | Configurable `scan_extensions` in strata.toml | Done |
| 0.4 | Switch to `miette` for rich error diagnostics with source spans | Done |
| 0.5 | Add SARIF v2.1.0 output (`strata lint --format sarif`) | Done |
| 0.6 | Snapshot tests with `insta` + `insta-cmd` | Done |
| 0.7 | Parallel scanning with `rayon` | Done |

### Phase 0.5: Memory System + Workspace Expansion (complete)

Added between Phase 0 and Phase 1. Context generation, budget enforcement, and full workspace management.

| Step | Summary | Status |
|------|---------|--------|
| 0.5.1 | `strata generate` - tiered context generation with char budget truncation | Done |
| 0.5.2 | `[context]` + `[memory]` config sections with budget defaults | Done |
| 0.5.3 | 5 lint rules: context-budget, skill-structure, context-freshness, memory-budget, memory-structure | Done |
| 0.5.4 | `strata fix --index` - full INDEX.md regeneration | Done |
| 0.5.5 | skills/ directory scaffolding and SKILL.md validation | Done |
| 0.5.6 | `strata init --preset minimal\|standard\|full` - tiered scaffolding | Done |
| 0.5.7 | Lifecycle hooks: `[hooks]` config, `.strata/hooks/`, hook-structure + hook-budget lint | Done |
| 0.5.8 | Specs: `strata spec new\|list\|status\|complete`, spec-structure + spec-stale + spec-ownership lint | Done |
| 0.5.9 | Sessions: `strata session start\|list\|save`, session-structure lint | Done |
| 0.5.10 | Agent targets: `strata generate --target claude\|cursor\|copilot`, starter-skills lint | Done |

### Phase 1: Smart Scaffold (complete)

Improve generation quality with project awareness, better templates, and drift detection.

| Step | Summary | Status |
|------|---------|--------|
| 1.1 | Project type detection (Rust, JS/TS, Python, Go, frameworks) | Done |
| 1.2 | Template engine upgrade (`minijinja` - conditional sections, loops) | Done |
| 1.3 | `strata diff` command (show changes since last generation) | Done |
| 1.4 | Freshness tracking (`.strata/state.json`, git-aware staleness) | Done |

### Phase 2: Recursive Improvement (mostly complete)

strata gets smarter over time by watching project evolution and suggesting structural updates.

| Step | Summary | Status |
|------|---------|--------|
| 2.1 | `strata watch` (file watching with `notify`, streaming diagnostics) | Done |
| 2.2 | `strata update` (re-analyze + update generated files, preserve human edits) | Done |
| 2.3 | Git-aware freshness (track last-verified by mtime/git log) | Done |
| 2.4 | Incremental scanning (cache by path+mtime+content_hash, `blake3`) | Next |

### Phase 3: Advanced Features

| Step | Summary |
|------|---------|
| 3.1 | Custom lint rules (TOML-driven pattern/condition/message) |
| 3.2 | Workspace support (monorepo, per-member INDEX/RULES, shared PROJECT) |
| 3.3 | MCP server mode (`strata serve`, task-aware context loading, tiered hot/warm/cold) |
| 3.4 | Shell completions (`clap_complete`) |

---

## Architecture Decisions

| Decision | Choice | Rationale | Status |
|----------|--------|-----------|--------|
| File walker | `ignore` crate | gitignore-aware, parallel-ready, BurntSushi quality | Implemented |
| Error display | `thiserror` + `miette` | Rich diagnostics with source spans, diagnostic codes, actionable help text | Implemented |
| Template engine | `{{KEY}}` marker-based (planned: `minijinja`) | Current: simple replacement. Future: conditionals, loops | Implemented (basic) |
| Config format | TOML | Rust ecosystem standard, already in use | Implemented |
| Link mode | Config-driven (`path` vs `name`) | Code projects use paths, vaults use filename matching | Implemented |
| Generation markers | `<!-- strata:generated -->` | Single marker: above = human-owned, below = regenerated | Implemented |
| Budget unit | Characters (not tokens) | Deterministic, zero-dependency, ~4 chars/token | Implemented |
| MCP | Separate feature flag | Keep core CLI simple, MCP is additive | Planned |
| Structured output | SARIF v2.1.0 (`serde-sarif`) | Industry standard, VS Code + GitHub Actions | Implemented |
| Parallel scanning | `rayon` | Standard for data parallelism in file content scanning | Implemented |
| Snapshot testing | `insta` + `insta-cmd` | De facto standard, interactive review | Implemented |
| Content hashing | `blake3` | SIMD-accelerated, 3x faster than SHA-256 | Planned |
| File watching | `notify` v8 | Cross-platform, proven, debounced | Planned |

---

*Living document. Updated as the project evolves.*
