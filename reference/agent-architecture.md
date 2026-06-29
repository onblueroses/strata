<!-- keywords: agent, pipeline, multi-agent, routing, memory, rag, circuit breaker, fallback chain, orchestrator, llm agent, agent loop -->
# Agent Architecture Patterns

Transferable patterns for building LLM-powered agents. Distilled from production
implementations (Qwen-Agent, Reddit agent, pipewright) and first principles.

Reference repos worth reading when designing new agents:
- **Qwen-Agent** (`github.com/QwenLM/Qwen-Agent`) - 14k+ stars, backs Qwen Chat production.
  Clean Python, good separation. Key files: `agent.py` (base class), `agents/fncall_agent.py`
  (tool loop), `agents/group_chat.py` (multi-agent routing), `memory/memory.py` (RAG-as-agent),
  `agents/keygen_strategies/` (query decomposition for retrieval).

---

## Quick Nav

| Task | Section |
|------|---------|
| Design agent memory / RAG | Core Patterns > Memory as Agent |
| Break down complex retrieval queries | Core Patterns > Query Decomposition |
| Inject retrieved context into prompts | Core Patterns > System-Message Injection |
| Route between multiple agents | Core Patterns > Agent Selection Strategies |
| Prevent infinite agent loops | Core Patterns > Cycle Protection |
| Build reliable agent pipelines | Production Patterns |
| Handle subagent failures gracefully | Production Patterns > Circuit Breaker Convention |
| Choose fallback models | Production Patterns > Fallback Chains |
| Log agent invocations | Production Patterns > Agent Observability Logging |
| Avoid common agent mistakes | Anti-Patterns |

---

## Core Patterns

<details>
<summary>Core Patterns</summary>

### 1. Memory as Agent (uniform interface)

Model memory/retrieval as an agent with the same `run()` interface as everything else.
Not a separate subsystem - just another composable unit.

```
# Instead of:
context = memory_store.retrieve(query)
response = agent.run(messages, context=context)

# Do:
memory_agent = MemoryAgent(retrieval_tools, llm)
context = memory_agent.run(messages)  # same interface
response = main_agent.run(messages + context)
```

**Why**: composability. You can swap implementations, chain memory agents, or use
memory as a sub-agent. In pipewright terms: RAG retrieval is just another node.

**Source**: Qwen-Agent `memory/memory.py` - Memory inherits from Agent.

### 2. Query Decomposition Before Search

Don't pass the raw user query to your search/retrieval system. Decompose first:

```
user_query
  -> LLM: split into sub-queries (what information is actually needed?)
  -> LLM: generate search keywords from each sub-query
  -> search engine gets targeted keywords, not raw natural language
```

Two LLM calls before retrieval. Expensive but dramatically improves recall on
complex questions. The keyword generation step is especially valuable for BM25-style
search (exact term matching).

**Where to apply**:
- Reddit agent Tavily search: decompose post content into targeted search queries
  instead of relying solely on category-based triggers
- example BM25 component: generate keywords from user query before hybrid search

**Source**: Qwen-Agent `agents/keygen_strategies/split_query_then_gen_keyword.py`

### 3. System-Message Injection for Retrieved Context

When an agent retrieves context (RAG, search results, memory), inject it into the
system message rather than returning it as a tool result in the conversation.

```
# Instead of:
tool_result: "Here are the relevant docs: ..."
# (competes with conversation flow, LLM may ignore it)

# Do:
system_message += "\n\nRelevant context:\n" + retrieved_docs
tool_result: "Context has been loaded into your instructions."
# (LLM pays most attention to system message)
```

**Why**: models weight system message content higher than mid-conversation tool
results. Especially effective for grounding facts that should influence the entire
response, not just the next turn.

**Where to apply**:
- Reddit agent: move `<expertenkontext>` from mid-prompt to system message and
  measure draft quality difference
- Any new RAG pipeline

**Source**: Qwen-Agent `agents/virtual_memory_agent.py`

### 4. Per-Agent Message Reformatting (Multi-Agent)

In multi-agent conversations, each agent should see the history from its own
perspective: its messages as `assistant`, everyone else's as `user` with name
prefixes.

```
# Raw history:
[agent_A: "I think...", agent_B: "But consider...", agent_A: "Good point..."]

# What agent_B sees:
[user: "agent_A: I think...", assistant: "But consider...", user: "agent_A: Good point..."]
```

**Why**: LLMs get confused about role boundaries in multi-agent setups. Reformatting
keeps the model clear about what it said vs. what others said.

**Source**: Qwen-Agent `agents/group_chat.py:_manage_messages()`

### 5. Cycle Protection with Call Budgets

Every agent loop needs a hard ceiling on LLM calls per run. Not just for cost -
prevents infinite loops when the model keeps calling tools without converging.

```
MAX_CALLS = 20  # Qwen-Agent default
while calls_remaining > 0:
    calls_remaining -= 1
    output = llm.call(messages)
    if no_tool_call(output):
        break
    # ... execute tool, append result, continue
```

Already in pipewright as `maxSteps`. Include in any new agent.

### 6. Agent Selection Strategies (Multi-Agent)

Four strategies for who speaks next, in order of complexity:

| Strategy | How | When |
|----------|-----|------|
| Round-robin | Fixed order | Structured workflows, pipelines |
| Manual/@mention | Explicit routing | User-directed, approval flows |
| Random | Random choice | Brainstorming, diversity |
| Auto (LLM-routed) | Ask LLM "who next?" | Open-ended conversations |

Plus a `[STOP]` signal for the router to end the conversation.
Most pipeline-style agents only need round-robin. Auto-routing is for chat.

</details>

---

## Production Patterns

<details>
<summary>Production Patterns</summary>

Lessons from running autonomous LLM pipelines. Complement the architectural
patterns above with operational concerns.

### 7. Grounding Chain: Search -> Reason -> Generate

Three-step pipeline for factual content:

```
search_engine(topic)      -> raw facts
reasoning_model(facts)    -> analysis: what matters, what's missing, what to address
generation_model(analysis) -> final output in target voice/format
```

Direct generation hallucinates. Search-only without reasoning can't synthesize.
The reasoning step (a thinking model like R1/QwQ) bridges raw facts to structured
analysis that the generation model can execute on.

**Source**: a drafting pipeline (web-search tool -> reasoning model -> generation model).

### 8. Model Specialization in Pipelines

Assign each pipeline step the right model class:

| Step | Model type | Why |
|------|-----------|-----|
| Scoring/classification | Cheapest (Haiku/Flash) | Binary or categorical, doesn't need reasoning |
| Analysis/reasoning | Thinking model (R1/QwQ) | Needs to synthesize, identify gaps, plan |
| Final generation | Fast generation model | Needs style control, persona voice, fluency |

A single model doing everything performs worse than specialized models per step.
Cost is also lower - cheap models handle the high-volume steps.

### 9. Fault-Tolerant Pipeline Steps

Each stage catches exceptions and continues with degraded output:

```
try:
    facts = search(topic)
except SearchError:
    facts = None  # generation model works without, just less grounded

try:
    analysis = reason(facts)
except ReasoningError:
    analysis = None  # generation model drafts without analysis step

output = generate(analysis or facts or topic)  # always produces something
```

Never let one failure kill the whole run. In an autonomous pipeline running on
a cron, silent degradation is better than complete failure - the next run will
likely succeed on different inputs.

### 10. Circuit Breaker Convention

When a subagent fails, don't immediately abort or silently continue. Use a
three-strike pattern:

```
Attempt 1: original model (e.g., opus)
  -> failure? retry once with same model
Attempt 2: same model, fresh context
  -> failure? fall back to cheaper model
Attempt 3: fallback model (e.g., sonnet for opus, haiku for sonnet)
  -> failure? abort and report to orchestrator
```

**When to apply**: any command that spawns subagents for work that CAN degrade
gracefully. Not for `/harness` (correctness requires opus) but yes for
`/research` (a haiku agent is better than no agent).

**What to report on failure**: which agent failed, on which attempt, with what
error. The orchestrating command includes this in its output so the user knows
what was lost.

### 11. Fallback Chains

Predefined degradation paths for model selection:

| Primary | Fallback | Use case |
|---------|----------|----------|
| opus | sonnet | Planning, evaluation tasks that can tolerate lower reasoning |
| sonnet | haiku | Research, code review where speed matters more than depth |
| haiku | (abort) | Already the cheapest - if haiku fails, the problem isn't the model |

Fallback is for transient failures (timeout, rate limit, context overflow), not
for quality failures. If an agent produces bad output, retrying with a weaker
model won't help - investigate the prompt instead.

### 12. Agent Observability Logging

Log every subagent invocation to `.claude/agent-log.jsonl` for analysis.
One JSON object per line, appended after each agent completes.

Schema and conventions documented in `$STRATA_HOME/reference/agent-taxonomy.md`
under the Observability section. Commands that spawn agents should append
entries with: timestamp, command, agent_type, model, purpose, duration_estimate,
outcome, session_id.

**What this enables (future)**:
- Token cost analysis per command and agent type
- Failure rate tracking per model tier
- Identifying commands that over-spend on agent count
- Framing effectiveness correlation (with harness-memory.json)

</details>

---

## Anti-Patterns

- **Memory as a special subsystem**: breaks composability. Make it an agent/node.
- **Raw query to search**: natural language queries underperform vs. decomposed keywords.
- **Unlimited tool loops**: model calls tools forever. Always set a budget.
- **Shared message history in multi-agent**: agents confuse their own output with others'.
- **Context in tool results only**: system message injection gets more attention from the model.
- **Single model for all pipeline steps**: specialized models per step outperform one-size-fits-all.
- **Hard failure on pipeline errors**: autonomous pipelines should degrade gracefully, not stop.
- **Hard abort on first subagent failure**: use the circuit breaker pattern - retry once, then fallback model, then abort.
- **No agent invocation logging**: without observability, you can't optimize agent usage or diagnose failures across sessions.
