# strata

Scaffold and validate AI-navigable project structures.

strata encodes a five-layer navigation architecture that makes complex projects navigable by both humans and AI agents. It generates the scaffolding, validates structural integrity, and auto-repairs drift.

## The Five Layers

1. **Constitution** (`PROJECT.md`) - Purpose, constraints, non-negotiables
2. **Global Index** (`INDEX.md`) - Flat map of every file with path + description
3. **Domain Boundaries** (`RULES.md` per folder) - What belongs, what doesn't
4. **Crosslink Mesh** (See Also sections) - Lateral navigation between related files
5. **Per-File Descriptions** (frontmatter/headers) - Retrieval without full file load

## Quick Start

```bash
# Install from source
cargo install --path .

# Initialize a new project
strata init --name my-project --domains Core,Docs,Config,Scripts

# Check structural integrity
strata check

# Run quality diagnostics
strata lint

# Auto-repair issues
strata fix

# Install git hooks
strata install-hooks
```

## What `strata init` Creates

```
my-project/
  PROJECT.md          # Layer 1: Constitution
  INDEX.md            # Layer 2: Global index
  strata.toml         # Configuration
  01-Core/
    RULES.md          # Layer 3: Domain boundary
  02-Docs/
    RULES.md
  03-Config/
    RULES.md
  04-Scripts/
    RULES.md
  config/
  archive/
  .strata/
```

## Commands

### `strata init`

Interactive project scaffolding. Prompts for project name and domains, then generates the full five-layer structure with numbered domain folders.

```bash
# Interactive
strata init

# Non-interactive
strata init --name my-project --domains Core,Docs,Scripts
```

### `strata check`

Structural integrity validation. Pass/fail with exit code 1 on failure.

Checks:
- INDEX.md exists
- PROJECT.md exists
- Every configured domain has RULES.md
- No dead crosslinks

### `strata lint`

Quality diagnostics with severity levels.

| Rule | Severity | Catches |
|------|----------|---------|
| `rules-completeness` | Error | RULES.md missing Purpose or Boundaries section |
| `index-freshness` | Warning | Files not listed in INDEX.md |
| `dead-links` | Error | Crosslinks pointing to non-existent files |
| `missing-descriptions` | Warning | Files without description in frontmatter/header |
| `orphan-files` | Warning | Files not referenced anywhere |
| `empty-folders` | Info | Domain folders with no content |

```bash
# Run all rules
strata lint

# Single rule
strata lint --rule dead-links

# JSON output for CI
strata lint --format json

# Exit code only
strata lint --quiet
```

### `strata fix`

Auto-repair common issues:
- Adds unindexed files to INDEX.md
- Generates missing RULES.md stubs
- Removes dead crosslinks

```bash
# Preview changes
strata fix --dry-run

# Apply fixes
strata fix
```

### `strata install-hooks`

Installs a git pre-commit hook that runs `strata check` before each commit.

## Configuration

`strata.toml` at project root:

```toml
[project]
name = "my-project"
description = "What this project does"

[[project.domains]]
name = "Core"
prefix = "01"

[[project.domains]]
name = "Docs"
prefix = "02"

[structure]
ignore = [".git", ".strata", "node_modules", "target"]
require_descriptions = false

[lint]
disable = []    # Rule names to skip
strict = false  # Treat warnings as errors
```

## Why Five Layers?

AI agents navigate projects by reading files. Without structure, they waste context window on irrelevant files, miss important ones, and make changes in the wrong places.

The five layers solve this by giving every file a discoverable address (INDEX.md), every folder an explicit scope (RULES.md), and every file a one-line summary (frontmatter). An agent can navigate from PROJECT.md to the right domain in three hops.

This pattern was battle-tested across production projects before being extracted into strata.

## License

MIT
