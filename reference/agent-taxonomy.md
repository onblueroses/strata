<!-- keywords: subagent, spawn agent, which agent type, agent for the job, model selection, model tier, observability schema, agent logging, agent-log jsonl, ad-hoc agent pattern, cross-skill state, skill cache, delegate, dispatch, parallel subagents -->
# Agent Taxonomy

Central reference for all agent types available in the agent harness. Covers formal definitions
(`$STRATA_HOME/agents/`), ad-hoc patterns used in commands, and cross-agent infrastructure.

Read this before spawning subagents. Use the right agent for the job; the wrong agent type
wastes tokens and produces worse results.

---

## Quick Nav

| Task | Section |
|------|---------|
| Choose which agent type to spawn | Agent Types |
| Understand ad-hoc agent patterns in commands | Ad-Hoc Patterns |
| Share findings between skills | Cross-Skill State |
| Log agent invocations | Observability |
| Handle agent failures | Error Recovery (in `reference/agent-architecture.md`) |

---

## Agent Types

Formal agent definitions live in `$STRATA_HOME/agents/`. Each has YAML frontmatter with name, description, tools, and model. Model values below are capability tiers (small / mid / large); the concrete model bound to each tier is set per install.

| Agent | Model | Tools | Spawned by | Use when |
|-------|-------|-------|------------|----------|
| `knowledge-lookup` | small | Read, Grep, Glob | Any command needing entity data | Fast lookup in the `$KB_DIR/` knowledge base: entity summaries, items.json, daily notes, PARA structure. Not for analysis. |
| `quick-research` | small | WebSearch, WebFetch, Read | `/research` Simple tier, any quick lookup | Simple factual web lookups: docs, versions, definitions. Not for multi-step reasoning. |
| `code-reviewer` | mid | Read, Grep, Glob | Manual-only maintainability review | Apply the Fowler code-smell lens in `code-smell-baseline.md` with read/grep context. Complements the independent `breadth` review; correctness, security, and tests stay with `/review` and `/verify` F0. |

<!-- deep-researcher and pattern-extractor retired: zero dispatch callers. Web lookups route through quick-research; pattern extraction runs inline (an Explorer subagent plus an inline /evaluate phase); heavy research and analysis route to the external sub-model lanes. -->

`dmux-pane` is not a subagent; see the dmux Dispatch Panes entry under Ad-Hoc Patterns.

Large-diff specialist routing lives in `review-fanout.md`: `grader`-lane specialists cover file buckets while the independent `breadth` pass sees the whole diff.

### Model Selection Guide

| Task type | Model | Why |
|-----------|-------|-----|
| File reads, searches, simple lookups | small | Much cheaper, sufficient for retrieval |
| Moderate analysis, code review, research synthesis | mid | Needs reasoning but not the frontier |
| Planning, adversarial evaluation, architecture | large | Complex reasoning, high-stakes decisions |

**Rule of thumb**: if the agent just reads and returns, use the small tier. If it must reason about what it found, use the mid tier. If it must make decisions that are hard to reverse, use the large tier. If the task is independent implementation work that doesn't need to return into the parent's context, use a dmux pane (`/dispatch`) instead of a subagent.

---

## Ad-Hoc Patterns

<details>
<summary>Ad-Hoc Patterns</summary>

These aren't formal agent definitions but recurring patterns where commands spawn `general-purpose` or `Explore` agents with specific prompts.

### Explore Agents (`/deep-understand`)

- **Type**: `subagent_type: "Explore"`
- **Model**: small tier (small projects) or mid tier (medium/large projects)
- **Purpose**: Codebase familiarization: architecture, data flow, conventions
- **Pattern**: Pre-scan context block injected into each agent's prompt. Agents get focused areas (architecture, data, API, quality).
- **Batching**: Small = 3 parallel, Medium = 5 in 2 batches, Large = 8 in 3 batches

### Research Agents (`/research`)

- **Type**: `subagent_type: "general-purpose"` (Moderate) or `subagent_type: "general-purpose"` on the mid tier (Complex)
- **Model**: small (Moderate), mid (Complex)
- **Purpose**: Parallel web research on decomposed sub-questions
- **Pattern**: Each agent gets one sub-question + word budget. Results synthesized by the orchestrator.

### Generator/Evaluator Agents (`/harness`)

- **Type**: large-tier subagents (both generator and evaluator)
- **Model**: large (always; correctness stakes justify the cost)
- **Purpose**: Adversarial loop. Generator implements, evaluator judges with asymmetric information.
- **Pattern**: Evaluator never sees the task description or generator reasoning. Rotating adversarial framings break systematic bias. Fresh generation on failure, not patching.

### Plan Agents (`/spec`)

- **Type**: `subagent_type: "Plan"` on the large tier
- **Purpose**: Architecture and implementation planning
- **Pattern**: Receives full task description + exploration results + constraints. Returns plan content only. The orchestrator writes the spec file.

### dmux Dispatch Panes (`/dispatch`)

- **Type**: Independent agent sessions in git worktrees (NOT subagents; fully separate processes)
- **Model**: Any full-CLI agent session (each pane runs an independent CLI with its own context window)
- **Purpose**: Parallel implementation of independent tasks. Each pane gets its own worktree, branch, and context window.
- **Pattern**: Parent writes `.task-brief.md` (YAML frontmatter + structured sections), calls `dmux-dispatch.sh` to create the worktree + tmux pane. Child reads the brief, executes, writes `.task-result.md` via `/end`. Parent reads results via `/collect`.
- **When to use over subagents**: when the task can be fully specified upfront and the parent doesn't need the result in working memory. Default for implementation tasks. See the Delegation section in CLAUDE.md.
- **Communication**: filesystem only: `.task-brief.md` (parent->child), `.task-result.md` (child->parent), `.task-blocked.md` (child->parent), `.dmux/scratchpad/{slug}.md` (sibling->sibling).
- **Design doc**: `reference/dmux-dispatch-protocol.md`

</details>

---

## Cross-Skill State

<details>
<summary>Cross-Skill State</summary>

Skills can share findings via `$STATE_DIR/skill-cache.json`. This lets patterns extracted by one skill inform another.

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
| `/harness` | Reads patterns relevant to the task type, includes them in the generator's PROJECT CONSTRAINTS |
| Future agents | Can query for domain-specific grounding before starting work |

### Convention

- Append only. Never delete entries.
- Keep entries under 50. If over 50, the next writer should prune entries older than 90 days or with verdict `pass`.
- Always include the `skill` field so readers know the source context.

</details>

---

## Observability

<details>
<summary>Observability</summary>

Commands log agent invocations to `$STATE_DIR/agent-log.jsonl` for analysis. One JSON object per line, appended after each agent completes.

### JSONL Entry Schema

```json
{
  "timestamp": "2026-03-25T22:00:00Z",
  "command": "/research",
  "agent_type": "general-purpose",
  "model": "small",
  "purpose": "Research Redis vs Memcached tradeoffs",
  "duration_estimate": "fast",
  "outcome": "success",
  "session_id": "a1b2c3d4"
}
```

### Fields

| Field | Type | Values |
|-------|------|--------|
| `timestamp` | ISO 8601 | When the agent completed |
| `command` | string | Which command spawned this agent |
| `agent_type` | string | `knowledge-lookup`, `quick-research`, `code-reviewer`, `general-purpose`, `Explore`, `Plan` (use `dmux-pane` as a label when logging dispatches, even though it isn't a formal agent) |
| `model` | string | `small`, `mid`, `large` (the configured tier the agent ran on) |
| `purpose` | string | One-line description of what this agent was doing |
| `duration_estimate` | string | `fast` (<30s), `medium` (30s-2min), `slow` (>2min) |
| `outcome` | string | `success`, `error`, `timeout`, `partial` |
| `session_id` | string | 8-char session ID |

### When to log

- `/research`: log each research agent after completion
- `/verify`: log the subagent for Full/Deep tiers
- `/deep-understand`: log each Explore agent batch
- `/harness`: log generator and evaluator agents per iteration
- `/evaluate`: log the pattern-extraction pass
- `/dispatch`: log each dispatched pane (agent_type: `dmux-pane`, model: the CLI/agent name, duration: `slow`)
- `/collect`: log the collection run (agent_type: `dmux-pane`, purpose: "Collected N results")

### How to log

Commands append entries with a pattern like:
```
Write one line to $STATE_DIR/agent-log.jsonl:
{"timestamp":"[ISO]","command":"/research","agent_type":"general-purpose","model":"small","purpose":"[sub-question]","duration_estimate":"[fast|medium|slow]","outcome":"[success|error]","session_id":"[id]"}
```

Note: duration is estimated by the orchestrating command, not measured precisely. Use the guidelines above.

</details>
