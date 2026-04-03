# Research Skill

Adaptive research that scales effort to question complexity. Simple questions get direct answers; complex topics get parallel deep-dives.

## Usage

```
/research "topic or question"
/research --quick "topic"        # Force simple mode (direct search, no agents)
/research --deep "topic"         # Force complex mode (5 agents, thorough)
/research --export               # Save findings to .claude/research/
```

Arguments via `$ARGUMENTS`.

## Comparison Mode (X vs Y)

**Detection:** If the query contains "vs", "versus", or "compared to" between two identifiable subjects, activate comparison mode. This overrides normal complexity assessment.

**Three-pass research (pattern from last30days-skill):**

1. **Pass A + B (parallel):** Spawn two research agents simultaneously - one for subject A alone, one for subject B alone. Each researches its subject independently, capturing how that subject's community discusses itself. This yields richer signal than how each talks about its competitor.

2. **Pass C (sequential, after A+B):** Spawn one more agent researching "A vs B" directly. This captures the population of content that explicitly compares the two - a different set of sources than either individual pass.

3. **Synthesize all three passes:**

```markdown
## [A] vs [B]

### Quick Verdict
[1-2 sentences. Include source counts from each pass.]

### [A]
[Key findings from Pass A]

### [B]
[Key findings from Pass B]

### Head-to-Head
| Aspect | [A] | [B] |
|--------|-----|-----|
| [comparison axis from Pass C] | [finding] | [finding] |

### Recommendation
[Based on user's context, if applicable]

### Sources
[All sources from all three passes, deduplicated]

### Gaps
[What the comparison couldn't answer]
```

**Latency:** `max(t_A, t_B) + t_C` - not additive. Passes A and B run in parallel.

The three-pass structure replaces Phase 0 (Assess Complexity), Phase 1 (Decompose), and Phase 2 (Research). Phase 3 (Synthesize) is replaced by the comparison synthesis template above. Phase 4 (Follow-ups) still runs after synthesis. Use sonnet for comparison agents by default, or haiku with `--quick`.

---

## Instructions

### Phase 0: Assess Complexity (no agents)

Before spawning anything, classify the question complexity. Override with `--quick` (force simple) or `--deep` (force complex). Default classification: Simple (direct lookup, 1-3 searches), Moderate (multi-faceted, 2-3 agents), Complex (deep topic, 4-5 agents).

---

### Phase 1: Decompose (Moderate and Complex only)

Break the main question into sub-questions. Write them out before any searching.

Rules:
- Each sub-question must be independently answerable
- No overlap between sub-questions
- Together they fully answer the main question
- Moderate: 2-3 sub-questions
- Complex: 4-5 sub-questions

Example - "Best database for my Flask app":
1. What are the main database options for Flask? (SQLite, PostgreSQL, MySQL, MongoDB)
2. How do they compare on performance, complexity, and scaling?
3. What does the Flask/SQLAlchemy ecosystem recommend?
4. What's best at small scale vs when you need to scale later?

---

### Phase 2: Research

#### Simple mode (direct, no agents)

Do 1-3 WebSearch calls yourself with targeted queries. WebFetch the most authoritative result if detail is needed. Synthesize directly. Done.

#### Moderate mode (2-3 agents)

Launch all agents in a SINGLE message with parallel Task tool calls. **Permission profile: Explorer** (Read, Grep, Glob, WebSearch, WebFetch - no Edit/Write).

- `subagent_type: "general-purpose"`
- `model: "haiku"`
- Word budget: 200 words per agent

#### Complex mode (4-5 agents)

Launch all agents in a SINGLE message with parallel Task tool calls.

- `subagent_type: "general-purpose"`
- `model: "sonnet"`
- Word budget: 300 words per agent

#### Agent prompt template

```
Research this specific question: [SUB-QUESTION]

Context: Part of a larger research effort on "[MAIN_TOPIC]".

Instructions:
- Use 2-3 web searches with different angles
- Fetch the most relevant page for details if needed
- Prioritize: official docs > engineering blogs > benchmarks > Stack Overflow > Reddit/HN
- Note publication dates - flag anything older than 1 year

Return ([WORD_BUDGET] words max):
- Key findings (bullet points)
- Sources (URLs with one-line descriptions)
- Confidence: high / medium / low
- Any contradictions between sources

No preamble, no filler.
```

#### Error Recovery

If a research agent fails (error, timeout, empty output):
- **Moderate tier**: retry once with same model. If second failure, continue with remaining agents - partial results are better than none.
- **Complex tier**: retry once with same model. If second failure, retry with haiku (fallback). If third failure, continue without that agent and note the gap.

Never abort the entire research because one agent failed. Surface what was lost in the Gaps section.

#### Observability

After each agent completes (success or failure), append a log entry to `.claude/agent-log.jsonl`:
```
{"timestamp":"[ISO]","command":"/research","agent_type":"general-purpose","model":"[haiku|sonnet]","purpose":"[sub-question summary]","duration_estimate":"[fast|medium|slow]","outcome":"[success|error|timeout]","session_id":"[8-char-id]"}
```

---

## DO NOT

- Spawn agents for Simple-tier questions - it wastes tokens and adds latency for a 1-search answer
- Use `model: "sonnet"` for Moderate tier - haiku is sufficient and 10x cheaper; reserve sonnet for Complex
- Present raw agent outputs to the user - always synthesize into the structured format below
- Include sources you didn't actually read - only cite URLs whose content you (or an agent) fetched and verified
- Let agent contradictions silently disappear - if two agents disagree, surface both perspectives
- Research without checking local knowledge first - grep the codebase and memory files before web searching

---

### Phase 3: Synthesize

Combine findings into a coherent answer.

**Concrete test before presenting:** Cover the "Summary" section with your hand. Read only the "Key Findings" bullets. Do they make sense without the summary? If not, the findings are too vague - add specifics.

**Good vs bad synthesis:**

| Aspect | Bad | Good |
|--------|-----|------|
| Summary | "There are several options for caching in Flask" | "Redis is the best fit for Flask session caching at small scale - it's the only option with built-in Flask-Session support and sub-ms latency" |
| Finding | "PostgreSQL is popular" | "PostgreSQL handles concurrent writes 3x faster than SQLite (source: pgbench benchmarks), but requires a separate server process" |
| Recommendation | "It depends on your needs" | "For your Flask API with SQLite and <1000 daily users: keep SQLite. Switch to PostgreSQL when you hit connection contention (>50 concurrent writes/sec)" |
| Source | "Various online sources" | "Flask-Caching docs (https://example.com) - confirms Redis is the recommended backend for production" |

**Structure:**

```markdown
## [Research Topic]

### Summary
[2-3 sentences answering the main question]

### Key Findings

#### [Sub-topic 1]
- Finding with [source]

#### [Sub-topic 2]
- Finding with [source]

### Comparison (if applicable)
| Aspect | Option A | Option B |
|--------|----------|----------|

### Recommendation
Based on [user's context], ...

### Sources
- [Title](https://example.com) - what it contributed

### Gaps
- Couldn't find reliable data on [X]
- Sources disagreed on [Y]
```

**Quality checks before presenting:**
- Does this actually answer the original question?
- Are claims supported by cited sources?
- Are contradictions acknowledged?
- Is the recommendation actionable?
- Are sources recent enough? (flag if >1 year old)

---

### Phase 4: Follow-ups

Offer 2-3 specific deeper dives based on gaps or interesting threads that emerged.

---

## Export

If `--export` flag or user requests, save to `.claude/research/[topic-slug]-[YYYY-MM-DD].md`:

```markdown
# Research: [Topic]
Date: YYYY-MM-DD
Query: [Original question]
Complexity: [Simple/Moderate/Complex]
Agents: [count]

## Executive Summary
[Key takeaway]

## Findings
[Full synthesized findings]

## Sources
[All URLs]

## Follow-up Questions
[Unanswered or deeper questions]
```

---

## Examples

```
/research "what port does PostgreSQL use"
-> Simple: 1 web search, direct answer, no agents

/research "Redis vs Memcached for session storage"
-> Moderate: 2 agents (haiku) - one per technology's tradeoffs

/research --deep "best email API provider for transactional email"
-> Complex: 5 agents (sonnet) - players, pricing, deliverability, DX, reviews

/research --quick "microservices vs monolith"
-> Forced simple: 2-3 searches, concise summary, no agents
```
