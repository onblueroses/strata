---
description: "Evaluate repos, URLs, articles, or pasted content for transferable patterns. Triggers on: 'is this useful?', 'check this out', 'what do you think of this?', 'thoughts?', 'thoughts on this', 'evaluate this', 'have a look at this', 'is this interesting', 'is this any good', 'should I look at this', 'what can we learn from', 'extract patterns from', 'patterns worth stealing', 'lessons from this repo'. Also triggers for an unexplained URL or a requested take on pasted content. Manual: /evaluate; --quick for triage; --no-context to skip local-project context."
---

# Evaluate

Extract what's genuinely interesting from a link or pasted content, through the lens of your actual work. Not "is this relevant to your stack" - that's shallow. The real question: what patterns, techniques, or ways of thinking here would make your projects better?

Arguments via `$ARGUMENTS`. Default mode is deep. Use `--quick` for fast triage, `--no-context` to skip context loading.

**Execution order:** Phase 0 and Phase 1 are independent; run them concurrently. Phase 2 depends on Phase 1. Phase 3 depends on the preceding results.

## Phase 0: Read Local Project Context

**Skip if** `--quick` or `--no-context` flag set.

Resolve the current repository root. Read its `CLAUDE.md`, README, build manifest, and the source or diff relevant to the evaluation question. Extract only facts that a file supports: purpose, constraints, architecture, and current problem.

If the current directory is not a project or no local mapping is useful, leave the context empty. Do not search for a separate Strata memory store.

## Phase 1: Fetch

Identify input type and get the content.

| Input | Detection | Fetch method |
|-------|-----------|-------------|
| GitHub repo | `github.com/{owner}/{repo}` | `gh repo view` + `gh api` for stats |
| GitHub file/dir | `github.com/.../tree/` or `/blob/` | `gh` for repo + WebFetch for path |
| Tweet / X post | `twitter.com` or `x.com` | defuddle or WebFetch |
| HN post | `news.ycombinator.com` | WebFetch for post + top comments |
| Reddit post | `reddit.com` | WebFetch |
| Article / blog | Other URLs | `defuddle parse <url> --md` preferred, WebFetch fallback |
| Raw text | No URL detected | Use directly |

Follow linked resources - the linked thing is usually what matters.

**GitHub repos** (run in parallel):
```bash
gh api repos/{owner}/{repo} --jq '{stars: .stargazers_count, forks: .forks_count, language: .language, updated: .updated_at, archived: .archived, description: .description, topics: .topics, license: .license.spdx_id}'
```
```bash
gh api repos/{owner}/{repo}/readme --jq '.content' | base64 -d
```

## Phase 2: Deep Analysis

**Skip if** `--quick` flag set - go to Quick Mode.

### For GitHub repos - adaptive multi-agent exploration

#### Pre-scan

Get the repo's file count and default branch, then clone for agent access:

```bash
# Get metadata including default branch
gh api repos/{owner}/{repo} --jq '{default_branch: .default_branch, description: .description, language: .language, topics: .topics}'
```
```bash
# Get file count from tree (use default branch name, not HEAD)
gh api "repos/{owner}/{repo}/git/trees/{default_branch}?recursive=1" --jq '[.tree[] | select(.type=="blob")] | length'
```

Classify using **Project Size** tiers from `$STRATA_HOME/reference/tier-classification.md`:
- **Small:** < 30 files
- **Medium:** 30-200 files
- **Large:** 200+ files

#### Clone for agent access

Agents use Read/Grep/Glob which only work on local files. Shallow-clone the repo to a temp directory:

```bash
git clone --depth 1 "https://github.com/{owner}/{repo}.git" /tmp/evaluate-{repo}
```

Pass the clone path to all agents. Clean up after Phase 2 completes: `rm -rf /tmp/evaluate-{repo}`

For very large repos (1000+ files), consider `--filter=blob:none` (treeless clone) to save bandwidth - agents fetch blobs on demand via Read.

#### Agent scaling

| Size | Agents | Model | Batching |
|------|--------|-------|----------|
| Small | 3 | haiku | 1 batch (all at once) |
| Medium | 4 | sonnet | 2 batches (2 + 2) |
| Large | 5 | sonnet | 2 batches (3 + 2) |

All agents use `subagent_type: "Explore"`. **Permission profile: Explorer** (Read, Grep, Glob, WebSearch, WebFetch - no Edit/Write/Agent).

**Word budget per agent:**

| Size | Max words |
|------|-----------|
| Small | 200 |
| Medium | 300 |
| Large | 400 |

**Batched execution** (not all-parallel) for medium/large to avoid OOM - wait for each batch to complete before launching the next.

#### Focus areas

**Small (3 agents):**

| # | Focus | What to extract |
|---|-------|----------------|
| 1 | Architecture + Hard Problem | Module structure, the core algorithm/technique the repo exists to solve, how it's decomposed. Not utils or config - the thing the README brags about. |
| 2 | Patterns + Conventions | Design patterns, abstractions, naming conventions, API surface design, configuration approach. What's idiomatic or novel about how the code is organized? |
| 3 | Data Flow + Error Handling | How data moves through the system, type boundaries, validation strategy, failure modes, edge case handling. Where does it break and how does it recover? |

**Medium (4 agents):** Small's 3 agents plus:

| 4 | External Integration + Build | Dependencies, API contracts, deployment approach, build tooling, CI. What external assumptions does it make? |

**Large (5 agents):** Medium's 4 agents plus:

| 5 | Testing + Quality Strategy | Test architecture, coverage approach, benchmarks, performance-sensitive paths. How does it prove correctness? |

#### Agent/LLM repos - additional focus

If the repo is an agent framework, LLM tool, or AI pipeline (detected from README content and GitHub topics - both available from Phase 1 fetch before agents spawn), replace agent #3 with:

| 3 | Prompt + Context + Orchestration | Prompt structure, context window management, tool schema design, multi-step workflows, retry/fallback logic, model routing. |

#### Agent prompt template

Every agent gets:
```
Goal: Analyze the GitHub repo and extract transferable patterns: techniques, architectures, or approaches that can improve other projects.

Success means:
- Each pattern names a concrete implementation choice from the repo.
- Each pattern explains why the choice is useful beyond this repo.
- Each pattern cites source anchors and literal values when they exist.
- The output stays within the word budget.

Stop when: You have returned the strongest patterns for your assigned focus area.

REPO CONTEXT (from pre-scan):
- Repo: {owner}/{repo}
- Local clone: /tmp/evaluate-{repo}
- Language: {language} | Stars: {stars} | Updated: {updated}
- Description: {description}
- File count: {file_count} ({size_tier})
- Top-level structure: {tree_output}
- README summary: {first_200_words_of_readme}

Your focus: {FOCUS_AREA_DESCRIPTION}
Other agents are covering: {comma-separated list of the other agents' focus areas}
Cover your assigned area deeply and use the other focus list to keep your scope distinct.

Rules:
- Use the clone at /tmp/evaluate-{repo}; read files with Read, Grep, and Glob on that path.
- Start from the provided structure and move directly into files relevant to your focus area.
- Return named pattern items in this shape: "pattern-name: what it is and why it is clever"
- Cite exact file paths, function names, and config keys with their source spelling.
- Carry exact numbers (benchmarks, sizes, latencies) as literal values.
- Select surprising patterns: implementation choices, architectural techniques, or recovery strategies that reveal how the repo solves hard problems.
- Write {WORD_BUDGET} words max and start with the first pattern.
```

#### Error recovery

If an agent fails (error, timeout, empty output), note the gap area. Don't retry - the information can be gathered from README + other agents' output. If >50% of agents fail, fall back to single-agent mode (read README + key files from the clone yourself).

#### Cleanup

After all agents return and you've consolidated their output, remove the clone:
```bash
rm -rf /tmp/evaluate-{repo}
```

#### Observability

After each batch, append one log entry per agent to `$STATE_DIR/agent-log.jsonl`:
```json
{"timestamp":"[ISO]","command":"/evaluate","agent_type":"Explore","model":"[haiku|sonnet]","purpose":"[focus area]","outcome":"[success|error]","session_id":"[id]"}
```

### For articles, posts, and raw text

No agents. Read the full content yourself. Extract the core technique or argument, not the headline.

**For tweets**: follow the thread. The interesting part is often in replies or linked resources.

### Structured data extraction

Whether from agent output, article text, or repo stats, capture these as literal values - do not paraphrase or round:
- **Numbers**: star counts, benchmark results, percentages, latencies, sizes. Carry the exact value.
- **Names**: function names, file paths, config keys, CLI flags. Use the source's exact spelling.
- **Comparisons**: if the source says "X is 3.2x faster than Y", carry "3.2x", not "significantly faster".

These literals flow through to Phase 5 and Comparison Mode. Re-summarizing numbers across agent boundaries introduces hallucination (57% error rate in multi-hop numerical propagation per Lu et al. 2025).

## Phase 3: Find What's Interesting

This is the entire point of the skill. You now have two sources of context:
1. **Phase 0's context block** - verified facts about the current project, when present
2. **Phase 2's agent output** - extracted patterns from the target

**Process:** Read each agent's full output before synthesizing. Work from the extracted text. For each pattern, ask what specific part of the current project would change if the user applied it.

**The bar**: if you can't explain in one sentence why the user should care about a pattern, it's not interesting enough. Drop it. No filler patterns to pad the list.

**Cross-domain transfer is where the real value lives.** A game engine's ECS might inform your-project's node architecture. A compiler's pass system might improve a workflow pipeline. Domain distance doesn't mean no transfer - it often means the most novel transfer.

**Context-grounded mapping:** Every local-project mapping must reference a specific file, component, constraint, or observed failure. A project name alone is not evidence.

**If Phase 0 was skipped** (`--no-context` or `--quick`), present the external pattern without a local-project mapping.

**No-match is valid.** If a pattern doesn't map to any loaded project, say so: "No direct application in current projects, but the technique is worth caching for future reference." Don't force connections.

## Phase 4: Present

```
## [Name/Title]

**What**: [1 sentence]

### Patterns

- **[Pattern name]** - [What it is, how it works, why it's clever. 1-2 sentences max. Use exact numbers/names from Phase 2 extraction - never paraphrase metrics.]
  -> [Current project] - [What specifically changes, grounded in the files read during Phase 0.]

- **[Pattern name]** - [...]
  -> [project] - [...]

### Take it further
[Only if there's a non-obvious next step. 1-2 sentences. Skip if patterns speak for themselves.]
```

That's the whole format. No prose sections. No verdict labels. Each pattern is 2-3 lines.

## Quick Mode (--quick)

```
## [Name]
**What**: [1 sentence]
**Interesting?** yes/no - [1 sentence why]
```

No deep dive. Skim + relevance check. Skips Phase 0 and Phase 2 agents.

## Comparison Mode (X vs Y)

**Detection:** If the input contains "vs", "versus", or "compared to" between two identifiable subjects (repos, tools, frameworks, approaches), activate comparison mode.

**Run Phase 0 first** (if not skipped) - the context block is needed for "What to steal from each."

**Three-pass research:**

1. **Pass A + B (parallel):** Evaluate subject A and subject B as two separate deep analyses. For GitHub repos, each pass independently pre-scans and spawns scaled agents per Phase 2. For articles/text, each pass is read-and-extract by the orchestrator. Each pass captures how each subject's community discusses itself - richer signal than how it talks about competitors.

2. **Pass C (sequential, after A+B complete):** If both subjects are GitHub repos, fetch both READMEs and do a direct structural comparison. If articles/posts, search for content that explicitly compares the two.

3. **Synthesize:** Combine all three passes:

```
## [A] vs [B]

**Quick verdict**: [1-2 sentences with source counts from each pass]

### [A]
[Patterns from Pass A, using standard /evaluate pattern format]

### [B]
[Patterns from Pass B, using standard /evaluate pattern format]

### Head-to-Head
| Dimension | [A] | [B] |
|-----------|-----|-----|
| [relevant comparison axis] | [exact number/value from Pass A] | [exact number/value from Pass B] |

### What to steal from each
- From [A]: [specific pattern] -> [which the user project, how - grounded in Phase 0 context]
- From [B]: [specific pattern] -> [which the user project, how - grounded in Phase 0 context]
```

Skip the standard Phase 3 and Phase 4 output because this synthesis replaces them.

## Anti-patterns

These are the specific ways this skill fails.

| Failure | Why it's bad | What to do instead |
|---------|-------------|-------------------|
| "Interesting error handling" | Teaches nothing. the user can't implement "interesting" | "Circuit breaker with 3-strike window that disables failing providers for 60s" |
| "Could be useful for your-project" | Name-dropping a project without saying HOW | "Your-project validates per-node but not cross-node - this capability negotiation pattern catches mismatches at build time" |
| Paragraph-length pattern descriptions | the user won't read them | 1-2 sentences. If you can't compress it, you don't understand it well enough |
| 5 patterns where 2 are interesting | Dilutes the good ones, signals you're padding | Only include patterns that pass the "one sentence why the user should care" test |
| Forced project connections | "This relates to ProjectA because ProjectA also uses React" | If the connection isn't specific and actionable, don't make it. "No match" is valid. |
| Restating what the repo does | the user can read the README | Say what's SURPRISING or CLEVER, not what's obvious from the description |
| Paraphrasing numbers | "significantly faster" loses the actual data point | Carry exact values from source: "3.2x faster", "57% error rate", "15.4 points". If you don't have the number, say so - don't invent a vague substitute |
| Loading unrelated project histories in Phase 0 | Token waste and diluted signal | Read only the current project's relevant files |
| Spawning agents for a blog post | Single-document analysis doesn't benefit from parallelization | Agents are for code repos with enough material to split across focus areas. Articles: read directly |
| Ignoring loaded context in Phase 3 | Defeats the purpose of Phase 0 | Ground each local mapping in a current project file or observed behavior |

## Quality Gate

Before presenting, check each pattern:
1. Can you say in one sentence why the user should care? If not, drop it.
2. Is the "-> project" line specific enough that the user could start implementing without reading the source?
3. Did you find at least one cross-domain transfer opportunity? (Not required, but if you didn't look, look again.)
4. If Phase 0 loaded context, does every project reference cite a specific file, component, constraint, or observed failure?
5. For GitHub repos, did Phase 2 spawn the right number of agents for the repo's size tier? If not, note why (fallback, error recovery).
