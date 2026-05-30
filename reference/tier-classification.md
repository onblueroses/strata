<!-- keywords: tier, complexity, risk, classification, sizing, verify risk, research tier, project size -->
# Tier Classification Reference

Shared classification systems used across multiple commands. Each system maps input characteristics
to a response tier that determines agent count, model, and effort level.

Commands reference this doc instead of duplicating classification logic inline.
Override flags in each command take precedence over classification.

---

## Quick Nav

| System | Used by | Jump to |
|--------|---------|---------|
| Research Complexity | `/research` | Research Complexity |
| Project Size | `/deep-understand` | Project Size |
| Verify Risk | `/verify` | Verify Risk |

---

## Research Complexity

Classifies a research question into effort tiers. Used by `/research` Phase 0.

| Tier | Agents | Model | When |
|------|--------|-------|------|
| **Simple** | 0 (direct) | - | Single factual question, definition, quick lookup, single-source answer |
| **Moderate** | 2-3 | haiku | Comparison of 2 things, how-to with multiple approaches, best practices, problem investigation with known scope |
| **Complex** | 4-5 | sonnet | Multi-faceted comparison (3+ options), tradeoff analysis, market research, broad investigation with unknown scope |

### Classification Patterns

| Question shape | Tier |
|---|---|
| "What is X?" / "How does X work?" | Simple |
| "What version of X?" / "Does X support Y?" | Simple |
| "X vs Y" / "Should I use X or Y?" | Moderate |
| "How to do X" (multiple approaches exist) | Moderate |
| "Why does X happen?" (needs investigation) | Moderate |
| "Best X for Y" (many options) | Complex |
| "Compare X, Y, Z, W" | Complex |
| "Research X" (broad, open-ended) | Complex |

### Override Flags

- `--quick`: forces Simple regardless of assessment
- `--deep`: forces Complex regardless of assessment

---

## Project Size

Classifies a codebase by file count for familiarization effort. Used by `/deep-understand` Phase 0.

| Tier | File count | Agents | Model | Batching |
|------|-----------|--------|-------|----------|
| **Small** | < 30 | 3 | haiku | 1 batch (all at once) |
| **Medium** | 30-200 | 5 | sonnet | 2 batches (3 + 2) |
| **Large** | 200+ | 8 | sonnet | 3 batches (3 + 3 + 2) |

### Word Budget per Agent

| Tier | Max words |
|------|-----------|
| Small | 200 |
| Medium | 300 |
| Large | 400 |

### Project Type Detection

| Type | Marker files |
|------|-------------|
| Code | `package.json`, `Cargo.toml`, `pyproject.toml`, `go.mod`, `*.sln`, `Makefile`, `src/` |
| Vault/content | `.obsidian/`, majority `.md` files |
| Mixed | Both code markers and significant `.md` content |
| Concept | Argument doesn't resolve to a path - search across whole project |

---

## Verify Risk

Classifies edited files by risk for proportional verification. Used by `/verify`.

Highest-risk file determines the tier for the whole session.

| Tier | Criteria | Action |
|------|----------|--------|
| **Skip** | ALL files match safe patterns (see below) | Auto-pass. No checks. |
| **Light** | 1-3 files, same project, no cross-references, no skip-excludes | Inline checks (no subagent) |
| **Full** | 4+ files, multi-project, cross-references, settings.json/hooks edited, or files in src/lib/app/pages with siblings also edited | Opus subagent review |
| **Deep** | `--deep` flag explicitly passed | Opus subagent with extended checklist |

### Skip-Safe Patterns

All of these auto-pass (every file must match, one mismatch escalates):
- `$KB_DIR/**/*.md` - knowledge base markdown
- `$KB_DIR/**/*.json` - knowledge base data
- `$SPECS_DIR/**` - spec files
- `$STRATA_HOME/commands/**/*.md` - skill definitions
- `.claude/memory/**` - memory files
- `**/CLAUDE.md` - project instructions
- `$STRATA_HOME/reference/**/*.md` - reference docs

### Skip-Excludes (NOT safe even if in .claude/)

- `.claude/settings.json` - affects runtime behavior
- `$STRATA_HOME/hooks/**` - executable scripts
- Any `.ps1`, `.sh`, `.js`, `.ts`, `.py`, `.rs` file regardless of location

### Light Tier Checks

1. **Fresh re-read** - Read every edited file from disk
2. **Debris scan** - Grep for: orphan TODO/FIXME, stray console.log/debug, debugger, placeholder values
3. **Run tests** - If project has test runner, run it

### Override

- `--deep`: forces Deep tier regardless of classification
