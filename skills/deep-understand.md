# Deep Understand

Automated deep familiarization with any codebase, project, or specific domain. Pre-scans to determine project size and type, then spawns an adaptive number of targeted agents.

## Usage

```
/deep-understand [target]
```

Arguments via `$ARGUMENTS`:
- **Path:** `/deep-understand ./src/auth` - explore that directory
- **Concept:** `/deep-understand authentication system` - explore that domain across the codebase
- **Empty:** Explores current working directory

## Skip Conditions

- **Skip if** no argument provided AND cwd is the home directory - too broad; ask the user for a specific target
- **Skip if** the target path doesn't exist - tell the user and stop
- **Skip if** the target was already explored this session (check if you wrote a scratchpad for it in recent context)

## Priority Mode

**When to use:** `--quick` flag, or user just needs a fast overview before starting work.

**Quick mode:** Run only Phase 0 (pre-scan) + read identity files. No agents. Write a brief summary (under 200 words) with the file tree, detected stack, and key files. Skip the full scratchpad. This takes seconds, not minutes.

**What catches deferred work:** User can run full `/deep-understand` later, or the scratchpad check in Phase 0 step 6 will detect incomplete prior results.

---

## DO NOT

- Spawn agents before completing the pre-scan - the pre-scan context block makes agents 3x more effective
- Use more agents than the size tier calls for - extra agents on a small project waste tokens
- Overwrite an existing target-specific scratchpad without asking - the user may have annotated it
- Explore `node_modules/`, `.git/`, `dist/`, `build/`, `.next/`, `__pycache__/` - always exclude these
- Report the raw agent outputs to the user - synthesize into the scratchpad format first
- Run deep-understand on a project you already know well - use `/pickup` instead

---

## Instructions

When invoked, perform deep familiarization on the specified target.

**Parse `$ARGUMENTS`:**
- If it looks like a path (contains `/`, `\`, `.`, or is a directory name): Explore that directory
- If it's conceptual (words describing a domain): Explore that concept across the entire project
- If empty: Explore the current working directory root

---

### Phase 0: Pre-Scan (no agents)

Do this yourself, directly, before spawning any agents. This phase should take seconds, not minutes.

1. **Determine the target path.** Resolve `$ARGUMENTS` to an absolute path. Default to cwd.

2. **Count files and measure size** using Glob and Bash:
   - `Glob("**/*", path=TARGET)` to get file list
   - Exclude: `node_modules/`, `.git/`, `dist/`, `build/`, `.obsidian/`, `__pycache__/`, `.next/`
   - Count the remaining files

3. **Classify project size**:
   - **Small:** < 30 files
   - **Medium:** 30-200 files
   - **Large:** 200+ files

4. **Detect project type** by checking for marker files:
   - **Code project:** Has `package.json`, `Cargo.toml`, `pyproject.toml`, `go.mod`, `*.sln`, `Makefile`, or `src/` directory
   - **Vault/content project:** Has `.obsidian/` folder, or majority of files are `.md`
   - **Mixed:** Has both code markers and significant `.md` content
   - **Concept mode:** `$ARGUMENTS` doesn't resolve to a path - searching across the whole project

5. **Read identity files** (if they exist, read them directly - no agents):
   - `README.md` or `README`
   - `CLAUDE.md` or `.claude/CLAUDE.md`
   - `package.json` (just name, description, scripts, dependencies keys)
   - Any `pyproject.toml`, `Cargo.toml`, `go.mod` (just the project metadata section)

6. **Derive scratchpad filename:**
   - For path targets: slug = last path component, lowercased, spaces → hyphens (e.g. `src/auth` → `auth`, `~/my-vault` → `my-vault`)
   - For concept targets: slug = `$ARGUMENTS` lowercased, spaces → hyphens (e.g. `data pipeline` → `data-pipeline`)
   - Full path: `.claude/scratchpad-deep-understand-{slug}.md`

7. **Check for prior results:**
   - If the target-specific scratchpad exists, read it
   - Tell the user: "Prior findings exist from [date]. Reuse and refresh, or start fresh?"
   - If user says reuse, skip agents whose areas are already well-covered

8. **Build the pre-scan context block** - a text blob you'll include in every agent prompt:
   ```
   PROJECT CONTEXT (from pre-scan):
   - Path: [absolute path]
   - Type: [code|vault|mixed]
   - Size: [N files] ([small|medium|large])
   - Language/framework: [detected from identity files]
   - Purpose: [from README/package.json description]
   - File tree (top 2 levels): [output]
   ```

9. **Run `git status`** (code projects only) to capture working state. Add to context block if relevant.

---

### Phase 1: Spawn Adaptive Agents

Every agent uses `subagent_type: "Explore"`. **Permission profile: Explorer** (Read, Grep, Glob, WebSearch, WebFetch - no Edit/Write/Agent). **Do NOT launch all agents in parallel for medium/large projects** - this causes OOM crashes. Use batched execution instead.

**Error recovery:** If an Explore agent fails (error, timeout, empty output), note the gap area in consolidation. Do not retry individual agents - the information can be filled manually. If >50% of agents in a batch fail, abort the entire run and report: "Familiarization failed - [N]/[total] agents returned errors. Try `/deep-understand --quick` for a lightweight scan."

**Observability:** After each batch completes, append one log entry per agent to `.claude/agent-log.jsonl`:
`{"timestamp":"[ISO]","command":"/deep-understand","agent_type":"Explore","model":"[haiku|sonnet]","purpose":"[focus area]","duration_estimate":"[fast|medium]","outcome":"[success|error]","session_id":"[id]"}`

Agent count and model by size:

- **Small:** Launch all 3 agents in a single parallel message.
- **Medium:** Launch in 2 batches - first 3, wait for results, then remaining 2.
- **Large:** Launch in 3 batches - first 3, wait, next 3, wait, final 2.

Wait for each batch to fully complete before launching the next.

**Model and count by size:**

| Size | Agent count | Model | Batches |
|------|-------------|-------|---------|
| Small (< 30 files) | 3 | haiku | 1 (all at once) |
| Medium (30-200) | 5 | sonnet | 2 (3 + 2) |
| Large (200+) | 8 | sonnet | 3 (3 + 3 + 2) |

**Word budget per agent:**

| Size | Summary length |
|------|---------------|
| Small | 200 words max |
| Medium | 300 words max |
| Large | 400 words max |

---

#### CODE PROJECT agents

**Small (3 agents):**

| # | Focus | What to find |
|---|-------|-------------|
| 1 | Identity + Architecture | Purpose, language, framework, folder structure, module boundaries, entry points, build/deploy config |
| 2 | Data + API + State | Types, schemas, data flow, routes, exports, interfaces, state management, external integrations |
| 3 | Quality + Conventions | Tests, error handling, security patterns, code style, naming conventions, linting config |

**Medium (5 agents):**

| # | Focus | What to find |
|---|-------|-------------|
| 1 | Architecture + Patterns | Module structure, abstractions, design patterns, entry points, startup flow |
| 2 | Data + State | Types, schemas, entities, relationships, stores, caching, state management |
| 3 | API + Integration | Routes, exports, interfaces, external service calls, dependencies, environment config |
| 4 | Build + Deploy + Config | Build scripts, CI/CD, Dockerfile, env vars, config files, package scripts |
| 5 | Quality | Tests, error handling, security, logging, code style, conventions, linting |

**Large (8 agents):**

| # | Focus | What to find |
|---|-------|-------------|
| 1 | Architecture | High-level module structure, boundaries, layering, design patterns |
| 2 | Entry Points + Startup | Main files, CLI, server startup, initialization flow |
| 3 | Data Models | Types, schemas, entities, database models, relationships |
| 4 | State + Caching | Stores, context, globals, caching strategies, session management |
| 5 | API Surface | Routes, exports, public interfaces, commands, GraphQL schemas |
| 6 | External Integration | Third-party libs, service calls, environment config, secrets usage |
| 7 | Build + Deploy | CI/CD, Docker, build scripts, package scripts, deployment config |
| 8 | Quality + Security | Tests, error handling, auth, permissions, input validation, logging |

---

#### VAULT/CONTENT PROJECT agents

**Small (3 agents):**

| # | Focus | What to find |
|---|-------|-------------|
| 1 | Structure + Content | Folder organization, content types, metadata/frontmatter, tags |
| 2 | Links + Workflows | Internal links, orphans, hub notes, creation/publishing workflows |
| 3 | Quality + Integration | Style rules, gaps, drafts, TODOs, scripts, automation, external tools |

**Medium (5 agents):**

| # | Focus | What to find |
|---|-------|-------------|
| 1 | Structure + Navigation | Folder organization, navigation patterns, index files, MOCs |
| 2 | Content Types + Metadata | What kinds of content exist, frontmatter schema, tags, properties |
| 3 | Link Graph | Internal links, backlinks, orphan notes, hub notes, clusters |
| 4 | Workflows + Publishing | Creation flow, review process, publishing pipeline, automation |
| 5 | Quality + Gaps | Style rules, TODOs, drafts, incomplete items, consistency issues |

**Large (8 agents):**

| # | Focus | What to find |
|---|-------|-------------|
| 1 | Top-level Structure | Folder organization, naming conventions, navigation patterns |
| 2 | Content Types | What kinds of content exist, templates, archetypes |
| 3 | Metadata System | Frontmatter schema, tags, properties, dataview queries |
| 4 | Link Graph + Hubs | Internal links, orphans, hub notes, clusters, MOCs |
| 5 | Workflows | Creation, review, publishing flow, status tracking |
| 6 | Automation + Integration | Scripts, plugins, external tools, n8n, publishing targets |
| 7 | Personas + Style | Content voices, style guides, constraints, forbidden patterns |
| 8 | Quality + Gaps | TODOs, drafts, incomplete items, stale content, consistency |

---

#### CONCEPT MODE agents

Scale agent count the same way (by project size), but with concept-tracing focuses:

**Small (3 agents):**

| # | Focus |
|---|-------|
| 1 | Definition + Entry Points: Where is [CONCEPT] defined? How is it triggered/started? |
| 2 | Data Flow + State: What data flows through it? What state does it manage? |
| 3 | Integration + Quality: What depends on it? How is it tested? How does it fail? |

**Medium (5 agents):**

| # | Focus |
|---|-------|
| 1 | Definition: Core files, types, interfaces where [CONCEPT] lives |
| 2 | Entry Points + Triggers: How [CONCEPT] gets invoked, startup paths |
| 3 | Data Flow: Inputs, transforms, outputs through [CONCEPT] |
| 4 | Dependencies + Integration: What [CONCEPT] depends on, what depends on it |
| 5 | Quality: Testing, error handling, configuration, security |

**Large (8 agents):**

| # | Focus |
|---|-------|
| 1 | Definition: Core files, types, interfaces |
| 2 | Entry Points: How [CONCEPT] gets triggered/started |
| 3 | Data Flow: Inputs, transforms, outputs |
| 4 | State: What state [CONCEPT] manages or accesses |
| 5 | Dependencies: What [CONCEPT] depends on |
| 6 | Dependents: What depends on [CONCEPT] |
| 7 | Configuration: How [CONCEPT] is configured, env vars |
| 8 | Quality: Testing, error handling, security |

---

### Agent Prompt Template

Every agent gets the same structure. Fill in the blanks per agent:

```
You are exploring a [TYPE] project to understand [FOCUS_AREA].

[PRE-SCAN CONTEXT BLOCK from Phase 0]

Your task: [SPECIFIC_QUESTIONS for this agent's focus area]

Rules:
- Start from the file tree provided above. Don't re-discover project structure.
- Reference specific files as path:line_number where relevant.
- Skip node_modules, .git, dist, build, __pycache__, .next.
- Return a [WORD_BUDGET]-word summary. No preamble, no filler.
```

---

### Phase 2: Consolidation

After all agents return:

1. **Write scratchpad** at `.claude/scratchpad-deep-understand-{slug}.md` (slug derived in Phase 0 step 6) with organized findings:
   ```markdown
   # Deep Understand: [target]
   Date: [YYYY-MM-DD]
   Type: [code|vault|mixed] | Size: [N files] ([small|medium|large])

   ## Identity
   [What this is, its purpose, language/framework]

   ## Architecture
   [How it's structured, key patterns, module boundaries]

   ## Key Components
   [Most important files/modules with paths]

   ## Data Flow
   [How data moves through the system]

   ## External Interfaces
   [APIs, integrations, entry points]

   ## Patterns + Conventions
   [Coding style, naming, structure patterns]

   ## Constraints
   [Rules, gotchas, things to never do]

   ## Pending/Incomplete
   [TODOs, gaps, known issues]

   ## Navigation Reference

   | To understand... | Read... |
   |------------------|---------|
   | [topic] | [file:line] |

   ## Recommended Exploration Order
   1. [file] - [why first]
   2. [file] - [why second]
   ```

2. **Summarize for user** (under 400 words):
   - What this is
   - How it works
   - Key patterns
   - Important constraints
   - What's ready vs pending

3. **Offer next steps:**
   - "Want me to dive deeper into [X]?"
   - "Ready to work on this - what's the task?"

---

## Quality Self-Check

After writing the scratchpad and before presenting to the user:
1. **All agents returned** - did every spawned agent complete? If any timed out, note the gap
2. **Scratchpad written** - is the scratchpad file actually saved to disk?
3. **Key files referenced** - does the Navigation Reference table contain real file:line paths that exist?
4. **No conflation** - did you keep findings from different agents distinct, not merge contradictory info?
5. **Summary under 400 words** - the user summary should be concise; the scratchpad has the full details

---

## Special Behaviors

**For code projects:**
- Include `git status` output from pre-scan in context
- Note any failing tests mentioned in CI configs
- Check for security-sensitive files (.env, credentials)

## Examples

```
/deep-understand
-> Pre-scans cwd, detects "medium code project", spawns 5 Explore agents (sonnet)

/deep-understand ./src/auth
-> Pre-scans src/auth, detects "small code" (12 files), spawns 3 Explore agents (haiku)

/deep-understand authentication
-> Concept mode, scans full project size, spawns scaled concept-tracing agents

/deep-understand data pipeline
-> Concept mode, traces data flow across project with scaled agent count
```
