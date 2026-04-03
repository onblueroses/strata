# Evaluate

Extract what's genuinely interesting from a link or pasted content, through the lens of your actual work. Not "is this relevant to your stack" - that's shallow. The real question: what patterns, techniques, or ways of thinking here would make your projects better?

Arguments via `$ARGUMENTS`. Default mode is deep. Use `--quick` for fast triage, `--no-context` to skip context loading.

**Execution order:** Phase 0 and Phase 1 are independent - run them concurrently. Phase 2 depends on Phase 1 output. Phase 3 depends on both Phase 0 and Phase 2.

## Phase 0: Load Work Context

<details>
<summary>Phase 0: Load Work Context</summary>

**Skip if** `--quick` or `--no-context` flag set.

Auto-detect your active projects so Phase 3 can map patterns to real work, not just whatever MEMORY.md happens to contain. This runs inline (no subagents).

1. **Read MEMORY.md entities table.** Extract entity names, paths, and status. Filter to `active` status only.

2. **Batch-scan daily notes from the last 14 days.** Use a single Bash command to extract entity signals from all recent notes at once (avoids 50+ individual Read calls):
   ```bash
   python3 -c "
   import json, glob, os
   from datetime import datetime, timedelta
   cutoff = (datetime.now() - timedelta(days=14)).strftime('%Y-%m-%d')
   notes = sorted(f for f in glob.glob(os.path.expanduser('$STRATA_KB/daily/*.json')) if os.path.basename(f)[:10] >= cutoff)
   for f in notes:
       try:
           d = json.load(open(f))
           print(json.dumps({'file': os.path.basename(f), 'date': d.get('date',''), 'entities_touched': d.get('entities_touched',[]), 'summary': d.get('summary','')[:500]}))
       except: pass
   "
   ```
   From the output, collect two signals per entity per session (not per mention):
   - `entities_touched` field: +2 per session that lists the entity (explicit, most reliable)
   - Entity name substring match in `summary` field: +1 per session whose summary mentions the entity name (case-insensitive, whole-word preferred). Count each session once regardless of how many times the name appears.

3. **Rank entities by activity.** Sum scores across sessions. Tiebreak by most recent appearance date.

4. **Pick top 5-6.** If fewer than 5 active entities have any signal, use whatever is available - don't pad with inactive ones.

5. **Load entity summaries.** Read the first ~40 lines of each selected entity's `summary.md` (at `$STRATA_KB/projects/{entity}/summary.md` or `$STRATA_KB/areas/{entity}/summary.md`). Read all summaries in a single parallel tool call. Extract: purpose, status, architecture outline, current pain points.

6. **Build the context block.** Structure it as:
   ```
   ACTIVE WORK CONTEXT (auto-detected from last 14 days):

   1. [entity-name] (sessions: N, last: YYYY-MM-DD)
      Purpose: [from summary]
      Stack: [from summary]
      Current focus: [from recent session summaries]

   2. [entity-name] ...
   ```

   This block flows to Phase 3 only - explore agents in Phase 2 don't need it (they examine the target, not your projects).

</details>

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

<details>
<summary>For GitHub repos - adaptive multi-agent exploration</summary>

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

Classify by **Project Size**:
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
You are analyzing a GitHub repo to extract TRANSFERABLE PATTERNS - techniques,
architectures, or approaches that could improve other projects.

REPO CONTEXT (from pre-scan):
- Repo: {owner}/{repo}
- Local clone: /tmp/evaluate-{repo}
- Language: {language} | Stars: {stars} | Updated: {updated}
- Description: {description}
- File count: {file_count} ({size_tier})
- Top-level structure: {tree_output}
- README summary: {first_200_words_of_readme}

Your focus: {FOCUS_AREA_DESCRIPTION}

Rules:
- The repo is cloned at /tmp/evaluate-{repo}. Use Read, Grep, Glob on that path.
- Start from the structure above. Don't re-discover project layout.
- Return patterns as named items: "pattern-name: what it is and why it's clever"
- Include specific file paths, function names, config keys - exact names, not paraphrases
- Include exact numbers (benchmarks, sizes, latencies) - never round or summarize
- Skip obvious patterns (has a README, uses standard tooling). Find what's SURPRISING.
- {WORD_BUDGET} words max. No preamble.
```

#### Error recovery

If an agent fails (error, timeout, empty output), note the gap area. Don't retry - the information can be gathered from README + other agents' output. If >50% of agents fail, fall back to single-agent mode (read README + key files from the clone yourself).

#### Cleanup

After all agents return and you've consolidated their output, remove the clone:
```bash
rm -rf /tmp/evaluate-{repo}
```

#### Observability

After each batch, append one log entry per agent to `.claude/agent-log.jsonl`:
```json
{"timestamp":"[ISO]","command":"/evaluate","agent_type":"Explore","model":"[haiku|sonnet]","purpose":"[focus area]","outcome":"[success|error]","session_id":"[id]"}
```

</details>

### For articles, posts, and raw text

No agents. Read the full content yourself. Extract the core technique or argument, not the headline.

**For tweets**: follow the thread. The interesting part is often in replies or linked resources.

### Structured data extraction

Whether from agent output, article text, or repo stats, capture these as literal values - do not paraphrase or round:
- **Numbers**: star counts, benchmark results, percentages, latencies, sizes. Carry the exact value.
- **Names**: function names, file paths, config keys, CLI flags. Use the source's exact spelling.
- **Comparisons**: if the source says "X is 3.2x faster than Y", carry "3.2x", not "significantly faster".

These literals flow through to Phase 5 and Comparison Mode. Re-summarizing numbers across agent boundaries introduces hallucination.

## Phase 3: Find What's Interesting

<details>
<summary>Phase 3: Find What's Interesting</summary>

This is the entire point of the skill. You now have two sources of context:
1. **Phase 0's context block** - the top 5-6 active projects with their purpose, stack, and current focus
2. **Phase 2's agent output** - extracted patterns from the target

**Process:** Read the extracted patterns. For each one, check it against every loaded entity summary. The question isn't "is this relevant?" - it's "what specific thing in this project would change if you applied this pattern?"

**The bar**: if you can't explain in one sentence why someone should care about a pattern, it's not interesting enough. Drop it. No filler patterns to pad the list.

**Cross-domain transfer is where the real value lives.** A game engine's ECS might inform a pipeline's node architecture. A compiler's pass system might improve a workflow pipeline. Domain distance doesn't mean no transfer - it often means the most novel transfer.

**Context-grounded mapping:** Every pattern that maps to a project must reference something specific from the loaded summary - not just the project name. "This would help project-x" is vague. "project-x's node validation is per-node (summary.md line 12) - this cross-node capability negotiation catches type mismatches at graph-build time" is grounded.

**If Phase 0 was skipped** (--no-context or --quick), fall back to MEMORY.md entities in context. The mapping will be shallower but still functional.

**No-match is valid.** If a pattern doesn't map to any loaded project, say so: "No direct application in current projects, but the technique is worth caching for future reference." Don't force connections.

</details>

## Phase 4: Persist

After finding patterns, persist to `.claude/skill-cache.json` so other skills can benefit.

Read current `skill-cache.json`, append to `patterns` array:
```json
{
  "source": "[URL or description]",
  "patterns": ["pattern-name: one-line description", "..."],
  "timestamp": "[ISO 8601]",
  "skill": "/evaluate"
}
```

Update `last_updated`. Prune entries older than 90 days if array exceeds 50.

**Skip if** nothing worth recording was found.

## Phase 5: Present

```
## [Name/Title]

**What**: [1 sentence]

### Patterns

- **[Pattern name]** - [What it is, how it works, why it's clever. 1-2 sentences max. Use exact numbers/names from Phase 2 extraction - never paraphrase metrics.]
  -> [Which project] - [What specifically changes, grounded in loaded entity context. 1 sentence.]

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

<details>
<summary>Comparison Mode (X vs Y)</summary>

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
- From [A]: [specific pattern] -> [which project, how - grounded in Phase 0 context]
- From [B]: [specific pattern] -> [which project, how - grounded in Phase 0 context]
```

After synthesis, run Phase 4 (Persist) as normal. Skip Phase 3 and Phase 5 - the three-pass structure replaces them.

</details>

## Anti-patterns

These are the specific ways this skill fails. Each one has blown past sessions.

| Failure | Why it's bad | What to do instead |
|---------|-------------|-------------------|
| "Interesting error handling" | Teaches nothing. Can't implement "interesting" | "Circuit breaker with 3-strike window that disables failing providers for 60s" |
| "Could be useful for project-x" | Name-dropping a project without saying HOW | "project-x validates per-node but not cross-node - this capability negotiation pattern catches mismatches at build time" |
| Paragraph-length pattern descriptions | Nobody reads them | 1-2 sentences. If you can't compress it, you don't understand it well enough |
| 5 patterns where 2 are interesting | Dilutes the good ones, signals padding | Only include patterns that pass the "one sentence why you should care" test |
| Forced project connections | "This relates to project-x because it also uses React" | If the connection isn't specific and actionable, don't make it. "No match" is valid. |
| Restating what the repo does | Reader can read the README | Say what's SURPRISING or CLEVER, not what's obvious from the description |
| Paraphrasing numbers | "significantly faster" loses the actual data point | Carry exact values: "3.2x faster", "57% error rate", "15.4 points". If you don't have the number, say so. |
| Loading all entities in Phase 0 | Token waste, dilutes signal | Top 5-6 by recent activity. Use what's available if fewer are active. |
| Spawning agents for a blog post | Single-document analysis doesn't benefit from parallelization | Agents are for code repos. Articles: read directly. |
| Ignoring loaded context in Phase 3 | Defeats the purpose of Phase 0 | Every project reference must cite something specific from the loaded summary. |

## Quality Gate

Before presenting, check each pattern:
1. Can you say in one sentence why it matters? If not, drop it.
2. Is the "-> project" line specific enough that the reader could start implementing without reading the source?
3. Did you find at least one cross-domain transfer opportunity? (Not required, but if you didn't look, look again.)
4. If Phase 0 loaded context, does every project reference cite something specific from the loaded summaries? Generic project mentions fail this check.
5. For GitHub repos, did Phase 2 spawn the right number of agents for the repo's size tier? If not, note why (fallback, error recovery).
