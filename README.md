# strata

AI workspace manager for agent-navigable project structures.

strata encodes a five-layer navigation architecture and manages the full AI agent workspace: lifecycle hooks, specs, sessions, multi-agent target generation. It scaffolds the structure, validates integrity, and auto-repairs drift.

## Quick Start

```bash
# Install from source
cargo install --path .

# Initialize (choose a preset tier)
strata init --name my-project --domains Core,Docs --preset standard

# Check structural integrity
strata check

# Run quality diagnostics (18 lint rules)
strata lint

# Generate context files for your AI agent
strata generate --target claude

# Manage implementation specs
strata spec new my-feature --session abc12345
strata spec list
strata spec status
strata spec complete my-feature

# Track sessions
strata session start --name feature-work
strata session save
strata session list
```

## Presets

`strata init --preset <tier>` controls what gets scaffolded:

| Feature | minimal | standard | full |
|---------|---------|----------|------|
| PROJECT.md, INDEX.md, domains, skills/ | x | x | x |
| .strata/hooks/ (session-start, session-stop, pre-compact) | | x | x |
| Starter skills (review, commit) | | x | x |
| MEMORY.md template | | x | x |
| .strata/specs/ directory | | | x |
| .strata/sessions/ directory | | | x |

## The Five Layers

1. **Constitution** (`PROJECT.md`) - Purpose, constraints, non-negotiables
2. **Global Index** (`INDEX.md`) - Flat map of every file with path + description
3. **Domain Boundaries** (`RULES.md` per folder) - What belongs, what doesn't
4. **Crosslink Mesh** (See Also sections) - Lateral navigation between related files
5. **Per-File Descriptions** (frontmatter/headers) - Retrieval without full file load

## Agent Targets

`strata generate --target <agent>` writes agent-specific context files:

| Target | Output file |
|--------|-------------|
| generic (default) | `.strata/context.md` |
| claude | `CLAUDE.md` |
| cursor | `.cursorrules` |
| copilot | `.github/copilot-instructions.md` |

All targets also generate `.strata/context.md` and per-domain files. Human content above the `<!-- strata:generated -->` marker is preserved across regenerations.

## Commands

### `strata init`

Interactive project scaffolding with preset tiers.

```bash
strata init                                          # interactive
strata init --name my-project --domains Core,Docs    # non-interactive, minimal
strata init --preset full --name my-project          # full workspace
```

### `strata check`

Structural integrity validation. Exit code 1 on failure.

### `strata lint`

Quality diagnostics with 18 rules across Error/Warning/Info severity.

| Rule | Severity | Catches |
|------|----------|---------|
| `rules-completeness` | Error | RULES.md missing Purpose or Boundaries |
| `dead-links` | Error | Crosslinks to non-existent files |
| `index-freshness` | Warning | Files not in INDEX.md |
| `missing-descriptions` | Warning | No frontmatter description |
| `orphan-files` | Warning | Unreferenced files |
| `context-budget` | Warning | Files exceeding char budget |
| `skill-structure` | Warning | Malformed SKILL.md |
| `memory-budget` | Warning | Memory files over budget |
| `hook-structure` | Warning | Hook configured but missing/not executable |
| `hook-budget` | Warning | Hook script too large |
| `spec-structure` | Warning | Missing Status or Current Step |
| `memory-structure` | Info | Memory files without headings |
| `empty-folders` | Info | Domain folders with no content |
| `context-freshness` | Info | Generated context out of date |
| `spec-stale` | Info | In-progress spec not modified recently |
| `spec-ownership` | Info | In-progress spec with no session ID |
| `session-structure` | Info | Malformed daily note or context save |
| `starter-skills` | Info | Hooks configured but no skills installed |

```bash
strata lint                    # all rules
strata lint --rule dead-links  # single rule
strata lint --format json      # CI output
strata lint --quiet            # exit code only
```

### `strata fix`

Auto-repair: add unindexed files to INDEX.md, generate missing RULES.md, remove dead links.

```bash
strata fix --dry-run    # preview
strata fix              # apply
strata fix --index      # rebuild INDEX.md
```

### `strata generate`

Generate context files for AI agents.

```bash
strata generate                  # generic target
strata generate --target claude  # writes CLAUDE.md
strata generate --skills         # install starter skills
```

### `strata spec`

Manage implementation specs in `.strata/specs/`.

```bash
strata spec new my-feature --session abc12345
strata spec list --status in-progress
strata spec status my-feature
strata spec complete my-feature
```

### `strata session`

Track AI agent sessions.

```bash
strata session start --name feature-work
strata session list --limit 20
strata session save --session abc12345
```

### `strata install-hooks`

Install git pre-commit hook that runs `strata check`.

## Configuration

`strata.toml` at project root:

```toml
[project]
name = "my-project"
description = "What this project does"

[[project.domains]]
name = "Core"
prefix = "01"

[structure]
ignore = [".git", ".strata", "node_modules", "target"]
link_mode = "path"  # or "name" for vault-style

[lint]
disable = []
strict = false

[context]
project_budget = 3000
index_budget = 8000
rules_budget = 1500
skill_budget = 5000

[memory]
files = ["MEMORY.md"]
budget = 3200

[hooks]
session_start = ".strata/hooks/session-start.sh"
session_stop = ".strata/hooks/session-stop.sh"
pre_compact = ".strata/hooks/pre-compact.sh"

[specs]
dir = ".strata/specs"
require_session_ownership = true
max_steps_per_phase = 6

[sessions]
dir = ".strata/sessions"
daily_notes = true
context_save = true
staleness_days = 7

[targets]
default = "generic"  # generic | claude | cursor | copilot
```

## Design Principles

- **Agent-agnostic**: Works with Claude, Cursor, Copilot, or any agent that reads markdown
- **Tiered presets**: Start minimal, grow into full workspace management
- **No external dependencies for core**: Session IDs use timestamp hashing, dates use manual epoch math
- **Canonical representation**: `.strata/` is the source of truth; `--target` translates to agent-specific formats

## License

MIT
