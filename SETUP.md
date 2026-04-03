# SETUP.md - Bootstrap Prompt

Paste this file's contents into your AI agent's first message to configure
strata for your project. The agent will detect your project type, select
relevant skills, wire hooks, and generate a CLAUDE.md.

---

You are setting up the strata agent harness for this project. Follow each
section in order. Ask questions only when marked [ASK].

## 1. Detect Project Type

Scan the current directory for:

- `package.json` -> Node.js (check for next, react, vue, svelte, astro, express)
- `Cargo.toml` -> Rust
- `pyproject.toml` or `requirements.txt` -> Python (check for django, flask, fastapi)
- `go.mod` -> Go
- `*.sln` or `*.csproj` -> .NET
- `Makefile` or `CMakeLists.txt` -> C/C++
- `.obsidian/` -> Obsidian vault (use vault mode)
- Multiple of the above -> monorepo

Record the detected type and frameworks. You will use this in step 2.

## 2. Select Skills

Read `skills/INDEX.md` for the full categorized skill list.

**Always install (core):**
- review, verify, commit, debug, test, plan, spec, explore, end, pickup

**Install if relevant to detected project type:**
- Frontend project: frontend-design, ship, mobile-preview, react-best-practices
- Node.js API: security-review, deploy, xbow
- Python project: research, visualize
- n8n workflows: n8n-code-javascript, n8n-code-python, n8n-expression-syntax,
  n8n-workflow-patterns, n8n-node-configuration, n8n-validation-expert,
  n8n-mcp-tools-expert
- Obsidian vault: obsidian-markdown, obsidian-cli, obsidian-bases, json-canvas
- Any project with deployments: deploy, status
- Any project needing research: research, deep-understand, evaluate

**[ASK]** Show the user the selected skills and ask if they want to add or
remove any. Also ask: "Do you want the meta skills? (skill-creator,
autooptimize, visualize, context-resume, context-save, browser-automation,
copywriting, latex-presentation)"

Copy selected skill files from `skills/` to your project's skill directory
(`.claude/commands/` for Claude Code, or the equivalent for your agent).

## 3. Wire Hooks

Copy the hooks you want from `hooks/` to your project. The recommended
starter set:

**Quality gates (blocking):**
- `quality-lint-on-write.sh` - lint Python/JS/TS on every edit
- `quality-crlf-check.sh` - catch Windows line endings
- `quality-search-path-guard.sh` - prevent broad searches

**Context management (advisory):**
- `context-nudge.sh` - remind to save context before compaction
- `context-suggest-compact.sh` - suggest compaction at tool call thresholds
- `context-pre-compaction-save.sh` - auto-save state before compaction

**Session lifecycle:**
- `session-check-dev-servers.sh` - warn about too many dev servers
- `gate-verify.sh` - enforce verification before session end

**Observability (advisory):**
- `observe-track-edits.sh` - track which files were edited
- `observe-track-session-events.sh` - JSONL event log
- `observe-track-skill-runs.sh` - track skill invocations

Use `examples/settings.json` as a template for wiring hooks into your agent's
settings. For Claude Code, this goes in `.claude/settings.json`.

**For the observability and verification hooks**, set the state directory:
```bash
export STRATA_STATE_DIR="${XDG_STATE_HOME:-$HOME/.local/state}/strata"
mkdir -p "$STRATA_STATE_DIR"
```

**[ASK]** "Which hooks do you want? I recommend the full set for a thorough
setup, or just the quality gates for a lightweight start."

## 4. Generate CLAUDE.md

Create a `CLAUDE.md` (or equivalent) for the project following the pattern in
`examples/CLAUDE.md`. Include these sections:

1. **Project Overview** - one paragraph: what, stack, what matters
2. **Commands** - frequently used commands with aliases
3. **Architecture** - code organization, enough to navigate without exploring
4. **Constraints** - always/ask first/never rules
5. **Conventions** - patterns to match

Populate each section by reading:
- README.md (project description, setup instructions)
- Package manifest (dependencies, scripts)
- Source directory structure (architecture)
- Existing CI/CD config (commands, quality gates)
- Any existing CLAUDE.md or AGENTS.md content

**[ASK]** Show the generated CLAUDE.md to the user for review before writing.

## 5. Set Up Memory

Create `MEMORY.md` at the project root (or `.claude/memory/MEMORY.md` for
Claude Code's auto-memory):

```markdown
# Memory Index

(No entries yet. Use /learn to add patterns, decisions, and gotchas as you work.)
```

The memory file will grow organically as the agent works on the project.
Don't pre-populate it.

## 6. Reference Docs (Optional)

If the user wants reference documentation available to the agent:

```bash
mkdir -p references/
cp path/to/strata/reference/code-quality.md references/
cp path/to/strata/reference/skill-design.md references/
cp path/to/strata/reference/getting-started.md references/
```

These are optional but useful for teams onboarding to strata.

## Done

Report what was configured:
- Skills installed (count and names)
- Hooks wired (count and which events)
- CLAUDE.md created (confirm sections)
- Memory initialized

The harness is ready. The agent can now use `/pickup` to load context and
start working.
