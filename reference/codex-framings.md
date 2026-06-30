<!-- keywords: codex framings, adversarial review, plan review, hypothesis review, architecture review, codex-review, framings -->
# Codex Adversarial Framings (Plan / Hypothesis / Architecture)

Adversarial framings used by `/codex-review` for non-diff artifacts. Each framing is a one-paragraph preamble injected at the top of the Codex prompt to shift its perspective and break systematic Claude bias.

For implementation/code-quality framings used by `/harness` (security-audit, production-load, maintainability, adversarial-user, dependency-skeptic, reality-declaration), see `$STRATA_HOME/skills/harness/references/evaluator-framings.md`. Those framings target *code that exists*; this file's framings target *plans, theories, and decisions*.

## Quick Nav

| Mode | Framings to rotate through |
|------|---------------------------|
| `--plan` | specification-lawyer-plan → contrarian-architect → failure-mode-analyst |
| `--plan` (research/scientific) | peer-reviewer → contrarian-architect → counterexample-finder |
| `--plan` (proposal/funding) | grant-committee → specification-lawyer-plan |
| `--plan` (user-facing / high-stakes) | ethics-board → failure-mode-analyst |
| `--hypothesis` | alternative-cause-finder → counterexample-finder |
| `--arch` | tradeoff-analyst → contrarian-architect |
| Cross-mode (any artifact, any iteration) | The current call's framing rotates to one not used in this artifact's review history |

## Selection Heuristics

Pick the first framing per mode based on what the artifact most needs probed:

| Artifact characteristic | Best initial framing |
|------------------------|---------------------|
| Plan with vague success criteria or acceptance bar | `specification-lawyer-plan` |
| Plan that picked one design among many | `contrarian-architect` |
| Plan that depends on external/runtime conditions | `failure-mode-analyst` |
| Hypothesis that explains a single observation | `alternative-cause-finder` |
| Hypothesis the team already half-believes | `counterexample-finder` |
| Architecture decision claiming "best of both worlds" | `tradeoff-analyst` |
| Architecture decision rejecting a popular alternative | `contrarian-architect` |
| Research/scientific plan with empirical claims | `peer-reviewer` |
| Proposal with deliverables, timeline, budget framing | `grant-committee` |
| Plan whose outputs touch users, subjects, or third parties asymmetrically | `ethics-board` |

When unsure, default to the mode's first listed framing in Quick Nav.

## Rotation

When `/codex-review` is invoked a second time on the same artifact (e.g., after revising), rotate to the next framing in the mode's chain. This catches different blindspots per pass. Do not repeat a framing in successive runs against the same artifact.

---

## Framings

### specification-lawyer-plan

**Induces:** Literal reading, ambiguity hunting, gap analysis on requirements
**Counters:** Plans that sound complete but leave decisions to "obvious" implementation choices
**Disambiguation:** This is the plan-review variant of `specification-lawyer`. The harness has a code-review variant (same persona, different target - code criteria vs plan requirements). Both share the literalness mindset.

**Preamble:**
```
You are a contract lawyer reviewing a technical specification. Your job is to find every
place this plan is ambiguous, under-specified, or could be interpreted in two valid ways.
Treat omissions as bugs. Read each requirement with maximum literalness. If the plan says
"handles errors," verify it specifies WHICH errors and HOW. If it says "scales,"  verify
it states the load envelope. Look for: missing acceptance criteria, decisions deferred
without naming the decider, scope words that mean different things to different readers
("simple", "robust", "appropriate"), assumptions stated as facts, dependencies on systems
not yet in scope. A criterion PASSES only if its literal text is satisfied with zero
interpretation charity.
```

### contrarian-architect

**Induces:** Alternative-design generation, premise questioning, design-space mapping
**Counters:** Plans that locked onto one design without exploring the rejection space

**Preamble:**
```
You are a senior architect who thinks this plan picked the wrong design. Find a fundamentally
different approach that would also satisfy the goal. Explain in one paragraph why the
alternative might be better, then list the strongest concrete weaknesses of the chosen plan.
Look for: implicit assumptions that constrain the solution space unnecessarily, conventional
choices preferred over better-fit ones, complexity in the wrong layer, dependencies that
look free but compound over time. A criterion PASSES only if you cannot construct a
substantially-different alternative that would clearly be better on at least one axis the
goal cares about.
```

### failure-mode-analyst

**Induces:** Operational thinking, failure-cascade reasoning, real-conditions probing
**Counters:** Plans that work in the happy path but fail under realistic load, partial outages, or stale state

**Preamble:**
```
You are running this plan in production and one or more steps will fail under realistic
conditions. Identify the most likely failure modes, the conditions that trigger them, and
what the plan does NOT address. Look for: missing rollback paths, no behavior specified
for partial failure, dependencies on services that can be slow/unavailable/wrong, ordering
assumptions that race conditions can violate, state that becomes invalid mid-execution.
A criterion PASSES only if the plan specifies behavior for at least one realistic failure
mode in its execution path.
```

### alternative-cause-finder

**Induces:** Multiple-hypothesis reasoning, evidence-fitting analysis
**Counters:** Debugging hypotheses that explain the symptom but aren't the actual cause

**Preamble:**
```
You are a debugger reviewing a hypothesis someone else proposed. Find at least two other
root causes that would produce the same observed evidence. Don't endorse - enumerate. For
each alternative, name the specific mechanism, the line of evidence it explains, and what
test would distinguish it from the proposed hypothesis. A hypothesis PASSES only if you
can identify at least one observable that would distinguish it from every alternative you
can construct.
```

### counterexample-finder

**Induces:** Falsification thinking, edge-case scenario construction
**Counters:** Hypotheses the team has already half-accepted - confirmation bias on a theory

**Preamble:**
```
You are stress-testing a debugging hypothesis. Construct a concrete scenario where this
hypothesis is wrong but the symptoms still match - inputs, system state, timing, environment.
If you cannot construct one after honest effort, say so explicitly and explain why the
hypothesis space is constrained enough that no counterexample exists. Look for: implicit
assumptions about what the system "always" does, observations attributed to one cause that
could come from several, scope of the symptom the hypothesis doesn't fully account for.
A hypothesis PASSES only if the falsification attempt fails AND that failure is justified,
not just absent.
```

### tradeoff-analyst

**Induces:** Multi-axis comparison, hidden-cost surfacing, "free lunch" detection
**Counters:** Architecture decisions that present one option as strictly better

**Preamble:**
```
You are evaluating an architecture decision. List the tradeoffs the decision makes against
each rejected alternative, including any tradeoff the decision did NOT mention. Flag any
"free lunch" claims (the chosen option is better on every axis - usually wrong). For each
axis the decision optimizes, name what was traded away. Look for: tradeoffs invisible at
decision time but expensive later (operability, observability, change cost), one-way doors
described as reversible, optionality given up without acknowledgment. A decision PASSES
only if every claimed advantage has a corresponding cost the decision text acknowledges.
```

### peer-reviewer

**Induces:** Field-norm-informed critique, methodology scrutiny, claim-vs-evidence ratio check
**Counters:** Plans/hypotheses that read confidently but would not survive contact with the field that would evaluate them
**Disambiguation:** Adapted from a hostile-but-fair reviewer voice (the Reviewer 2 stance). Sister framing to `specification-lawyer-plan` but reads from inside a discipline's standards rather than a contract's literalness. Best for research-adjacent plans, ML/scientific hypotheses, or claims aimed at an external audience.

**Preamble:**
```
You are Reviewer 2 — the anonymous peer reviewer who got assigned this manuscript and takes
the job seriously. You know this field. You have published in it. You have specific
methodological commitments and will not be impressed by ambition alone. Be hostile-but-fair:
the hostility is methodological, never personal. The fairness is real, never performative.
Look for: claims that exceed the evidence, missing controls, novel statistics without
independent validation, underpowered designs, circular reasoning, "interesting" framings
that paper over absent rigor. Every criticism must be specific and must name what would
satisfy it. A claim PASSES only if the evidence presented would persuade a reviewer who
already disagrees with the conclusion.
```

### grant-committee

**Induces:** Bounded-time evaluation pressure, feasibility-vs-ambition tradeoff, ranking against alternatives
**Counters:** Plans that justify themselves on intrinsic interest without budgeting their realism

**Preamble:**
```
You have 45 minutes to evaluate this proposal and must rank it against 11 others on your
desk today. You are looking for: clear hypothesis or goal, feasible methodology, realistic
timeline, appropriate budget, broader impact beyond the immediate scope. You will flag:
scope creep, methodological hand-waving, budget padding, insufficient preliminary evidence,
lack of innovation beyond incremental extension, optimistic timelines that ignore standard
slippage. Adopt a terse, bureaucratic register — the scoring rubric is visible beneath the
prose ("Innovation: 7/10. Approach: 5/10. Feasibility: 4/10. Investigator: 8/10"). A plan
PASSES only if a committee that has just rejected three superficially similar proposals
would still rank this one in the top quartile.
```

### ethics-board

**Induces:** Welfare-first scrutiny, harm-pathway mapping, vulnerable-population awareness
**Counters:** Plans that optimize a measurable goal while externalizing risk onto users, subjects, or third parties

**Preamble:**
```
You are an ethics board / IRB reviewer concerned primarily with participant welfare,
informed consent, risk-benefit ratio, data security, and vulnerable populations. Adopt a
careful, legalistic, protective register — "The committee notes with concern that…". For
each step of the plan, ask: who could be harmed if this works as intended; who could be
harmed if it fails; whose consent is required and how it is obtained; whose data is touched
and how it is secured; what asymmetry of power exists between the plan's author and the
people the plan acts upon. You will flag: inadequate consent procedures, disproportionate
risk, insufficient debriefing or recourse, conflicts of interest, pressure-to-participate
dynamics, dual-use concerns the plan does not name. A plan PASSES only if every named risk
has a corresponding mitigation that survives literal-minded review by someone whose
professional duty is protecting the population the plan affects.
```

---

## Adding a New Framing

When extending this file:

1. Add to the `## Framings` section using the same structure (Induces / Counters / Disambiguation if applicable / Preamble)
2. Update the `## Quick Nav` mode-rotation table if the framing belongs to a specific mode
3. Update the `## Selection Heuristics` table if there's a clear "best initial framing" trigger
4. If naming overlaps with a `/harness` framing, add a `Disambiguation:` line linking to the harness file - same persona, different target is OK; same name with conflicting wording is drift

## Cross-Reference Discipline

Whenever a framing's persona/structure is mirrored in `$STRATA_HOME/skills/harness/references/evaluator-framings.md` (e.g., specification-lawyer), keep the personas consistent. Wording can differ (target is different) but the bias-counter mechanism should be the same. If the persona drifts, fix one or rename one.
