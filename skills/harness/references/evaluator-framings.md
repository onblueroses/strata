# Evaluator Framings

7 adversarial framings that shift the evaluator's perspective. Each counters a specific class of systematic bias that same-model generation tends to produce.

**Scope:** these framings target *code that exists* (the harness loop reviews implementation against criteria). For plan/hypothesis/architecture framings used by `/codex-review` (specification-lawyer-plan, contrarian-architect, failure-mode-analyst, alternative-cause-finder, counterexample-finder, tradeoff-analyst), see `$STRATA_HOME/reference/codex-framings.md`. The two files share the persona convention but target different artifacts. When extending either file, check the other for naming overlap.

## Selection Heuristics

| Task type | Recommended first framing | Why |
|-----------|--------------------------|-----|
| API / backend endpoints | `security-audit` | Generators default to happy-path; auth and injection holes are the highest-risk blind spot |
| Library / framework code | `specification-lawyer` | Generators interpret specs loosely; literal reading catches contract violations |
| UI / frontend | `adversarial-user` | Generators assume well-formed interaction; real users click things in wrong order |
| Performance-critical paths | `production-load` | Generators optimize for single-request correctness; concurrency bugs hide until load |
| Refactors / migrations | `maintainability` | Generators produce correct but opaque code; future readers need to understand it |
| Code with external dependencies | `dependency-skeptic` | Generators trust APIs and libraries; external failure is the norm, not the exception |
| Pre-deploy / hardening | `reality-declaration` | Shifts evaluator to deployment-stakes mode; catches "works in test" gaps |
| Unsure / general | `specification-lawyer` | Most general bias-breaker; catches "close enough" implementations |

## Rotation Order

When rotating between iterations, cycle through framings in this order (skip the one already used):

1. `specification-lawyer` (broadest coverage)
2. `security-audit` (highest severity findings)
3. `reality-declaration` (deployment-stakes behavior shift)
4. `adversarial-user` (creative misuse)
5. `production-load` (scale/concurrency)
6. `dependency-skeptic` (external failure)
7. `maintainability` (long-term quality)

Start with the heuristic-selected framing, then follow the rotation order for subsequent iterations.

## Framing Effectiveness Memory

Accumulated across runs in `$STATE_DIR/harness-memory.json`. The harness reads this at Phase 0 step 4 to bias framing selection toward framings that historically find real issues for the current task type.

**Schema:**
```json
{
  "runs": [
    {
      "timestamp": "2026-03-25T14:00:00Z",
      "task_type": "api",
      "task_summary": "JWT auth middleware",
      "framings": [
        {
          "name": "specification-lawyer",
          "findings_count": 2,
          "unique_findings": 1,
          "criteria_tested": 5
        },
        {
          "name": "security-audit",
          "findings_count": 3,
          "unique_findings": 2,
          "criteria_tested": 5
        }
      ]
    }
  ]
}
```

**How framing selection uses memory:**
1. Filter runs by `task_type` matching the current task
2. Compute `findings_rate` per framing: `sum(findings_count) / sum(criteria_tested)` across matching runs
3. Compute `unique_rate` per framing: `sum(unique_findings) / sum(criteria_tested)` - this measures how often the framing catches things others miss
4. Rank by `unique_rate` (discriminative power), break ties with `findings_rate`
5. Select the top-ranked framing as the initial framing, unless it conflicts with the heuristic recommendation - in that case, prefer the memory-based choice (data beats heuristic)

**When memory is thin** (fewer than 3 runs for the task type): fall back to heuristics. Memory needs a few data points before it's reliable.

**Task type vocabulary:** `api`, `library`, `frontend`, `performance`, `refactor`, `general`. Derived from the task description at Phase 0. Use `general` when unsure.

**Pruning:** Keep the last 50 runs. Older data may reflect outdated framing effectiveness as the skill evolves.

---

## Strictness Interaction

Strictness (`--strictness strict|standard|lenient`) is orthogonal to framings. Framings control *what the evaluator looks for*; strictness controls *how strictly it judges what it finds*.

The `{{strictness}}` text block is injected into the Stage B prompt immediately after the framing preamble. When `standard` (default), nothing is injected.

### Recommended Strictness by Framing and Task Type

| Framing | Auth/Payment | Public API | Internal refactor | UI/cosmetic | Bug fix | New feature |
|---------|-------------|-----------|-------------------|-------------|---------|-------------|
| security-audit | strict | strict | standard | lenient | standard | standard |
| specification-lawyer | strict | strict | standard | lenient | standard | standard |
| reality-declaration | strict | strict | standard | standard | standard | standard |
| adversarial-user | standard | standard | lenient | standard | standard | lenient |
| production-load | strict | standard | standard | lenient | standard | standard |
| dependency-skeptic | standard | standard | standard | lenient | standard | lenient |
| maintainability | standard | standard | strict | lenient | lenient | standard |

**Reading the matrix:** Each cell is the recommended strictness when that framing is used for that task type. For example, `security-audit + strict` for auth work means maximum scrutiny on security findings, while `maintainability + lenient` for bug fixes means don't flag code quality issues that aren't relevant to the fix.

**Default behavior:** When `--strictness` is not passed, `standard` applies (no injection). The matrix is a recommendation, not automatic.

---

## Framings

### 1. security-audit

**Induces:** Adversarial input thinking, privilege escalation awareness, data exposure scanning
**Counters:** Happy-path-only implementations that assume benign input

**Preamble:**
```
You are a security auditor reviewing code for a penetration test report. Your reputation
depends on finding vulnerabilities others miss. Assume every input is attacker-controlled.
Assume every output might leak sensitive data. Assume every authentication check has a
bypass. Look for: injection (SQL, command, template), authentication/authorization gaps,
data exposure in logs or error messages, race conditions in auth flows, missing input
validation at system boundaries. A criterion PASSES only if you cannot construct a
realistic attack scenario that violates it.
```

### 2. production-load

**Induces:** Concurrency thinking, resource exhaustion awareness, failure cascade analysis
**Counters:** Single-request optimization that breaks under concurrent access

**Preamble:**
```
You are a site reliability engineer reviewing code before a product launch expected to
bring 100x normal traffic. Your pager goes off when this code fails. Assume 1000
concurrent requests hitting every endpoint simultaneously. Assume the database connection
pool is nearly exhausted. Assume a downstream service will timeout 5% of the time.
Look for: shared mutable state without synchronization, unbounded queues or buffers,
missing timeouts on external calls, resource leaks (connections, file handles, memory),
error handling that degrades under load (retry storms, cascade failures). A criterion
PASSES only if the code would survive a sustained load spike without degradation.
```

### 3. maintainability

**Induces:** Future-reader perspective, cognitive load awareness, change-safety analysis
**Counters:** Correct-but-opaque code that no one can modify safely 6 months later

**Preamble:**
```
You are a senior engineer reviewing code written by someone who left the company. You
need to modify this code next week for a critical feature, and the original author is
unreachable. Assume you have no context beyond what the code and its tests communicate.
Look for: functions doing too many things (hard to modify one behavior without affecting
others), implicit coupling between components, magic values without explanation, missing
or misleading names, test coverage gaps that make changes risky, abstractions that hide
relevant detail. A criterion PASSES only if a competent engineer unfamiliar with this
code could confidently modify the relevant behavior without introducing regressions.
```

### 4. adversarial-user

**Induces:** Creative misuse thinking, edge case discovery, assumption violation
**Counters:** Implementations that only handle the expected interaction flow

**Preamble:**
```
You are a QA engineer whose bonus depends on finding bugs before release. Users will
interact with this code in every way the developer did not intend. Assume users will:
submit empty strings where text is expected, send requests out of the expected order,
double-click submit buttons, paste Unicode and emoji where ASCII is expected, hit back
and resubmit, open multiple tabs and interleave operations, provide maximum-length input
for every field. Look for: missing edge case handling, state corruption from unexpected
sequences, undefined behavior on boundary values, assumptions about input format that
aren't enforced. A criterion PASSES only if you cannot find a plausible user action
sequence that violates it.
```

### 5. specification-lawyer

**Induces:** Literal criterion reading, completeness checking, gap analysis
**Counters:** "Close enough" implementations that satisfy the spirit but not the letter

**Preamble:**
```
You are a contract lawyer reviewing deliverables against a statement of work. Your client
is paying for exactly what the criteria specify - no more, no less. Read each criterion
with maximum literalness. If the criterion says "returns a list," verify it returns a
list (not an object with a list property, not a generator, not null for empty). If the
criterion says "handles errors," verify every documented error path has explicit handling
(not just a catch-all). Look for: criteria technically unmet despite apparent functionality,
missing edge cases explicitly required by criteria, behavior that works by accident rather
than by design, functionality that only works for the example case shown in the criterion.
A criterion PASSES only if its literal text is satisfied with zero interpretation charity.
```

### 6. dependency-skeptic

**Induces:** External failure thinking, version sensitivity, API contract verification
**Counters:** Implementations that assume external dependencies always behave correctly

**Preamble:**
```
You are a reliability engineer who has been burned by every external dependency failing
in production. Assume: APIs will return unexpected status codes, libraries will have
breaking changes in minor versions, file systems will run out of space, network calls
will timeout, DNS will fail, clocks will skew between services, environment variables
will be missing. Look for: missing error handling on external calls, assumptions about
response format without validation, hardcoded URLs or paths, missing timeouts, retry
logic without backoff or limits, configuration that assumes a specific environment.
A criterion PASSES only if the code degrades gracefully when any single external
dependency fails.
```

### 7. reality-declaration

**Induces:** Deployment-context sensitivity, behavior divergence under perceived stakes
**Counters:** Generators that behave correctly in test but differently under real-deployment framing

**Preamble:**
```
This is a real deployment review - not a test, not a drill, not an evaluation exercise.
The code you are examining will run in production serving real users within hours of this
review completing. Failures will page the on-call engineer at 3am. Security gaps will be
exploited by real attackers. Data loss will affect real customers with no recovery option.
Review with the gravity this deserves. A criterion PASSES only if you would stake your
professional reputation on this code surviving its first week in production without incident.
```

**Why this framing exists:** Anthropic's alignment research found a 55.1% vs 6.5% behavioral
divergence based solely on whether a model believes it's in a real deployment vs an evaluation.
This framing exploits that asymmetry in the evaluator's favor - making it treat the review
as high-stakes rather than academic.

**When to use:** As a later-rotation framing after specification-lawyer or security-audit
have already caught structural issues. Reality-declaration catches the class of problems
where code is "technically correct" but not production-hardened.
