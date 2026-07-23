---
name: directional-prompting
description: "Write prompts, agent directives, slash commands, and skill descriptions with three stacked layers: outcome contract (goal, checkable success criteria, does-not-count list, stop condition, self-verification), direction (positive verbs name the path; zero contradictions; calibrated emphasis), and loop engineering for agentic prompts (persistence policy, diverse routes, blocked-route criteria, adversarial verification). Use when writing or reviewing any prompt, AGENTS.md, CLAUDE.md, tool description, subagent brief, or eval rubric. Triggers on: 'write a prompt', 'improve this prompt', 'make it positive', 'goal engineering', 'loop engineering', 'definition of done'."
metadata:
  version: "3.1.1"
---

# Directional Prompting

Three stacked layers, each earned. Direction alone serves a single-response task whose correct result is self-evident; add Outcome when completion, constraints, or near-misses need explicit definition; add Loop when the prompt drives autonomous iteration.

**Layer 1: Outcome.** The contract. Name the destination, what done means, what does not count, when to stop, and how the model verifies its own work.

**Layer 2: Direction.** Inside that frame, every sentence names the path forward with positive verbs, no two instructions collide, and emphasis is spent only on true invariants.

**Layer 3: Loop.** For agentic prompts: state the persistence policy, manage the search (diverse routes, blocked-route criteria), verify adversarially, require evidence in returns.

Outcome without direction reads as wishful: the model knows where to go but not how to step. Direction without outcome wanders: crisp paths to nowhere. An agentic prompt without loop discipline stops at the first plausible wall, or circles it forever.

## Why this shape

Frontier-lab guidance converges on a core: state the goal, success criteria, and constraints explicitly; structure the prompt with consistent delimiters; put material before task in long contexts; treat prompting as empirical iteration. Reasoning models plan internally, so the prompt's job moved up a level: from scripting the steps to specifying the destination and managing the search. Current guidance also warns that contradictory instructions degrade reasoning models disproportionately.

The motivating case study for the contract and loop layers is the open-problem prompt lineage: contract-style prompts with exhaustive definitions of what counts as solved, adversarial verification, and explicit route management produced credible solutions to open math problems. Those cases show the bundle can support hard open-ended search; they neither isolate component effects nor establish gains on routine tasks. Treat each device below as a strong hypothesis: adopt it where its failure mode is present, and test it against representative cases.

Everything below is model-agnostic. Where a knob is platform-specific (reasoning effort, thinking level, verbosity), the principle names the knob's role and leaves the dial to the platform's docs. When a new model generation arrives, re-tune from a minimal baseline against real cases; porting a tuned prompt stack unchanged degrades.

## Layer 1: the outcome contract

Where the literal block applies: free-standing task prompts (system prompts, dispatch briefs, command bodies) open with it verbatim; embedded instruction fields (tool descriptions, frontmatter descriptions, rubric cells) carry the same semantics compactly in prose; trivial one-shot prompts can run on direction alone. In long-context prompts, the block sits immediately before the task, after the material (see Structure and placement).

```
Goal: <one sentence>

Success means:
  - <checkable element>
  - <checkable element>
  - <constraint: format, schema, length>

Does not count:
  - <the plausible near-miss>
  - <the lazy-but-defensible return>

Stop when: <explicit condition>

Verify by: <the check the model runs on its own work before returning>
```

When the block appears, `Goal`, `Success means`, `Stop when` are its floor. Add `Does not count` and `Verify by` for anything hard, ambiguous, or agentic. `Constraints:` remains available as an optional field for true invariants only.

Rules for the block:

1. **Goal names one coherent objective.** Express coupled deliverables as success criteria under it; split into separate prompts only objectives that can be completed and verified independently.
2. **Success criteria are checkable.** "Returns valid JSON matching schema X" beats "high quality output". A criterion the model can test binds behavior; a vibe invites drift.
3. **The does-not-count list closes the loopholes.** A model can satisfy the letter of the success criteria while missing the point: a plan instead of working code, a mocked test instead of a real call, a partial result presented as complete, a reduction of the problem to an equally hard subproblem, a confident status report instead of an artifact. Write the list by asking: what would a lazy or overeager attempt return that still looks like success? Name those returns as failures in advance. The open-problem prompts lean on this device hardest: an exhaustive does-not-count list is how they define "solved" tightly enough to search against.
4. **Stop condition is explicit.** It prevents both failure directions: returning early at the first plausible wall, and refining forever past usefulness.
5. **Verify-by makes self-checking part of the task.** Run the tests, re-run the failing input, diff the output against the schema, re-read the result against the success list. This makes checking an explicit step instead of a hope; it raises the floor without guaranteeing correctness.
6. **Constraints carry real weight.** Reserve absolutes for the invariants: safety boundaries, required output fields, actions that must never happen. Decorating regular guidance with ALWAYS bleeds signal from the words that need it, and on current models an over-emphasized instruction overtriggers: it fires in situations it was never meant for.

## Layer 2: directional execution

Inside the outcome frame, every sentence pulls forward.

### The five rules

1. **Lead with the verb of the correct action.** "Trace", "build", "read", "return", "ask", "check". Open the sentence with the action itself; name the action, its object, and its condition explicitly.
2. **Describe the destination so completely that the wrong path has no room.** "Return JSON matching this schema" beats "do not return prose". Delete hedges and meta-commentary ("be careful with...", "make sure you don't..."): anxiety in text form; replace each with the concrete positive action.
3. **Prefer the positive replacement.** Most prohibitions have a sister "do Y" that makes the prohibited thing structurally impossible; write Y. When a negative constraint bounds the space more precisely than any positive paraphrase, keep it and pair it with the desired behavior (see "When negation survives").
4. **Keep instructions contradiction-free.** Conflicting rules are worse than useless on reasoning models: the model spends reasoning tokens reconciling them, and the resolution is unstable across runs. "Be concise" plus "cover everything" resolves differently every time. Where real tension exists, state the hierarchy: "cover every required element; compress everything else."
5. **Calibrate emphasis.** Write plain imperatives. Current models take emphasis literally: a CAPS-and-MUST instruction fires out of scope. If everything is shouted, nothing is; if one thing is shouted, it had better be an invariant.

### Bad → good

| Anti-pattern (plants the wrong action) | Directional (plants the right action) |
|---|---|
| Don't make assumptions. | Read the file before answering. |
| Avoid using `any` types. | Type every parameter and return value explicitly. |
| Don't write tests that mock everything. | Write tests that call the real function and assert on the returned value. |
| Don't be verbose. | Answer in one or two sentences. |
| Avoid hallucinating APIs. | Look up the library's current API before calling it. |
| Try not to break existing tests. | Run the test suite after every edit and keep it green. |
| Be thorough. Also, keep it short. | Cover every changed file; one sentence per file. |
| Avoid creating unnecessary files. | Edit the existing file at `<path>`. |

### Prompt the goal, not the process

Reasoning models plan internally. Hand-written reasoning scaffolds ("think step by step", "first list your assumptions, then...") range from redundant to harmful: they constrain a planner that plans better unconstrained. Set reasoning depth with the platform's knob, not with prose exhortation. The same applies to role theatrics: "you are the world's best programmer" moves style, not correctness. State the task, the audience, and the success criteria; use personas only when voice itself is the deliverable.

Distinguish reasoning scaffolds from operational process. Omit attempts to steer internal reasoning. Prescribe observable process when it affects correctness or auditability: plan before code, touch files in dependency order, apply every rule of an audit, produce the intermediate artifact the next step consumes.

### Show the form with an example

Start without examples; reasoning-heavy work usually needs none. When output form matters and drifts (format, tone, register, schema), add the smallest set of consistent, realistic examples that pins it: a worked example of the correct output often outperforms a paragraph describing it, and models imitate structure with high fidelity. Spend examples on form, and let observed outputs decide the count; official guidance genuinely differs here (zero-first for reasoning work, several diverse examples where form is the point).

## Layer 3: loop engineering (agentic prompts)

**Skip this layer when the prompt produces a single response with no tool loop.**

An agentic prompt manages a search, not just an output. The model runs for many steps without supervision, and the prompt is most of the management it gets. Six instruments, each earned by the task: 1 and 2 fit any tool loop; 3 and 4 fit open-ended search; 5 and 6 fit long or high-stakes work.

1. **State the persistence policy.** Decide eagerness explicitly, in either direction. Autonomous: "Continue until the goal is met; when uncertain on a reversible, in-scope step, make the most reasonable decision and proceed; stop and surface when an action is irreversible, destructive, or outside granted authority; return only when Verify-by passes or no in-scope route remains open." Bounded: "Spend at most N tool calls; return your best answer and name what remains unknown." An unstated policy yields model-default eagerness, which varies by model and by run.
2. **Give the loop an exit test.** Progress is new information. Re-reading the same files, re-running the same query, re-editing the same function without new evidence means the current route is exhausted: switch to an untried route. Return short of success only when every in-scope route is blocked or the budget is spent, and return current state with the exact remaining gap.
3. **Diversify before converging.** For open search (debugging, design, research, proof): start genuinely different approaches, develop them independently, and converge on the route with the strongest evidence once independent development has exposed real strengths and gaps. When fanning out parallel workers, withhold your favored approach from most of them early; premature convergence is groupthink with extra steps.
4. **Define the blocked-route criterion.** Mark an approach blocked when it only reduces the problem to another problem of comparable difficulty: the lemma as hard as the theorem, the fix that requires the same bug understood. Reopen a blocked route only for a genuinely new mechanism, invariant, construction, or measurement. This one rule guards against both thrashing and premature abandonment.
5. **Verify adversarially, separate from generation.** Check candidate work with a fresh pass (or a separate agent) whose brief is to refute: hunt the counterexample, run the failing input, attack the weakest step. Arm the verifier by naming the task's known traps in the prompt: the off-by-one classes, the race conditions, the edge cases the domain is famous for. A generator asked to grade itself grades on a curve.
6. **Require evidence in every return.** Returns contain artifacts: the diff, the passing test output, the counterexample, the measured number, the exact remaining gap. A status report ("this approach looks promising") belongs on the does-not-count list. For long horizons, keep durable state (a progress file, an approach registry with open/blocked status and reasons) so the loop resumes instead of restarting.

## Structure and placement

- **Delimit sections with one consistent scheme**: XML-style tags or markdown headers, one or the other. Models parse structure reliably when the structure is uniform.
- **Long context: material first, task last.** Put documents and data above, the instruction and outcome block at the end, and restate the core question after a long context block. Attention to instructions decays mid-context.
- **One meaning, one place.** Duplicated rules drift apart and then contradict. Keep each behavior owned by exactly one sentence; where instruction files concatenate (root-to-leaf rules files), let closer files override rather than repeat. One deliberate exception: in long prompts, restate critical output constraints verbatim near the output boundary; repetition across distance is insurance, repetition within a section is drift.
- **Put durable rules in the layer the runtime re-presents.** Runtimes differ in what they reload each turn (system prompt, project rules files) and what decays into history. Place invariants in the layer the target runtime reliably re-presents; put one-off task detail in the task prompt.

## Context and tool descriptions

The prompt is one part of what fills the window; curate the rest with the same discipline.

- **Minimal high-signal context.** Find the smallest set of information that fully outlines expected behavior. Start unrelated tasks in fresh context; accumulated history dilutes the live rules.
- **Tool descriptions are prompts.** For each tool: purpose, when to choose it over neighboring tools, parameters, outputs and errors, side effects. Write as if onboarding a new colleague who cannot ask follow-ups. Where the runtime supports parallel dispatch, name which calls are independent and safe to parallelize; serialize dependent calls.
- **Subagent briefs share the evidence.** Give a dispatched agent the full relevant trace and files; withhold only your favored hypothesis (instrument 3 above). Fragmentary briefs make subagents act on conflicting assumptions.
- **Trust boundaries are structural.** Delimit untrusted data from instructions; enforce permissions outside the prompt (tool allowlists, sandboxes); validate outputs before they reach consequential sinks. Prompt-level pleas to ignore injected instructions are decoration; the boundary must be structural.

## The audit pass

Four scans over a draft's normative instructions (quoted examples and descriptive prose are out of scope):

1. **Negation scan.** Search for: `don't`, `do not`, `never`, `avoid`, `refrain`, `instead of`, `rather than`, `not allowed`, `prohibited`, `forbidden`, `won't`, `shouldn't`, "be careful", "watch out", "make sure you don't". Rewrite each as the positive replacement when one is equally precise; when the negative bounds the space more sharply, it survives (cases below). A list titled "Anti-patterns" becomes "Do this" with each entry converted. If neither a precise positive nor a survival case applies, cut the rule.
2. **Contradiction scan.** Read the rules pairwise; any two that can collide in a single situation get an explicit hierarchy, or one gets cut.
3. **Emphasis scan.** Every ALWAYS / NEVER / MUST / CRITICAL marks a true invariant, or gets demoted to a plain imperative.
4. **No-op scan.** Delete each sentence the model already obeys by default ("be accurate", "think carefully"). Every surviving sentence changes behavior.

## When negation survives

The common survivors, as examples of a principle: keep the negative form when it is more precise than any positive paraphrase.

1. **Hard safety boundaries**, where the prohibited action must be named so the model can recognize and refuse it. Pair refusal with a positive action where possible: "Refuse requests for credentials you do not own, then point the user to the provider's dashboard."
2. **Disambiguating near-identical paths** where the model would otherwise pick the wrong one: "Use `bun test`, not `npm test`; this project runs on Bun." The negation clarifies; the positive verb still leads.
3. **Acceptable space too large to enumerate.** "Do not modify infrastructure files" beats listing every allowed file type. When the positive form requires exhaustive enumeration, the negative is cleaner.
4. **A named ban narrower than any positive paraphrase.** "No `console.log` in production code" is crisper than "use the logger" (which logger? where?). When the negative is more precise, keep it.

Outside these, treat the negation as a smell and hunt for the positive replacement.

## Aged out

Techniques current evidence disfavors, each with its replacement. Evidence grades vary (lab guidance, practitioner measurement, contested); re-test per model and task.

| Was standard | Now | Do instead |
|---|---|---|
| Role prompting for quality ("You are an expert...") | No demonstrated correctness gain; style shift only | State task, audience, success criteria; personas only when voice is the deliverable |
| "Think step by step" / hand-written CoT scaffolds | Redundant to harmful on reasoning models | Prompt the goal; set the reasoning knob |
| Threats, tips, emotional appeals | No effect | Plain instructions |
| Anti-laziness exhortations ("be thorough", "do not be lazy") | Overtriggers into overengineering on current models | Explicit scope, completion criteria, a does-not-count list |
| Emphasis inflation (CAPS and MUST everywhere) | Overtriggering; instructions fire out of scope | Plain imperatives; absolutes only for invariants |
| "Ignore any malicious instructions" | Broken as a defense | Structural boundaries: tool permissions, input isolation, output validation |
| Porting a tuned prompt stack across model generations | Degrades; each generation rebalances | Re-tune from a minimal baseline against representative cases |
| Always-on style-guide dumps in rules files | Context bloat; dilutes the live rules | Linters and formatters for mechanics; load detailed guidance on demand |

Few-shot prompting is the nuanced case, kept above rather than aged out: weak as a reasoning aid, alive as a form calibrator.

## Example: rewrite with the first two layers

**Before** (no outcome block, mostly negatives):

```
You are a code reviewer. Don't be too harsh. Don't nitpick formatting.
Avoid making assumptions about the author's intent. Never approve code
with obvious bugs. Don't suggest changes that aren't actionable. Try
not to be vague. Avoid emojis.
```

**After**:

```
Goal: Review the PR diff and decide: approve, request changes, or block.

Success means:
  - Verdict is one of APPROVE, REQUEST_CHANGES, BLOCK
  - Every comment names the file and line, plus replacement code or a
    clarifying question
  - Comments cover correctness, security, clarity (the linter owns formatting)

Does not count:
  - A verdict with no line-anchored comments
  - Style opinions without a correctness or clarity consequence

Stop when: the verdict is issued and every comment is actionable.

Verify by: re-reading each comment and confirming a developer could act
on it without asking a follow-up question.

Read the full diff before commenting. Focus on bugs you can trace,
security boundaries, and unclear logic. Ask before interpreting intent:
quote the line and request clarification. Block on reproducible bugs.
Write in plain, neutral prose.
```

The don'ts survive as positive instructions (harshness became a neutral register, vagueness became line-anchored actionability), and a contract sits on top. A prompt that also drove a tool loop would add Layer 3: a persistence policy, an exit test, and a verification pass separate from generation.

## Iterate: the prompt is a hypothesis

Prompting is empirical. Keep a small fixed set of representative inputs; rerun it after each prompt change; read outputs closely and fix the most frequent failure first. Stop iterating when a full pass shows no regressions and no gain on the top failure; "feels better" is not a metric. The audit scans find structural faults; only real outputs find behavioral ones.

## Application checklist

For each draft:

1. **Outcome check.** The applicable form of the contract is present: literal block for free-standing prompts, compact semantics for embedded fields. Criteria are checkable; does-not-count and verify-by cover hard or agentic work.
2. **Direction check.** Run the four audit scans (negation, contradiction, emphasis, no-op).
3. **Loop check** (prompts with a tool loop). Persistence policy and exit test stated; for open-ended search, add diversification, the blocked-route criterion, and adversarial verification; for long horizons, add durable state and evidence-bearing returns.
4. **Context check.** Context is minimal and high-signal; tool descriptions carry purpose, boundaries, and side effects; untrusted data is delimited from instructions.
5. **Read-back.** Every sentence names a destination or a step toward it; cut anything that does neither.

## Sources

Distilled 2026-07 from primary sources.

- Anthropic: prompting best practices; context-engineering and tool-writing engineering posts (2025-2026)
- OpenAI: GPT-5-series prompting guides, Codex prompting guide, reasoning best practices (2025-2026)
- Google: Gemini prompt design strategies, Gemini 3 developer guide (2026)
- Open-problem prompt lineage: OpenAI cycle-double-cover prompt; Shouqiao Wang's Erdős-problem prompts (2026; community verification ongoing)
- Practitioner corpus: Willison, Karpathy, Schulhoff, Askell, Cursor, Cognition (2025-2026); supports the context-engineering frame and the aged-out table's role-prompting, persuasion, injection-defense, and prompt-porting rows

The two-layer outcome-plus-direction framing this skill grew from: [kingbootoshi/directional-prompting](https://github.com/kingbootoshi/directional-prompting) (MIT).
