---
name: tdd
description: Test-driven development as a vertical-slice red-green loop; one test drives one piece of implementation, then the next test responds to what that cycle taught. Tests verify behavior through public interfaces, never implementation details, so they survive refactors. Use when building a feature or fixing a bug test-first, when the user says "red-green-refactor", "write the test first", "TDD this", "tracer bullet", or "integration test", and as the default discipline for any new logic-bearing code. Auto-trigger when implementation of non-trivial logic is about to begin and no failing test exists yet, or when the user asks to add behavior to code that has a test surface.
---

# Test-Driven Development

Drive each behavior into existence one failing test at a time. The test comes first, the minimal code makes it pass, and the next test responds to what the last cycle revealed.

```
Goal: Build the target behavior through a sequence of vertical red-green slices,
      each test exercising a public interface so the suite survives refactors.

Success means:
  - Every behavior the user prioritized has one test that fails before its code exists
  - Each test asserts on observable output through the public interface, not internals
  - The implementation grew one test at a time; no speculative code ahead of a test
  - Refactor happened only on green, with tests re-run after each step

Stop when: the prioritized behaviors are covered, all tests are green, and mutation
           testing or a manual mutation spot-check shows the tests bite.
```

## Philosophy

Tests verify behavior through public interfaces, not implementation details. The code underneath can change entirely; the tests should not. A good test reads like a specification: "user can checkout with valid cart" names a capability, not a call graph. These survive refactors because they ignore internal structure.

Bad tests couple to implementation: they mock internal collaborators, exercise private methods, or verify through a side channel (querying the database directly instead of through the interface). The tell is a test that breaks when you rename an internal function while behavior is unchanged. That test was checking how, not what.

The richer treatment of which test shapes to avoid lives in `$STRATA_HOME/reference/code-quality-principles.md` section 5 (Testing Philosophy): the four forbidden patterns (tautological, no-op assertion, hardcoded mirroring, runs-without-crashing) and the mutation-testing discipline that catches weak suites. Read that section before writing the first test; this skill is the loop, that section is the bar each test clears.

## Anti-pattern: horizontal slices

Writing all the tests first, then all the implementation, is horizontal slicing: it treats RED as "write every test" and GREEN as "write every line of code." It produces weak tests.

Tests written in bulk verify *imagined* behavior. They test the shape of things (data structures, signatures) rather than what a user observes. They drift insensitive to real changes: they pass when behavior breaks and fail when behavior is fine. You commit to a test structure before you understand the implementation, outrunning your headlights.

```
WRONG (horizontal):
  RED:   test1, test2, test3, test4, test5
  GREEN: impl1, impl2, impl3, impl4, impl5
```

## The vertical slice

Build vertical slices with tracer bullets: one test, one piece of implementation, repeat. Each test responds to what the previous cycle taught. Because you just wrote the code, you know exactly which behavior matters and how to verify it.

```
RIGHT (vertical):
  RED→GREEN: test1 → impl1
  RED→GREEN: test2 → impl2
  RED→GREEN: test3 → impl3
  ...
```

## Workflow

### 1. Plan

When exploring the codebase, read `CONTEXT.md` if it exists so test names and interface vocabulary match the project's domain language, and respect any ADRs in the area you are touching. Look for deep-module opportunities (small interface, deep implementation); run `/codebase-design` for that vocabulary and its testability checks.

Before writing code, settle these with the user:

- Confirm which interface changes the feature needs.
- Confirm which behaviors to test, prioritized; you cannot test everything, so name the critical paths and the complex logic, and let the long tail of edge cases go.
- List the behaviors to test, framed as behaviors, not implementation steps.
- Get approval on the plan.

Ask: "What should the public interface look like, and which behaviors matter most to test?"

### 2. Tracer bullet

Write ONE test that confirms ONE thing about the system, then make it pass:

```
RED:   write the test for the first behavior → it fails
GREEN: write the minimal code that passes → it passes
```

This is the tracer bullet; it proves the path works end to end before you invest in the rest.

### 3. Incremental loop

For each remaining behavior:

```
RED:   write the next test → it fails
GREEN: write only enough code to pass → it passes
```

Hold these rules:

- One test at a time.
- Only enough code to pass the current test.
- Leave future tests for their own cycle; add nothing speculative now.
- Keep every test on observable behavior.

### 4. Refactor

Once the tests are green, hunt for refactor candidates: extract duplication, deepen modules (push complexity behind a simple interface), apply a SOLID principle where it falls out naturally, and let new code reveal what existing code should become. Re-run the tests after each refactor step.

Refactor only on green. Reach green first, then reshape.

## Checklist per cycle

```
[ ] Test describes behavior, not implementation
[ ] Test uses the public interface only
[ ] Test would survive an internal refactor
[ ] Code is minimal for this test
[ ] No speculative features added
```

## Test-strength check

Line coverage tells you a line ran; it says nothing about whether a test would notice that line breaking. After the prioritized behaviors are green, spot-check test strength: run mutation testing on the changed files if the toolchain supports it. When mutation tooling is unavailable, perform a manual mutation spot-check: temporarily break the implementation in a plausible way for the behavior under test, run the relevant test, and confirm it fails before restoring the implementation. Feed any surviving mutant back into a new test: "this mutation survived: <description>; write a test that catches this boundary." The forbidden-pattern list and mutation-testing rationale are in `$STRATA_HOME/reference/code-quality-principles.md` section 5.
