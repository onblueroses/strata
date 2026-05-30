<!-- keywords: code quality, code review, elegance, testing philosophy, comment discipline, slop, clean code, non-defensive, parse dont validate -->
# Code Quality Principles

Universal principles for all code the user writes with AI agents. Language-agnostic. Read this when starting any project, not just Rust. For Rust-specific applications, see `rust-ai-project-setup.md`.

Design goal: code that is beautiful, elegant, non-defensive, logically coherent, and minimally commented. Zero human review - the toolchain catches mistakes, the type system prevents misuse, and the code reads as its own documentation.

Evidence base: OX Security (300+ repos), CodeRabbit AI vs Human report, arXiv instruction-following research (20 frontier models), Chroma context-rot study, Tweag Agentic Coding Handbook, Addy Osmani's AI workflow, Armin Ronacher's agentic coding recommendations.

---

## Quick Nav

| Task | Section |
|------|---------|
| Write/review code style | 1. The Elegance Standard |
| Decide whether to write a comment | 2. Comment Discipline |
| Avoid unnecessary defensive code | 3. Non-Defensive Coding |
| Identify/fix AI-generated slop | 4. Killing AI Slop |
| Write tests correctly | 5. Testing Philosophy |
| Follow agent workflow patterns | 6. Agent Workflow |
| Design CLAUDE.md rules that stick | 7. CLAUDE.md Design |

---

## 1. The Elegance Standard

<details>
<summary>1. The Elegance Standard</summary>

Beautiful code is not clever code. It is code where the types carry meaning, the reader never wonders what a function does because its name and signature tell them, and there is nothing left to remove.

**Parse, don't validate.** Convert raw input into typed values at system boundaries. A function receiving a validated type does not re-check it. This eliminates defensive code at the source.

```
// Defensive (validates everywhere)
send_email(to: string)  ->  if !valid_email(to) { error }

// Elegant (impossible to misuse)
send_email(to: Email)   ->  `to` is guaranteed valid by construction
```

The standard library does this everywhere: `NonZeroU32` cannot be zero. `PathBuf` cannot be invalid UTF-16 on Windows. `String` is guaranteed valid UTF-8. Follow the same pattern in your own types.

**Flat over nested.** Every level of indentation is a cognitive tax. Use early returns, guard clauses, and language-specific flat patterns (Rust: `let-else` + `?`, TypeScript: early `if (!x) return`, Python: `if not x: return`) to keep the happy path at the left margin.

**Solve the actual problem.** No speculative abstractions, no "what if we need to later," no wrapper types that add no semantic value. Three similar lines of code is better than a premature abstraction. Add abstraction when you have three real use cases, not before.

**Honest signatures.** A function that always succeeds should not return an error type. A function that takes a string but immediately parses it should take the parsed type. The signature IS the documentation.

**Consistency within a file beats any abstract "best practice."** Match the patterns, naming, and structure of surrounding code. A codebase with one consistent style is more readable than a codebase where each function follows a different "best practice."

</details>

---

## 2. Comment Discipline

<details>
<summary>2. Comment Discipline</summary>

90-100% of AI-generated code has excessive comments (OX Security, 300+ repos analyzed). Over-commenting is the single loudest tell that code was AI-generated. The fix is simple: comments explain WHY, never WHAT or HOW.

### Delete these immediately

- `// increment counter` above `counter += 1`
- `/// Gets the foo` above `fn foo(&self) -> &Foo`
- `// Check if user is admin` above `if user.is_admin()`
- `// Initialize variables` above variable declarations
- Any comment that restates what the next line of code does

### Keep these

- **WHY decisions**: `// BTreeMap instead of HashMap because iteration order must be deterministic for snapshot tests`
- **Non-obvious performance**: `// Two-pass approach is 3x faster than single-pass due to cache locality (benchmarked)`
- **Pitfalls for future editors**: `// Do not reorder - migration must complete before cache invalidation`
- **External context links**: `// Implements algorithm from RFC 7539 Section 2.4`
- **Safety invariants**: Required on every `unsafe` block in Rust. Required on any code that relies on an invariant the type system doesn't enforce.

### Module-level docs are good

A module/file-level comment explaining the core concept, key invariants, and how this module fits into the larger system is valuable. Per-function doc comments on private functions with clear names are noise.

### The refactoring test

If you need a comment to explain what code does, consider renaming the function, variable, or type instead. `calculate_monthly_payment` needs no `// calculates the monthly payment` comment. If the logic is still unclear after good naming, then a WHY comment is warranted.

</details>

---

## 3. Non-Defensive Coding

<details>
<summary>3. Non-Defensive Coding</summary>

Defensive programming means checking for conditions that cannot occur. It makes code verbose, obscures the actual logic, and signals distrust in your own architecture. In AI-generated code, it's rampant - agents add checks "just in case" because their training data is full of defensive patterns.

### The boundary rule

Validate at **system boundaries** only:
- CLI argument parsing
- HTTP request handling
- File/database input
- User input from forms
- External API responses

Everything internal trusts its types. If a function receives a validated type, it does not re-validate. If a collection was checked for non-emptiness at the boundary, internal functions don't check again.

### Type-driven elimination of defensive code

Every defensive check is a sign that the type system isn't carrying its weight. Replace checks with types:

| Defensive check | Type-driven replacement |
|----------------|------------------------|
| `if email != ""` | `Email` newtype with validated constructor |
| `if count > 0` | `NonZeroU32` / `NonZeroUsize` |
| `if items.len() > 0` | `NonEmptyVec<T>` or validate at boundary |
| `if user.role == "admin"` | `enum Role { Admin, User }` |
| `if status == "active"` | `enum Status { Active, Inactive, ... }` |
| `if port >= 1 && port <= 65535` | `Port` newtype with range validation |

### What to trust

- Your own types and constructors
- Language/framework guarantees (Rust borrow checker, TypeScript strict mode, Python type hints with mypy)
- Validated data from your own parsing layer
- Return values from your own functions

### What NOT to trust

- External input (users, APIs, files, environment variables)
- Deserialized data from storage or network
- Third-party library behavior across version updates

</details>

---

## 4. Killing AI Slop

<details>
<summary>4. Killing AI Slop</summary>

AI-generated code has specific tells beyond just bugs (OX Security, CodeRabbit, dev.to analysis). Recognizing and eliminating these patterns is what separates working code from beautiful code.

### The tells

1. **Over-commenting** (90-100% of AI code). Every function documented regardless of complexity. Inline comments restating what code does. See Section 2.

2. **Universal defensive programming** (80-90%). Blanket try-catch blocks, null checks on things that can't be null, validation on already-validated data. See Section 3.

3. **Over-specification** (80-90%). Hyper-specific single-use solutions instead of simple, generalizable code. A 20-line script becomes a class with three helper methods and an abstract base.

4. **Textbook fixation** (80-90%). Rigidly follows conventional patterns, misses opportunities for simpler solutions. Builder pattern on a 3-field struct. Factory for a single type. Strategy pattern where an if-else would do.

5. **Absence of "fatigue"** (the uncanny valley). No rushed sections, no pragmatic workarounds, no `// TODO: revisit`. Code that is "too careful" everywhere, like a student who memorized the textbook.

6. **Naming inconsistency within consistency**. AI swings between hyper-descriptive names (`processAndValidateUserInputDataForRegistration`) and generic placeholders (`data`, `result`, `item`) within the same file. Humans maintain a consistent naming culture.

### Rules to prevent slop

For your project CLAUDE.md:

```
- No comments that restate code. Comments explain WHY only.
- No defensive checks on internal code. Validate at boundaries only.
- No abstractions for one use case. Add abstraction at three real use cases.
- No getters/setters on types with no invariants. Use public fields.
- No unnecessary error wrapping. If you can't add context, just propagate.
- No "just in case" code. If a condition can't happen, don't check for it.
```

### The style examples approach

The single most effective technique: include 2-3 exemplary functions in a project-local reference file (e.g., `<project>/.claude/style-examples.{rs,ts,py}`). LLMs are pattern matchers — showing a 30-line function that embodies your style teaches more than 30 lines of rules.

Reference from project CLAUDE.md: `For code style, match style-examples.{ext}`

Select examples that demonstrate: flat control flow, the right amount of commenting (almost none), type-driven design, and error handling with context. Update when your style evolves.

</details>

---

## 5. Testing Philosophy

<details>
<summary>5. Testing Philosophy</summary>

### Test-first is non-negotiable

When tests exist before code, the agent cannot write tautological tests that mirror a broken implementation. This is the single highest-leverage practice for autonomous AI coding (Tweag Agentic Coding Handbook, Builder.io, CodeRabbit).

Flow: **write test (red) -> implement (green) -> refactor -> commit**.

When modifying existing code: write a new test that captures the desired change FIRST, verify it fails, then make the change.

### Forbidden test patterns

These patterns create false confidence and are the primary way AI-generated tests fail silently:

- **Tautological tests**: test mirrors the implementation logic. If the impl is wrong, the test passes anyway because both sides compute the same wrong answer.
- **No-op assertions**: `assert(result.is_ok())` without checking the value. Passes on any success regardless of content.
- **Hardcoded mirroring**: running the implementation, copying the output as the expected value. If the implementation is buggy, the test enshrines the bug.
- **"Runs without crashing" tests**: test calls a function and asserts nothing about the result.

### Mutation testing catches weak tests

Coverage says "this line ran." Mutation testing says "if I break this line, does any test notice?" A test suite with 100% line coverage but 4% mutation score would miss 96% of possible bugs (TwoCents Software, HumanEval-Java analysis).

Run mutation testing on changed files after implementation. Surviving mutants = test gaps. Feed surviving mutants back to the AI with: "This mutation survived: [description]. Write a test that catches this boundary condition."

### Test behavior, not implementation

Name tests after the behavior they verify: `test_empty_input_returns_none`, not `test_parse_function`. If someone renames the function, the test name should still make sense. Test the contract, not the code path.

</details>

---

## 6. Agent Workflow

<details>
<summary>6. Agent Workflow</summary>

### Spec-driven development

The workflow power users converge on: **SPEC -> PLAN -> IMPLEMENT -> VERIFY -> SHIP** (Addy Osmani, ThoughtWorks, ICSE 2026). Write the spec first, iterate on it with the AI, then implement one step at a time with tests.

For your setup, this means using `/spec` for non-trivial tasks (3+ files). The spec survives context compaction. Decisions recorded in the spec are settled.

### The three-attempt pattern

Expect first-shot code to be ~95% wrong (Sanity engineering report). This is normal, not a failure:

- **Attempt 1** (~95% wrong): the agent builds system context while you identify real constraints
- **Attempt 2** (~50% wrong): after feeding back learnings, the agent grasps nuances
- **Attempt 3**: a workable foundation emerges for continuous iteration

Budget for iteration, not perfection.

### Context management

Context windows degrade as they fill (Chroma, 2025 - every frontier model tested). Performance drops 30%+ when relevant information sits in the middle of the context.

- **One feature per session.** Don't mix unrelated work. Use `/clear` between tasks.
- **Commit and restart** for features spanning 3+ hours. Export to spec, start fresh.
- **Ultra-granular commits.** Each small task = one commit = one save point.
- **Subagents for exploration.** The subagent's investigation history stays in its own context. Only the result returns to the main window.
- **Manual file reads over auto-discovery.** Telling the agent exactly which file to read prevents slow background searches.

### Three-layer enforcement

No single layer catches everything:

| Layer | Mechanism | Catches | Reliability |
|-------|-----------|---------|-------------|
| Instructions | CLAUDE.md, rules files | Architecture, naming, patterns, intent | ~80-95% per rule, degrades with count |
| Hooks | Pre-commit, pre-push | Test failures, format violations, coverage | 100% (deterministic) |
| Linters + CI | Language-specific tooling | Everything pattern-matchable | 100% for covered patterns |

Instructions explain intent. Hooks prevent the worst outcomes. Linters catch everything in between.

</details>

---

## 7. CLAUDE.md Design

<details>
<summary>7. CLAUDE.md Design</summary>

### The compliance math

Research testing 20 frontier models (arXiv 2025):

- Overall compliance = (per-instruction compliance)^(number of instructions)
- 20 rules at 95% = **36% overall compliance**
- Claude Code's system prompt already uses ~50 instruction slots

Every line in CLAUDE.md competes for attention. Fewer, higher-quality rules beat long lists.

### What makes rules stick

- **Specific and executable**: `npm run lint --fix` beats "format your code"
- **One code example > three paragraphs**: show the pattern, don't describe it
- **Front-loaded**: models attend more to the beginning and end of context
- **Positive framing**: "Always use X" outperforms "Never use Y". When using "Never," pair with "Instead, do X"
- **Not duplicating linters**: if the toolchain catches it, don't waste a CLAUDE.md rule

### What to put where

| Content | Location | Why |
|---------|----------|-----|
| Critical style rules (5-8 lines) | CLAUDE.md | Loaded every session |
| Full principles and rationale | `$STRATA_HOME/reference/code-quality-principles.md` | Read on-demand |
| Language-specific tooling | `$STRATA_HOME/reference/rust-ai-project-setup.md` etc. | Read at project setup |
| Module-specific rules | `.claude/rules/module-name.md` | Loaded only when touching that module |
| Style examples | project-local `style-examples.{ext}` | Pattern-matching teaches better than rules |

### The three-tier boundary pattern

The most effective constraint structure for agent instructions:

- **Always** (autonomous, no approval needed): "Always run tests before committing"
- **Ask first** (needs human sign-off): "Ask before adding new dependencies"
- **Never** (hard stop, pair with alternative): "Never add `.unwrap()` - use `?` or `.ok_or_else()` instead"

</details>
