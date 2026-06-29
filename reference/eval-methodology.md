<!-- keywords: eval, evaluation, benchmark, test, fixture, llm-as-judge, semantic, assertion, golden, trigger, benchmark-band, regression, predicate, judge, dataset, rubric -->
# Eval Methodology

How to build evaluators, eval fixtures, and benchmarks across projects. Defines the eval type taxonomy, assertion primitives, fixture formats, and common failure modes.

Companion to strata's `src/eval/` module. See `tier-classification.md` for risk tiers, `code-quality-principles.md` for test philosophy.

---

## Quick Nav

| Task | Jump to |
|------|---------|
| Pick the right eval type | Eval Types |
| Understand assertion primitives | Assertion Primitives |
| Write an eval fixture | Fixture Formats |
| Decide which type to use | Decision Flowchart |
| Structure a dataset | Dataset Design |
| Avoid common mistakes | Common Failures |
| Integrate with strata | Strata Integration |

---

## Eval Types

<details>
<summary>Eval Types</summary>

Five types, ordered from cheapest to most expensive to run. Pick the cheapest type that can detect the failure mode you care about.

| Type | What it checks | Cost | Strata status |
|------|---------------|------|---------------|
| **Trigger** | Did the right skill/tool fire? | Free (subprocess) | Implemented |
| **Behavioral** | Does output contain/not-contain specific content? | Free (string ops) | Planned (Phase 2) |
| **Benchmark** | Does a stochastic metric land in acceptable bands? | Low (N runs) | Planned (Phase 2) |
| **Semantic** | Does an LLM judge pass the output against natural-language criteria? | High (LLM call) | Planned (Phase 3) |
| **Regression** | Does output match a known-good baseline (snapshot)? | Medium (diff) | Future phase |

### Trigger

**Definition:** Verifies that a given input causes a specific tool or skill to be invoked (or not invoked). Binary pass/fail.

**Use when:** You need to test routing logic - "does this prompt cause the agent to call the right skill?"

**Example:** Query `"review my changes before committing"` should trigger the `review` skill. Query `"what time is it"` should not.

**Strata:** `EvalQuery.should_trigger: bool` + `ClaudeCodeBackend.test_trigger()`.

---

### Behavioral

**Definition:** Verifies structural properties of the output using deterministic string operations. No LLM needed.

**Use when:** You can specify the test as "output must contain X" or "output must not mention Y." Works for format compliance, required keywords, forbidden phrases.

**Example:** A commit message generator's output must contain a verb in the subject line. A privacy-aware response must not contain PII patterns.

**Strata:** `EvalQuery.assertions: Vec<Assertion>` with `AssertionKind::Contains` / `NotContains` / `Regex`.

---

### Benchmark

**Definition:** Runs the same query N times, aggregates a numeric metric, and checks it falls within a `{min, target, tolerance}` band.

**Use when:** The output is stochastic and you care about average quality rather than any single run. Metrics like accuracy, trigger rate, score distribution.

**Example:** A skill's trigger rate on "should trigger" queries must be ≥ 0.80 (min) with target 0.90.

**Strata:** `EvalQuery.benchmark_band: Option<BenchmarkBand>` + `EvalQuery.pass_threshold: Option<f64>`.

---

### Semantic

**Definition:** An LLM judge evaluates the output against one or more natural-language criteria. Returns `passed: bool` + `justification: String` per criterion.

**Use when:** Quality is subjective or structural checks aren't expressive enough. "The explanation should be concise and avoid jargon" cannot be checked with a regex.

**Example:** A code review output must "identify the most critical issue without nitpicking style" - only a judge can assess this.

**Strata:** `EvalQuery.assertions` with `AssertionKind::LlmJudge(criterion)` + `ClaudeCodeBackend.judge_output()`.

**Key rule:** Configure the judge model separately from the tested model (different temperature, different instance). Prevents the model from judging its own outputs.

---

### Regression

**Definition:** Stores a known-good output as a golden file; future runs diff against it. Fails on unexpected change.

**Use when:** You have a verified correct output and want to detect regressions. Useful for deterministic transformations (formatters, linters, code generators with fixed inputs).

**Strata:** Not yet implemented. Planned as a future phase.

**Gap note:** Neither lm-evaluation-harness nor Braintrust have built-in snapshot regression testing - this is a genuine gap in the ecosystem.

</details>

---

## Assertion Primitives

<details>
<summary>Assertion Primitives</summary>

An `Assertion` has a `kind`, an optional `weight` (default 1.0), and is evaluated against the LLM's output string.

### AssertionKind variants

| Kind | Signature | Evaluated by | Example |
|------|-----------|-------------|---------|
| `Contains(String)` | Output must contain substring | String search (free) | `Contains("Error:")` |
| `NotContains(String)` | Output must not contain substring | String search (free) | `NotContains("TODO")` |
| `Regex(String)` | Output must match regex pattern | Regex engine (free) | `Regex("^#\\s+\\w+")` |
| `LlmJudge(String)` | Output must satisfy natural-language criterion | LLM subprocess (expensive) | `LlmJudge("mentions the root cause without suggesting a workaround")` |

**Design rule (from verifiers):** Deterministic assertions (`Contains`, `NotContains`, `Regex`) are evaluated inline without any LLM call. Only `LlmJudge` assertions trigger a subprocess. Mix both kinds freely - the runtime separates them automatically.

### Weight and pass_threshold

`weight` controls how much each assertion contributes to the overall pass decision. `pass_threshold` on the query sets the fraction of weighted assertions that must pass (default: all must pass).

```json
{
  "query": "write a commit message for this diff",
  "should_trigger": true,
  "pass_threshold": 0.75,
  "assertions": [
    { "kind": { "Contains": "feat" }, "weight": 1.0 },
    { "kind": { "NotContains": "WIP" }, "weight": 2.0 },
    { "kind": { "LlmJudge": "subject line is under 72 characters and uses imperative mood" }, "weight": 1.5 }
  ]
}
```

Here, weighted total = 4.5. Pass threshold 0.75 requires 3.375 weighted points. If the `NotContains` (weight 2.0) and `LlmJudge` (weight 1.5) pass, total = 3.5 > 3.375 → passes even if `Contains` fails.

### Assertion composition rules

- **Use `Contains`/`NotContains` first.** Promote to `LlmJudge` only when string matching is too rigid.
- **One criterion per `LlmJudge`.** A judge cannot reliably evaluate two independent qualities in one assertion. Split them.
- **Negative assertions are as important as positive.** Test what the output should NOT do or say.
- **Don't make assertions tautological.** `Contains("")` always passes. `LlmJudge("is a valid response")` always passes.

</details>

---

## Fixture Formats

<details>
<summary>Fixture Formats</summary>

Fixtures live in JSON files. One file = one eval set for one skill. Arrays of `EvalQuery` objects.

**Design rule (from verifiers):** Fixtures store inputs and expected properties only. Scoring logic lives in the backend/rubric, not in the fixture. A fixture file should be readable by a human without understanding the eval framework.

### Trigger-only (minimal)

```json
[
  { "query": "review my staged changes", "should_trigger": true, "category": "direct" },
  { "query": "what is 2 + 2", "should_trigger": false, "category": "unrelated" },
  { "query": "can you check my code before I commit", "should_trigger": true, "category": "indirect" }
]
```

### With behavioral assertions

```json
[
  {
    "query": "write a function that adds two numbers",
    "should_trigger": true,
    "assertions": [
      { "kind": { "Contains": "def " } },
      { "kind": { "NotContains": "TODO" } },
      { "kind": { "Regex": "def \\w+\\(.*\\):" } }
    ]
  }
]
```

### With benchmark band

```json
[
  {
    "query": "refactor this function for readability",
    "should_trigger": true,
    "benchmark_band": { "min": 0.70, "target": 0.85, "tolerance": 0.05 }
  }
]
```

`min`: hard floor (fail below this). `target`: goal. `tolerance`: acceptable deviation from target in either direction before flagging as degraded.

### Combined: assertions + semantic + threshold

```json
[
  {
    "query": "explain why this test is failing",
    "should_trigger": true,
    "pass_threshold": 0.67,
    "assertions": [
      { "kind": { "NotContains": "I don't know" }, "weight": 2.0 },
      { "kind": { "LlmJudge": "identifies a specific cause, not just restates the error message" }, "weight": 1.0 },
      { "kind": { "LlmJudge": "suggests a concrete next step" }, "weight": 1.0 }
    ]
  }
]
```

### File naming convention

```
skills/
  review/
    eval-set.json          # primary eval set (used by optimizer)
    eval-set-edge-cases.json   # supplemental sets
    eval-set-negatives.json
```

Keep supplemental sets separate so the optimizer's train/test split isn't contaminated by hand-curated edge cases.

</details>

---

## Decision Flowchart

<details>
<summary>Decision Flowchart</summary>

```
Can you write a deterministic check for this failure mode?
│
├── Yes: Is it "did the right tool fire"?
│         ├── Yes → Trigger eval (EvalQuery.should_trigger)
│         └── No: Is it "output contains/doesn't contain X"?
│                   ├── Yes → Behavioral eval (AssertionKind::Contains/NotContains/Regex)
│                   └── No: Is there a numeric metric you care about?
│                             ├── Yes → Benchmark band (EvalQuery.benchmark_band)
│                             └── No → ??? (see below)
│
└── No: Is the quality judgment subjective or hard to specify precisely?
          ├── Yes → Semantic eval (AssertionKind::LlmJudge)
          └── No: Can you record a known-good output to diff against?
                    ├── Yes → Regression / golden file (future phase)
                    └── No → You may not have a testable requirement yet.
                              Write down what "correct" looks like first.
```

**Rule of thumb:** If you find yourself writing a `LlmJudge` assertion that starts with "is a good" or "is correct" - stop. That's the tautological trap. Make the criterion specific: *what* makes it good? Write that instead.

**When to mix types:** A single query can combine all types. Trigger + behavioral + semantic is common: verify routing, then check structural properties cheaply, then use the judge only for the nuanced quality check.

</details>

---

## Dataset Design

<details>
<summary>Dataset Design</summary>

### Minimum set sizes

| Eval type | Minimum examples | Recommended | Rationale |
|-----------|-----------------|-------------|-----------|
| Trigger | 20 | 40+ | Train/test split needs at least 12/8 for meaningful accuracy |
| Behavioral | 10 | 20+ | Deterministic - smaller sets are fine |
| Benchmark | 5 | 10+ | Run each N=3 times minimum; statistical noise matters |
| Semantic | 10 | 15+ | LLM judge has variance; need enough to distinguish signal from noise |

### Class balance

For trigger evals: aim for 40-60% positive (`should_trigger: true`). Heavily imbalanced sets (90% positive) make false-negative rates invisible.

For behavioral/semantic: include both "good output" and "bad output" examples. If all your examples test what the output should contain, you're not testing what it should reject.

### Category coverage

Use `category` to tag examples by the kind of trigger or failure mode. Run per-category accuracy to diagnose which category is weak, not just overall accuracy.

Common categories: `direct` (explicit request), `indirect` (implicit), `negative` (should not trigger), `edge-case` (boundary behavior), `adversarial` (attempts to mislead).

### Deterministic splits

Always use a fixed seed when splitting. Strata's `split_eval_set` uses LCG with seed parameter - pass the same seed for reproducible splits across optimization iterations. Changing the seed changes which examples land in train vs test, potentially inflating reported improvement.

### Handling stochastic outputs with `repeats`

For benchmark evals, run each query `repeats: N` times (minimum N=3, recommended N=5). A single run result is noise. Report the mean and whether it falls in the benchmark band.

### Keep fixture files clean

Never store runtime outputs (actual LLM responses) in fixture files. Fixtures are static inputs + expected properties. Runtime outputs belong in eval result logs, not committed JSON.

</details>

---

## Common Failures

<details>
<summary>Common Failures</summary>

### 1. Exact-match brittleness

**Problem:** Testing `output == expected_string` when the output is generated text. Fails on trivial rephrasing that preserves correctness.

**Mitigation:** Use `Contains` for required keywords, `LlmJudge` for semantic correctness. Reserve exact match for deterministic code generation with fixed inputs (regression tier).

---

### 2. Tautological assertions

**Problem:** Assertions that always pass regardless of output quality. `Contains("")`, `LlmJudge("is a helpful response")`, `NotContains("zzz")`.

**Detection:** Run your assertions against a known-bad output. If they still pass, the assertions are tautological.

**Mitigation:** Every assertion must be falsifiable. Write the bad output you're trying to prevent, then write the assertion that catches it.

---

### 3. Missing negative examples

**Problem:** All examples test what should happen. No examples test what should NOT happen. Result: a model that always fires passes all tests.

**Mitigation:** At least 30% of trigger eval examples should be `should_trigger: false`. For behavioral evals, include examples with deliberately bad outputs that should fail assertions.

---

### 4. Judge agrees with bad outputs

**Problem:** The LLM judge is too lenient. Assigns `passed: true` to outputs that clearly fail the criterion.

**Detection:** Feed known-bad outputs through the judge and check the `justification` field. If the judge is making excuses, recalibrate.

**Mitigation:** Make judge criteria concrete and negative: "does NOT suggest workarounds when the root cause is unknown" is harder to pass than "addresses the root cause." Use a separate judge model, not the same model that generated the output.

---

### 5. Stochastic undersampling

**Problem:** Running each query once for a benchmark eval. A single run can be an outlier.

**Mitigation:** Minimum N=3 runs per query for benchmark evals. Use `benchmark_band.tolerance` to encode the acceptable variance range.

---

### 6. Train/test contamination

**Problem:** Using the same examples for both optimizer training and final evaluation. The optimizer overfits to the train set; test accuracy looks artificially high.

**Mitigation:** Strata's `split_eval_set` separates train/test with a deterministic seed. Never manually add examples to the test set that were inspired by observing failures during training.

---

### 7. Single-dimension coverage

**Problem:** All assertions test the same dimension (e.g., all check for a specific keyword). A model that includes that keyword regardless of actual quality passes every assertion.

**Mitigation:** Use category tags. Ensure assertions cover orthogonal dimensions: structural (format, length), content (required elements), quality (semantic correctness), safety (forbidden outputs).

</details>

---

## Strata Integration

<details>
<summary>Strata Integration</summary>

### Current state (v0.2.0)

Strata's eval system (`src/eval/`) currently implements trigger testing only:

```
strata skill eval <skill-name> --eval-set path/to/eval-set.json
strata skill optimize <skill-name> --eval-set path/to/eval-set.json
```

### Planned extensions (eval-methodology spec)

**Phase 2** adds typed assertion schema to `EvalQuery`:

```rust
pub struct Assertion {
    pub kind: AssertionKind,     // Contains/NotContains/Regex/LlmJudge
    pub weight: f64,             // default 1.0
}

pub enum AssertionKind {
    Contains(String),
    NotContains(String),
    Regex(String),
    LlmJudge(String),           // natural-language criterion
}
```

**Phase 3** adds `judge_output()` to `EvalBackend`:

```rust
fn judge_output(
    &self,
    output: &str,
    assertions: &[Assertion],
    timeout: Duration,
) -> Result<Vec<SemanticResult>>
```

Deterministic assertion kinds (`Contains`, `NotContains`, `Regex`) are evaluated inline - no subprocess. Only `LlmJudge` triggers a Claude subprocess call.

### Config: separate judge model

The `[skills]` section of `strata.toml` has a `model` field used for both optimization and judging. When running semantic evals, set this to a different model than the one generating the outputs being tested.

```toml
[skills]
eval_backend = "claude-code"
model = "<PICK_CHEAP_PARALLEL>"   # cheap model for judging (the grader lane)
```

### Fixture location convention

```
<project-root>/
  skills/
    <skill-name>/
      SKILL.md
      eval-set.json             # primary (used by optimizer)
      eval-set-negatives.json   # supplemental
```

Or for strata-managed projects:

```
.strata/
  skills/
    <skill-name>/
      eval-set.json
```

</details>
