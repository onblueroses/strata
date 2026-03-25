# strata

AI workspace manager for agent-navigable project structures.

strata encodes a five-layer navigation architecture and manages the full AI agent workspace: lifecycle hooks, specs, sessions, multi-agent target generation, skill evaluation, and monorepo workspaces. It scaffolds the structure, validates integrity, detects drift, and auto-repairs issues.

## Quick Start

```bash
# Install from source
cargo install --path .

# Initialize (choose a preset tier)
strata init --name my-project --domains Core,Docs --preset standard

# Check structural integrity
strata check

# Run quality diagnostics (20 built-in lint rules + custom rules)
strata lint

# Generate context files for your AI agent
strata generate --target claude-code

# Show what changed since last generation
strata diff

# Selectively regenerate only changed files
strata update

# Watch for changes and regenerate automatically
strata watch

# Manage implementation specs
strata spec new my-feature --session abc12345
strata spec list
strata spec status
strata spec complete my-feature

# Track sessions
strata session start --name feature-work
strata session save
strata session list

# Evaluate and optimize skill descriptions
strata skill eval my-skill --eval-set skills/my-skill/eval-set.json
strata skill optimize my-skill --eval-set skills/my-skill/eval-set.json --report

# Generate shell completions
strata completions bash > ~/.bash_completion.d/strata
```

## Presets

`strata init --preset <tier>` controls what gets scaffolded:

| Feature | minimal | standard | full |
|---------|---------|----------|------|
| PROJECT.md, INDEX.md, domains, skills/ | x | x | x |
| .strata/hooks/ (session-start, session-stop, pre-compact) | | x | x |
| 23 core skills (review, commit, debug, test, plan, pr, explore, release, security, optimize, verify, end, pickup, tidy, research, deploy, status, get-to-work, trace, learn, deep-understand, reconcile, ship) | | x | x |
| .claude/settings.json (for ClaudeCode targets) | | x | x |
| MEMORY.md template | | x | x |
| references/ (code-quality.md, skill-design.md) | | x | x |
| --no-enforce flag for warning-only hooks | | x | x |
| .strata/specs/ directory | | | x |
| .strata/sessions/ directory | | | x |
| references/getting-started.md | | | x |
| 7 meta skills (skill-creator, ask-better, autooptimize, context-resume, context-save, browser-automation, visualize) | | | x |
| Domain skills with project-type matching (frontend, n8n, security, obsidian, academic) | | | x |

## The Five Layers

1. **Constitution** (`PROJECT.md`) - Purpose, constraints, non-negotiables
2. **Global Index** (`INDEX.md`) - Flat map of every file with path + description
3. **Domain Boundaries** (`RULES.md` per folder) - What belongs, what doesn't
4. **Crosslink Mesh** (See Also sections) - Lateral navigation between related files
5. **Per-File Descriptions** (frontmatter/headers) - Retrieval without full file load

## Agent Targets

`strata generate --target <agent>` writes agent-specific context files:

| Target | Output file | Hook mechanism |
|--------|-------------|----------------|
| claude-code (default) | `CLAUDE.md` | `.claude/settings.json` |
| opencode | `AGENTS.md` | JS/TS plugins |
| pi | `AGENTS.md` | TS extensions |

All targets also generate `.strata/context.md` and per-domain files. Human content above the `<!-- strata:generated -->` marker is preserved across regenerations.

## Commands

<details>
<summary>Commands</summary>

### `strata init`

Interactive project scaffolding with preset tiers. Detects project type (Rust, JS/TS, Python, Go, frameworks) and adapts templates.

```bash
strata init                                          # interactive
strata init --name my-project --domains Core,Docs    # non-interactive, minimal
strata init --preset full --name my-project          # full workspace
```

### `strata check`

Structural integrity validation. Exit code 1 on failure.

### `strata lint`

Quality diagnostics with 20 built-in rules across Error/Warning/Info severity, plus user-defined custom rules.

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
| `stale-dates` | Warning | `last_verified:` or `_Last updated:_` dates past threshold |
| `waiting-markers` | Warning | `WAITING (YYYY-MM-DD)` markers past threshold |
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
strata lint --format sarif     # SARIF v2.1.0 for GitHub Code Scanning
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
strata generate                       # claude-code (default)
strata generate --target opencode     # writes AGENTS.md
strata generate --skills              # install starter skills
```

### `strata diff`

Show what would change if you regenerated now. Compares current generated files against what `generate` would produce.

```bash
strata diff                     # compare all targets
strata diff --target claude-code     # compare specific target
```

### `strata update`

Selectively regenerate only context files that are out of date (based on file modification times and git state).

```bash
strata update                    # update stale files
strata update --target claude-code    # update specific target
```

### `strata watch`

Watch for file changes and automatically regenerate context files.

```bash
strata watch                     # default 300ms debounce
strata watch --debounce 500      # custom debounce interval
strata watch --target claude-code     # watch for specific target
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

### `strata skill`

Evaluate and optimize skill trigger descriptions.

```bash
strata skill eval my-skill --eval-set eval.json       # test trigger accuracy
strata skill eval my-skill --eval-set eval.json --format json
strata skill optimize my-skill --eval-set eval.json    # iterative improvement
strata skill optimize my-skill --eval-set eval.json --report --apply
strata skill eval-set init my-skill                    # create starter eval set
```

### `strata install-hooks`

Install git pre-commit hook that runs `strata check`.

### `strata completions`

Generate shell completion scripts.

```bash
strata completions bash > ~/.bash_completion.d/strata
strata completions zsh > ~/.zfunc/_strata
strata completions fish > ~/.config/fish/completions/strata.fish
strata completions powershell > _strata.ps1
```

</details>

## Custom Lint Rules

<details>
<summary>Custom Lint Rules</summary>

Define project-specific lint rules in `strata.toml`:

```toml
[[custom_rules]]
name = "require-changelog"
severity = "warning"
check = "file_exists"
glob = "CHANGELOG.md"
message = "CHANGELOG.md is missing"

[[custom_rules]]
name = "no-bare-todos"
severity = "error"
check = "content_contains"
glob = "**/*.md"
pattern = "TODO"
negate = false
message = "bare TODO found"

[[custom_rules]]
name = "require-description"
check = "frontmatter_key"
glob = "**/*.md"
key = "description"
message = "Missing frontmatter description"
```

Check types: `file_exists`, `file_missing`, `content_contains`, `frontmatter_key`.

</details>

## Workspace Support

<details>
<summary>Workspace Support</summary>

Monorepo projects can declare workspace members. Each member has its own `strata.toml`, and workspace-level commands aggregate results across members.

```toml
[project]
name = "my-monorepo"

[workspace]
members = ["client", "server", "shared"]
```

</details>

## Configuration

<details>
<summary>Configuration</summary>

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
scan_extensions = ["md", "txt", "rs", "py", "js", "ts"]  # override defaults

[lint]
disable = []
strict = false
stale_verified_days = 7    # days before last_verified: triggers warning
stale_updated_days = 60    # days before _Last updated:_ triggers warning
stale_waiting_days = 30    # days before WAITING markers trigger warning

[context]
project_budget = 3000
index_budget = 8000
rules_budget = 1500
skill_budget = 5000

[memory]
files = ["MEMORY.md"]
budget = 3200

[hooks]
enforce = true  # block session-stop until verification passes
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
active = ["claude-code"]  # claude-code | opencode | pi

[skills]
eval_backend = "claude-code"
eval_workers = 4
eval_timeout = 30
trigger_threshold = 0.5
runs_per_query = 1
holdout = 0.4
max_iterations = 5

[workspace]
members = []  # monorepo member directories

# Custom lint rules (repeatable)
# [[custom_rules]]
# name = "my-rule"
# check = "file_exists"  # file_exists | file_missing | content_contains | frontmatter_key
# glob = "README.md"
# message = "README is missing"
```

</details>

## Design Principles

- **Agent-aware**: First-class support for Claude Code, OpenCode, and Pi with target-specific generation
- **Tiered presets**: Start minimal, grow into full workspace management
- **No external dependencies for core**: Session IDs use timestamp hashing, dates use manual epoch math
- **Canonical representation**: `.strata/` is the source of truth; `--target` translates to agent-specific formats
- **Opinionated defaults**: Standard preset includes code quality principles, skill design guidelines, and reference docs

## License

MIT
