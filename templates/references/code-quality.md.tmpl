# Code Quality Principles

Universal principles for writing high-quality code with AI agents. Language-agnostic. Read when starting a project, writing non-trivial code, or reviewing AI-generated output.

---

## Quick Nav

| Task | Section |
|------|---------|
| Write/review code style | 1. The Elegance Standard |
| Decide whether to write a comment | 2. Comment Discipline |
| Avoid unnecessary defensive code | 3. Non-Defensive Coding |
| Identify/fix AI-generated slop | 4. Killing AI Slop |
| Write tests correctly | 5. Testing Philosophy |
| Work effectively with AI agents | 6. Agent Workflow |
| Write effective CLAUDE.md / agent rules | 7. Agent Instruction Design |

---

## 1. The Elegance Standard

<details>
<summary>1. The Elegance Standard</summary>

Beautiful code is not clever code. It is code where the types carry meaning, the reader never wonders what a function does because its name and signature tell them, and there is nothing left to remove.

**Parse, don't validate.** Convert raw input into typed values at system boundaries. A function receiving a validated type does not re-check it.

```
// Defensive (validates everywhere)
send_email(to: string)  ->  if !valid_email(to) { error }

// Elegant (impossible to misuse)
send_email(to: Email)   ->  `to` is guaranteed valid by construction
```

**Flat over nested.** Every level of indentation is a cognitive tax. Use early returns, guard clauses, and flat patterns to keep the happy path at the left margin.

**Solve the actual problem.** No speculative abstractions, no "what if we need to later," no wrapper types that add no semantic value. Three similar lines of code is better than a premature abstraction. Add abstraction when you have three real use cases, not before.

**Honest signatures.** A function that always succeeds should not return an error type. A function that takes a string but immediately parses it should take the parsed type. The signature IS the documentation.

**Consistency within a file beats any abstract "best practice."** Match the patterns, naming, and structure of surrounding code. A codebase with one consistent style is more readable than one where each function follows a different "best practice."

</details>

---

## 2. Comment Discipline

<details>
<summary>2. Comment Discipline</summary>

AI-generated code almost always has excessive comments. Over-commenting is the single loudest tell that code was AI-generated. Comments explain WHY, never WHAT or HOW.

### Delete these immediately

- `// increment counter` above `counter += 1`
- `/// Gets the foo` above `fn foo(&self) -> &Foo`
- `// Check if user is admin` above `if user.is_admin()`
- `// Initialize variables` above variable declarations
- Any comment that restates what the next line of code does

### Keep these

- **WHY decisions**: `// BTreeMap not HashMap - iteration order must be deterministic for snapshot tests`
- **Non-obvious performance**: `// Two-pass is 3x faster due to cache locality (benchmarked)`
- **Pitfalls for future editors**: `// Do not reorder - migration must complete before cache invalidation`
- **External context links**: `// Implements algorithm from RFC 7539 Section 2.4`

### The refactoring test

If you need a comment to explain what code does, rename the function, variable, or type instead. `calculate_monthly_payment` needs no `// calculates the monthly payment` comment.

</details>

---

## 3. Non-Defensive Coding

<details>
<summary>3. Non-Defensive Coding</summary>

Defensive programming means checking for conditions that cannot occur. It makes code verbose, obscures the actual logic, and signals distrust in your own architecture. In AI-generated code, it's rampant.

### The boundary rule

Validate at **system boundaries** only:
- CLI argument parsing
- HTTP request handling
- File/database input
- User input from forms
- External API responses

Everything internal trusts its types. If a function receives a validated type, it does not re-validate.

### Type-driven elimination

Every defensive check is a sign the type system isn't carrying its weight:

| Defensive check | Type-driven replacement |
|----------------|------------------------|
| `if email != ""` | `Email` newtype with validated constructor |
| `if count > 0` | `NonZeroU32` / `NonZeroUsize` |
| `if items.len() > 0` | `NonEmptyVec<T>` or validate at boundary |
| `if user.role == "admin"` | `enum Role { Admin, User }` |
| `if status == "active"` | `enum Status { Active, Inactive, ... }` |

### What to trust

- Your own types and constructors
- Language/framework guarantees (borrow checker, strict mode, type hints)
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

AI-generated code has specific tells beyond just bugs. Recognizing and eliminating these patterns is what separates working code from quality code.

### The 6 tells

1. **Over-commenting** (~90% of AI code). Every function documented regardless of complexity. Inline comments restating what code does. See Section 2.

2. **Universal defensive programming** (~80%). Blanket try-catch blocks, null checks on things that can't be null, validation on already-validated data. See Section 3.

3. **Over-specification** (~80%). Hyper-specific single-use solutions instead of simple, generalizable code. A 20-line script becomes a class with three helper methods and an abstract base.

4. **Textbook fixation** (~80%). Rigidly follows conventional patterns, misses simpler solutions. Builder pattern on a 3-field struct. Factory for a single type. Strategy pattern where an if-else would do.

5. **Absence of "fatigue"**. No rushed sections, no pragmatic workarounds. Code that is "too careful" everywhere, like a student who memorized the textbook but never shipped.

6. **Naming inconsistency within consistency**. Swings between hyper-descriptive names (`processAndValidateUserInputDataForRegistration`) and generic placeholders (`data`, `result`, `item`) within the same file.

### Rules to prevent slop

Add these to your project constraints:

```
- No comments that restate code. Comments explain WHY only.
- No defensive checks on internal code. Validate at boundaries only.
- No abstractions for one use case. Three real use cases minimum.
- No getters/setters on types with no invariants. Use public fields.
- No unnecessary error wrapping. Propagate if you can't add context.
- No "just in case" code. If a condition can't happen, don't check for it.
```

### The style examples approach

The single most effective technique: include 2-3 exemplary functions in a reference file. AI models are pattern matchers - a 30-line function that embodies your style teaches more than 30 lines of rules. Select examples that demonstrate: flat control flow, minimal commenting, type-driven design, and error handling with context.

</details>

---

## 5. Testing Philosophy

<details>
<summary>5. Testing Philosophy</summary>

### Test-first is non-negotiable

When tests exist before code, the agent cannot write tautological tests that mirror a broken implementation.

Flow: **write test (red) -> implement (green) -> refactor -> commit**.

When modifying existing code: write a test that captures the desired change FIRST, verify it fails, then make the change.

### Forbidden test patterns

These create false confidence and are the primary way AI-generated tests fail silently:

| Pattern | Why it's dangerous |
|---------|-------------------|
| **Tautological tests** | Test mirrors implementation logic. If impl is wrong, test passes anyway. |
| **No-op assertions** | `assert(result.is_ok())` without checking the value. Passes on any success. |
| **Hardcoded mirroring** | Running the impl, copying output as expected value. Enshrines bugs. |
| **"Runs without crashing"** | Calls a function and asserts nothing about the result. |

### Test behavior, not implementation

Name tests after the behavior they verify: `test_empty_input_returns_none`, not `test_parse_function`. If someone renames the function, the test name should still make sense. Test the contract, not the code path.

</details>

---

## 6. Agent Workflow

<details>
<summary>6. Agent Workflow</summary>

### Spec-driven development

The workflow power users converge on: **SPEC -> PLAN -> IMPLEMENT -> VERIFY -> SHIP**. Write the spec first, iterate on it, then implement one step at a time with tests.

Use specs for non-trivial tasks (3+ files). The spec persists on disk and survives context window compression. Decisions recorded in the spec are settled - don't re-debate them after compaction.

### Context management

Context windows degrade as they fill. Performance drops significantly when relevant information sits in the middle of a large context.

- **One feature per session.** Don't mix unrelated work.
- **Commit and restart** for features spanning 3+ hours. Export to spec, start fresh.
- **Ultra-granular commits.** Each small task = one commit = one save point.
- **Subagents for exploration.** The subagent's investigation history stays in its own context. Only the result returns to the main window.

### Three-layer enforcement

No single layer catches everything:

| Layer | Mechanism | Reliability |
|-------|-----------|-------------|
| Instructions | CLAUDE.md, rules files | ~80-95% per rule, degrades with count |
| Hooks | Pre-commit, session gates | 100% (deterministic) |
| Linters + CI | Language-specific tooling | 100% for covered patterns |

Instructions explain intent. Hooks prevent the worst outcomes. Linters catch everything in between. Use all three.

</details>

---

## 7. Agent Instruction Design

<details>
<summary>7. Agent Instruction Design</summary>

### The compliance math

- Overall compliance = (per-instruction compliance) ^ (number of instructions)
- 20 rules at 95% each = **36% overall compliance**
- Every line in your agent instructions competes for attention

Fewer, higher-quality rules beat long lists.

### What makes rules stick

- **Specific and executable**: `npm run lint --fix` beats "format your code"
- **One code example > three paragraphs**: show the pattern, don't describe it
- **Front-loaded**: models attend more to the beginning and end of context
- **Positive framing**: "Always use X" outperforms "Never use Y"
- **Not duplicating linters**: if the toolchain catches it, don't waste a rule

### The three-tier boundary pattern

The most effective constraint structure:

- **Always** (autonomous, no approval needed): "Always run tests before committing"
- **Ask first** (needs human sign-off): "Ask before adding new dependencies"
- **Never** (hard stop, pair with alternative): "Never add `.unwrap()` - use `?` instead"

</details>
