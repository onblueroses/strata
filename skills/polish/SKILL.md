---
name: polish
description: "Make any repo presentable for public release by restructuring files to ecosystem conventions, generating a first-person README with progressive disclosure, adding missing root files (LICENSE, .gitignore, CONTRIBUTING), and running a privacy sweep with git history scrubbing. Single audit-then-fix pass; targets public repos and humanizes generated prose at the end. Triggers on: 'polish', 'make presentable', 'clean up this repo', 'prepare for open source', 'make the README better', 'repo restructure', 'README generation', 'open source readiness', 'public repo cleanup', 'professionalize this repo'. Also triggers when: user points at a repo and wants it to look professional; user mentions README/LICENSE/.gitignore generation even without saying 'polish'; user is about to publish or open-source a repo. Pairs with /humanizer (invoked as the final phase to strip AI slop from generated prose), /review (sanity check the diff before push), /commit (downstream — commit the polish pass). Manual: invoke with /polish or /polish <path-to-repo>."
---

# Polish

Turn a messy working repo into something you'd show a stranger. One pass: audit everything,
fix everything. No approval gate - you review the diff at the end.

## When NOT to use this skill

- The repo is private and staying private (use normal refactoring instead)
- The user only wants a README rewrite (just write the README directly)
- The repo has fewer than 3 files (nothing to restructure)

---

## Process

The skill runs in two phases back-to-back. Do not pause between them.

### Phase 1: Audit

<details>
<summary>Audit</summary>

Gather everything you need before touching anything.

1. **Detect the stack.** Read the root directory, config files (package.json, pyproject.toml,
   Cargo.toml, go.mod, etc.), and file extensions. Determine the primary language/framework.
   If multi-language, identify each component and its role.

2. **Map the current structure.** Build a tree of all directories and files. Note what's
   misplaced relative to ecosystem conventions (see Structure Conventions below).

3. **Assess the README.** If one exists, grade it:
   - Is it written in first person? (Third person = rewrite)
   - Does it lead with what's technically interesting, not a dry summary?
   - Does it show off the coolest parts of the project?
   - Is install/setup visible without scrolling?
   - Is there at least one real working code example?
   - Does it include concrete numbers, architecture, design decisions?
   If no README exists, note that.

4. **Check root files.** Look for: LICENSE, .gitignore, CONTRIBUTING.md. Note what's missing.

5. **Privacy sweep.** Scan for:
   - Hardcoded IPs, URLs, or domains that look internal
   - TODOs or comments containing names, emails, or internal references
   - .env files, credentials, API keys, tokens
   - References to internal tools, Slack channels, or private services
   Flag everything found - these get stripped in Phase 2.

6. **Summarize findings.** Print a short audit report (under 20 lines) listing what will change.
   Then proceed directly to Phase 2.

</details>

### Phase 2: Fix

<details>
<summary>Fix</summary>

Apply all changes. Work in this order to avoid conflicts.

#### Step 1: Restructure files

Move files to match ecosystem conventions. Use the Structure Conventions section below to
determine the target layout. When moving files:
- Update all import paths and references
- Preserve git history where possible (use `git mv`)
- If the repo uses a build tool, verify the config still points to the right paths

#### Step 2: Generate .gitignore

If missing or incomplete, generate a stack-appropriate .gitignore. Use the detected
language/framework to pick the right template. Include common entries: editor configs,
OS files (.DS_Store, Thumbs.db), build artifacts, node_modules, __pycache__, etc.

#### Step 3: Add LICENSE

If missing, add MIT as the default. Use the current year. If the repo already has a license,
leave it alone.

#### Step 4: Generate README

This is the core output. Follow the README Blueprint below exactly.

#### Step 5: Generate CONTRIBUTING.md

If missing, generate a short contributing guide covering:
- How to set up the dev environment
- How to run tests
- PR conventions (if detectable from git history)

Keep it under 60 lines. Don't generate boilerplate filler.

#### Step 6: Remove infrastructure/operational scripts

Research repos accumulate operational tooling: monitor scripts, deploy scripts, cron jobs,
GPU instance launchers, setup scripts with hardcoded SSH details. These are not part of the
project's public interface. Identify and remove them:

- Monitor scripts (Vast.ai, cloud GPU watchers, cron jobs)
- Deploy/setup scripts with hardcoded instance IDs, SSH ports, or local paths
- Session artifacts (.claude/ session files, handoff docs, specs with personal notes)
- Binary artifacts (tarballs, model weights, notebooks not meant for distribution)

Use `git rm` for tracked files. For files containing secrets, also move a copy to
`~/to-delete/` with a manifest entry before removing from git.

#### Step 7: Privacy sweep and cleanup

Strip everything flagged in the audit:
- Replace hardcoded IPs/URLs with placeholders or environment variable references
- Remove names and emails from TODO comments (keep the TODO, strip the attribution)
- Ensure .env files are in .gitignore
- Remove any committed secrets (warn the user that git history still contains them)

#### Step 8: Scrub git history

Removing a file from the current tree does not remove it from git history. If any file
contained secrets (API keys, tokens, passwords), use `git filter-repo` to erase it from
every commit:

```bash
git filter-repo --invert-paths --path <file-with-secrets> --force
```

After filter-repo runs:
- Re-add the remote: `git remote add origin <url>`
- Verify the secret is gone: `git log --all -p | grep -c '<secret-pattern>'`
- Warn the user they need to force-push: `git push --force`
- Remind them to revoke the leaked credential regardless

If `git filter-repo` is not available, suggest installing it or using BFG Repo-Cleaner.

#### Step 9: Humanize

After all text is generated, invoke the `/humanizer` skill on every prose block in the
README and CONTRIBUTING.md. The humanizer removes AI-generation patterns that make text
feel robotic. This step is important because the README is the first thing a visitor reads
and AI-sounding text undermines credibility.

</details>

---

## Structure Conventions

<details>
<summary>Structure Conventions</summary>

Apply the convention that matches the detected stack. If the repo doesn't fit neatly into
one ecosystem, use the Generic layout.

### Node.js / TypeScript

```
src/
  features/        or domain-grouped directories
  index.ts
tests/
docs/              (if content beyond README exists)
scripts/           (build, deploy, migration scripts)
examples/          (if applicable)
package.json
tsconfig.json
.eslintrc.*        or eslint.config.*
.gitignore
LICENSE
README.md
```

Source goes in `src/`. Feature-based grouping (by domain) over layer-based (controllers/,
models/, services/). Tests mirror `src/` structure inside `tests/`. Config files stay at root.

### Python

```
src/
  packagename/
    __init__.py
    core.py
tests/
  test_core.py
docs/
scripts/
examples/
pyproject.toml
.gitignore
LICENSE
README.md
```

Use src layout (source inside `src/packagename/`). This prevents accidental imports from the
working directory and forces tests to run against the installed package. Tests live outside
`src/`. `pyproject.toml` at root - not `setup.py` unless there's a specific reason.

### Rust

```
src/
  lib.rs           and/or main.rs
  bin/             (additional binaries)
tests/             (integration tests)
benches/
examples/
Cargo.toml
Cargo.lock         (commit for binaries, gitignore for libraries)
.gitignore
LICENSE
README.md
```

Cargo enforces most of this. Don't fight it. Unit tests go inline (`#[cfg(test)]`),
integration tests go in `tests/`. Benches and examples are first-class directories.

### Go

```
cmd/
  appname/
    main.go
internal/          (private packages, compiler-enforced)
pkg/               (optional, public API packages)
docs/
scripts/
go.mod
go.sum
.gitignore
LICENSE
README.md
```

`cmd/` for entrypoints, `internal/` for private code. Don't over-structure small repos -
if there's only one binary and a few packages, a flat layout is fine. The Go community
pushes back on `pkg/` for small projects.

### Generic / Multi-language

```
frontend/          or client/
backend/           or server/
docs/
scripts/
.github/workflows/ (if CI exists)
.gitignore
LICENSE
README.md
```

Each component gets its own directory with its own config files (package.json, pyproject.toml,
etc.). Shared config (CI, editor settings) stays at root.

### What always goes at root

These files must be at the repo root, never nested:
- README.md
- LICENSE
- .gitignore
- CI config (.github/, .gitlab-ci.yml)
- Language config (package.json, Cargo.toml, go.mod, pyproject.toml)
- Editor config (.editorconfig)

### Antipatterns to fix

- Source files scattered in root directory (move to `src/` or equivalent)
- Tests mixed with source (separate unless ecosystem convention says otherwise)
- More than 10 items in the root directory (consolidate into directories)
- Config files buried inside directories (move to root)
- Build artifacts committed (add to .gitignore, remove from tracking)
- Multiple README files at different levels (consolidate to root)

</details>

---

## README Blueprint

<details>
<summary>README Blueprint</summary>

The README is the project's voice. It should read like the author talking to a peer -
first person, opinionated, technically precise. Show off what's cool. The reader should
finish thinking "this person knows what they're doing and built something interesting."

### Voice

**First person, always.** "I built this because..." not "This project provides...".
Third person sounds like a corporate press release. First person sounds like a person
who made something and wants to show you why it's interesting.

**Opinionated over neutral.** "Most workflow engines are either too heavy or too simple"
beats "A workflow engine for TypeScript." Take a position. Say what's wrong with the
alternatives and why this approach is better.

**Technical depth over marketing breadth.** The reader is a developer. Show them the
interesting technical decisions, the architecture, the numbers. Don't dumb it down.
A paragraph about how brain collapse led to 10x better signal encoding is more compelling
than ten bullet points of features.

### Structure

The structure is flexible - adapt it to what the project actually needs. But the opening
matters most:

**Opening (above the fold, no scrolling):**

1. **Project name** as `# heading`
2. **One-line summary** - what it is, concretely. Not a tagline.
3. **The hook** - 1-3 paragraphs explaining WHY this exists and what makes it interesting.
   This is where you show technical prowess. What's the core insight? What problem did you
   solve that others haven't? What surprising result did you get? Lead with the coolest thing.
4. **Quick Nav** (if the README is long enough to need one) - task-oriented ("I want to...")
   not section-oriented ("Getting Started", "Usage"). Example:
   ```markdown
   | I want to... | Go to |
   |--------------|-------|
   | Set it up | [Quick Start](#quick-start) |
   | See what it can do | [Examples](#examples) |
   | Understand the architecture | [How it works](#how-it-works) |
   ```

**Getting started** (never collapse):
- Install command
- One real working example that demonstrates the core value, not a toy hello-world

**The interesting middle** - adapt section names to the project. Don't force every repo
into the same template. A simulation needs "How it works" and "Results so far". A library
needs "Core concepts" and "API". A CLI tool needs "Commands" and "Configuration". Use the
names that make sense.

Show the architecture with ASCII diagrams, mermaid, or a file tree with annotations.
Include actual numbers and results when they exist (benchmark results, experimental findings,
line counts). Specificity is more impressive than vague claims.

**Closing** - License, one line. Contributing link if CONTRIBUTING.md exists.

### Progressive disclosure

Use `<details>`/`<summary>` for secondary content (full hook lists, all CLI commands,
extended configuration tables). Keep the main flow tight - a reader should get the full
picture without expanding anything.

### What NOT to do

- No third person ("The project provides...", "Users can...", "It enables...")
- No marketing language ("powerful", "seamless", "robust", "elegant")
- No generic section names when specific ones work better
- No badges unless they convey real information (CI status yes, "made with love" no)
- No emoji in headings or body text
- No "Table of Contents" heading - Quick Nav IS the table of contents
- No exhaustive API reference in the README (that goes in docs/)
- Don't hide the cool stuff in collapsed sections - lead with it

### Technical showcase checklist

Before finalizing the README, verify you've surfaced:
- [ ] The most technically interesting aspect of the project (architecture, algorithm, result)
- [ ] Concrete numbers where they exist (line count, performance, test results, metrics)
- [ ] Design decisions that show thought ("No built-in persistence because...", "Sequential
      execution because...")
- [ ] What makes this different from alternatives (if applicable)
- [ ] The actual file structure with annotations (not a generic tree)

### Dark mode awareness

If the README includes images, use the `<picture>` element for theme-aware rendering:

```html
<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/logo-dark.png">
  <source media="(prefers-color-scheme: light)" srcset="docs/logo-light.png">
  <img alt="Project Name" src="docs/logo-light.png">
</picture>
```

</details>

---

## Privacy Rules

<details>
<summary>Privacy Rules</summary>

This skill targets public repos. Every generated or modified file must be safe to publish.

**Strip on sight:**
- IP addresses (replace with `YOUR_SERVER_IP` or env var reference)
- Internal domain names (replace with `example.com`)
- Names and emails in code comments or TODOs
- API keys, tokens, secrets (even if they look fake - err on the side of caution)
- References to internal Slack channels, Jira boards, or private services
- Business names that aren't meant to be public

**Warn the user about:**
- Committed .env files (they're in git history even after removal)
- Secrets that appear in git history (suggest `git filter-branch` or BFG)
- Files that look proprietary or confidential

**When unsure:** Flag it and ask. Better to over-flag than to leak.

</details>

---

## Quality self-check

Before reporting completion, verify:

- [ ] README is written in first person throughout (no "the project", "users can", "it provides")
- [ ] Opening hook shows off the most technically interesting aspect
- [ ] Concrete numbers, architecture, or design decisions are visible - not buried in collapsed sections
- [ ] Quick Nav links all resolve to actual headings (if Quick Nav exists)
- [ ] Every `<details>` block has a blank line after `<summary>` and before `</details>`
- [ ] Code examples in README actually match the repo's current code
- [ ] .gitignore covers the detected stack's artifacts
- [ ] No privacy-sensitive content remains in any generated file
- [ ] All moved files have updated import paths
- [ ] The repo builds/runs after restructuring (if testable)
- [ ] Humanizer was run on all prose sections
- [ ] No marketing language ("powerful", "seamless", "robust", "elegant", "comprehensive")
