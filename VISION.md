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

strata encodes a five-layer navigation architecture:

1. **Constitution** (`PROJECT.md`) - Purpose, constraints, non-negotiables
2. **Global Index** (`INDEX.md`) - Flat map of every file with one-line descriptions
3. **Domain Boundaries** (`RULES.md` per folder) - What belongs here, what doesn't
4. **Crosslink Mesh** (See Also sections) - Lateral navigation between related files
5. **Per-File Descriptions** (frontmatter/headings) - Retrieval without loading full content

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

### Phase 0: Foundation

Fix false positives, modernize internals, make strata pleasant to use on real projects.

| Step | Summary |
|------|---------|
| 0.1 | Replace `walkdir`+`globset` with `ignore` crate (gitignore-aware, parallel-ready) |
| 0.2 | Fix link resolution (wiki-name mode, implicit .md, URL path filtering, code block skipping) |
| 0.3 | Configurable `scan_extensions` in strata.toml |
| 0.4 | Switch to `miette` for rich error diagnostics with source spans |
| 0.5 | Add SARIF v2.1.0 output (`strata lint --format sarif`) |
| 0.6 | Snapshot tests with `insta` + `insta-cmd` |
| 0.7 | Parallel scanning with `rayon` |

### Phase 1: Smart Scaffold (`strata generate`)

Generate project-level context files (CLAUDE.md, AGENTS.md, .cursorrules) from strata's 5-layer structure. Preserves human edits on re-generation.

| Step | Summary |
|------|---------|
| 1.1 | Project type detection (Rust, JS/TS, Python, Go, frameworks) |
| 1.2 | Template engine upgrade (conditional sections, loops, human-edit preservation via markers) |
| 1.3 | `strata generate` command (--target claude/agents/cursor/all) |
| 1.4 | `strata diff` command (show changes since last generation) |
| 1.5 | Freshness tracking (`.strata/state.json`, context-freshness lint rule) |

### Phase 2: Recursive Improvement

strata gets smarter over time by watching project evolution and suggesting structural updates.

| Step | Summary |
|------|---------|
| 2.1 | `strata watch` (file watching with `notify`, streaming diagnostics) |
| 2.2 | `strata update` (re-analyze + update generated files, preserve human edits) |
| 2.3 | Git-aware freshness (track last-verified by mtime/git log) |
| 2.4 | Incremental scanning (cache by path+mtime+content_hash, `blake3`) |

### Phase 3: Advanced Features

| Step | Summary |
|------|---------|
| 3.1 | Custom lint rules (TOML-driven pattern/condition/message) |
| 3.2 | Workspace support (monorepo, per-member INDEX/RULES, shared PROJECT) |
| 3.3 | MCP server mode (`strata serve`, task-aware context loading, tiered hot/warm/cold) |
| 3.4 | Shell completions (`clap_complete`) |

---

## Architecture Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| File walker | `ignore` crate | gitignore-aware, parallel-ready, BurntSushi quality |
| Error display | `miette` | Source spans, colored output, actionable help text |
| Output colors | Keep `console` | Works fine, migration is cosmetic |
| Template engine | Marker-based (then `minijinja`) | Conditional sections + human-edit preservation |
| Structured output | SARIF v2.1.0 | Industry standard, VS Code + GitHub Actions |
| Parallel scanning | `rayon` | Standard for data parallelism, deterministic with sort |
| Snapshot testing | `insta` + `insta-cmd` | De facto standard, interactive review |
| Config format | TOML | Rust ecosystem standard, already in use |
| Content hashing | `blake3` | SIMD-accelerated, 3x faster than SHA-256 |
| File watching | `notify` v8 | Cross-platform, proven, debounced |
| Link mode | Config-driven (`path` vs `name`) | Code projects use paths, vaults use filename matching |
| Generation markers | `<!-- strata:begin:X -->` | Works in markdown, invisible rendered |
| MCP | Separate feature flag | Keep core CLI simple, MCP is additive |

---

*Living document. Updated as the project evolves.*
