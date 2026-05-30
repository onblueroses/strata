<!-- keywords: subagent, spawn agent, agent type, model selection, observability schema, agent logging, ad-hoc agent, cross-skill state -->
# Agent Taxonomy

Central reference for all agent types available in Claude Code. Covers formal definitions
(`$STRATA_HOME/agents/`), ad-hoc patterns used in commands, and cross-agent infrastructure.

Read this before spawning subagents. Use the right agent for the job - wrong agent type
wastes tokens and produces worse results.

---

## Quick Nav

| Task | Section |
|------|---------|
| Choose which agent type to spawn | Agent Types |
| Understand ad-hoc agent patterns in commands | Ad-Hoc Patterns |
| Share findings between skills | Cross-Skill State |
| Log agent invocations | Observability |
| Handle agent failures | Error Recovery (in `agent-architecture.md`) |

---

## Agent Types

Formal agent definitions in `$STRATA_HOME/agents/`. These have YAML frontmatter with name, description, tools, and model.

| Agent | Model | Tools | Spawned by | Use when |
|-------|-------|-------|------------|----------|
| `knowledge-lookup` | haiku | Read, Grep, Glob | Any command needing entity data | Fast lookup in `$KB_DIR/` knowledge base. Entity summaries, items.json, daily notes, PARA structure. NOT for analysis. |
| `quick-research` | haiku | WebSearch, WebFetch, Read | `/research` Simple tier, any quick lookup | Simple factual web lookups: docs, versions, definitions. NOT for multi-step reasoning. |
| `code-reviewer` | sonnet | Read, Grep, Glob, Bash | `/verify` Full tier, code review tasks | Review code for correctness, style, edge cases. Reads files, runs tests. Not security-focused (use `/harness` for that). |
| `pattern-extractor` | sonnet | Read, Grep, Glob, WebFetch | `/evaluate` Phase 3 | Extract transferable patterns from code or content. Architecture decisions, clever solutions, cross-domain ideas. |

`dmux-pane` is not a subagent — see the dmux Dispatch Panes entry under Ad-Hoc Patterns.

### Model Selection Guide

| Task type | Model | Why |
|-----------|-------|-----|
| File reads, searches, simple lookups | haiku | 80% cheaper, sufficient for retrieval |
| Moderate analysis, code review, research synthesis | sonnet | Needs reasoning but not frontier |
| Planning, adversarial evaluation, architecture | opus | Complex reasoning, high-stakes decisions |

**Rule of thumb**: if the agent just reads and returns, use haiku. If it must reason about what it found, use sonnet. If it must make decisions that are hard to reverse, use opus. If the task is independent implementation work that doesn't need to return into the parent's context, use a dmux pane (`/dispatch`) instead of a subagent.

---

## Ad-Hoc Patterns

<details>
<summary>Ad-Hoc Patterns</summary>

These aren't formal agent definitions but recurring patterns where commands spawn `general-purpose` or `Explore` agents with specific prompts.

### Explore Agents (`/deep-understand`)

- **Type**: `subagent_type: "Explore"`
- **Model**: haiku (small projects) or sonnet (medium/large)
- **Purpose**: Codebase familiarization - architecture, data flow, conventions
- **Pattern**: Pre-scan context block injected into each agent's prompt. Agents get focused areas (architecture, data, API, quality).
- **Batching**: Small = 3 parallel, Medium = 5 in 2 batches, Large = 8 in 3 batches

### Research Agents (`/research`)

- **Type**: `subagent_type: "general-purpose"` (Moderate) or `subagent_type: "general-purpose"` with sonnet (Complex)
- **Model**: haiku (Moderate), sonnet (Complex)
- **Purpose**: Parallel web research on decomposed sub-questions
- **Pattern**: Each agent gets one sub-question + word budget. Results synthesized by orchestrator.

### Generator/Evaluator Agents (`/harness`)

- **Type**: Opus subagents (both generator and evaluator)
- **Model**: opus (always - correctness stakes justify cost)
- **Purpose**: Adversarial loop. Generator implements, evaluator judges with asymmetric information.
- **Pattern**: Evaluator never sees task description or generator reasoning. Rotating adversarial framings break systematic bias. Fresh generation on failure, not patching.

### Plan Agents (`/spec`)

- **Type**: `subagent_type: "Plan"` with `model: "opus"`
- **Purpose**: Architecture and implementation planning
- **Pattern**: Receives full task description + exploration results + constraints. Returns plan content only. Orchestrator writes the spec file.

### dmux Dispatch Panes (`/dispatch`)

- **Type**: Independent agent sessions in git worktrees (NOT subagents - fully separate processes)
- **Model**: Any (claude, codex, gemini - each pane is a full CLI session)
- **Purpose**: Parallel implementation of independent tasks. Each pane gets its own worktree, branch, and context window.
- **Pattern**: Parent writes `.task-brief.md` (YAML frontmatter + structured sections), calls `dmux-dispatch.sh` to create worktree + tmux pane. Child reads brief, executes, writes `.task-result.md` via `/end`. Parent reads results via `/collect`.
- **When to use over subagents**: When the task can be fully specified upfront and the parent doesn't need the result in working memory. Default for implementation tasks. See Delegation section in CLAUDE.md.
- **Communication**: Filesystem only - `.task-brief.md` (parent->child), `.task-result.md` (child->parent), `.task-blocked.md` (child->parent), `.dmux/scratchpad/{slug}.md` (sibling->sibling).
- **Design doc**: `$STRATA_HOME/reference/dmux-dispatch-protocol.md`

</details>

---

## Cross-Skill State

<details>
<summary>Cross-Skill State</summary>

Skills can share findings via `.claude/skill-cache.json`. This enables patterns extracted by one skill to inform another.

### Schema

```json
{
  "version": 1,
  "patterns": [
    {
      "source": "url-or-description",
      "patterns": ["pattern-name: one-line description"],
      "timestamp": "2026-03-25T22:00:00Z",
      "verdict": "adopt|adapt|learn|pass",
      "skill": "/evaluate"
    }
  ],
  "last_updated": "2026-03-25T22:00:00Z"
}
```

### Who writes

| Skill | What it writes |
|-------|---------------|
| `/evaluate` | Extracted patterns from repos/articles (Phase 3) |
| `/learn` | Patterns captured mid-session |

### Who reads

| Skill | How it uses patterns |
|-------|---------------------|
| `/harness` | Reads patterns relevant to task type, includes in generator's PROJECT CONSTRAINTS |
| Future agents | Can query for domain-specific grounding before starting work |

### Convention

- Append only. Never delete entries.
- Keep entries under 50. If over 50, the next writer should prune entries older than 90 days or with verdict `pass`.
- Always include `skill` field so readers know the source context.

</details>

---

## Observability

<details>
<summary>Observability</summary>

Commands log agent invocations to `.claude/agent-log.jsonl` for analysis. One JSON object per line, appended after each agent completes.

### JSONL Entry Schema

```json
{
  "timestamp": "2026-03-25T22:00:00Z",
  "command": "/research",
  "agent_type": "general-purpose",
  "model": "haiku",
  "purpose": "Research Redis vs Memcached tradeoffs",
  "duration_estimate": "fast",
  "outcome": "success",
  "session_id": "53524fee"
}
```

### Fields

| Field | Type | Values |
|-------|------|--------|
| `timestamp` | ISO 8601 | When the agent completed |
| `command` | string | Which command spawned this agent |
| `agent_type` | string | `knowledge-lookup`, `quick-research`, `code-reviewer`, `pattern-extractor`, `general-purpose`, `Explore`, `Plan` (use `dmux-pane` as a label when logging dispatches even though it isn't a formal agent) |
| `model` | string | `haiku`, `sonnet`, `opus` |
| `purpose` | string | One-line description of what this agent was doing |
| `duration_estimate` | string | `fast` (<30s), `medium` (30s-2min), `slow` (>2min) |
| `outcome` | string | `success`, `error`, `timeout`, `partial` |
| `session_id` | string | 8-char session ID |

### When to log

- `/research`: log each research agent after completion
- `/verify`: log subagent for Full/Deep tiers
- `/deep-understand`: log each Explore agent batch
- `/harness`: log generator and evaluator agents per iteration
- `/evaluate`: log pattern extraction agents
- `/dispatch`: log each dispatched pane (agent_type: `dmux-pane`, model: agent name, duration: `slow`)
- `/collect`: log collection run (agent_type: `dmux-pane`, purpose: "Collected N results")

### How to log

Commands append entries using a pattern like:
```
Write one line to .claude/agent-log.jsonl:
{"timestamp":"[ISO]","command":"/research","agent_type":"general-purpose","model":"haiku","purpose":"[sub-question]","duration_estimate":"[fast|medium|slow]","outcome":"[success|error]","session_id":"[id]"}
```

Note: duration is estimated by the orchestrating command, not measured precisely. Use the guidelines above.

</details>
