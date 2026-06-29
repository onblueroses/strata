---
name: diagnosing-bugs
description: "Feedback-loop-first diagnosis method for hard bugs and performance regressions: build a tight, red-capable reproduction loop before forming any hypothesis, then let bisection, instrumentation, and hypothesis-testing consume it. Operationalizes the CLAUDE.md 'Find or build the loop' principle for debugging. Walks six phases — build the loop, reproduce + minimise, hypothesise, instrument, fix + regression test, cleanup + post-mortem — with a hard stop-and-ask gate when no loop can be built. Auto-trigger when the user says 'diagnose', 'debug this', 'why is this failing', or reports something broken, throwing, crashing, flaky, hanging, regressed, or slow. Manual: /diagnosing-bugs [symptom]."
---

# Diagnosing Bugs

A discipline for hard bugs. Skip a phase only with an explicit reason.

This skill is the debugging arm of the CLAUDE.md principle **Find or build the loop**: never theorize in a vacuum; construct an environment that verifies the work quickly and cheaply, then iterate against something real. The whole method front-loads that loop and forbids hypothesizing before it exists.

```
Goal: Find and fix the root cause of a hard bug by building a tight, red-capable
      feedback loop first, then driving every later step from that loop.

Success means:
  - One named command exists that goes red on this exact bug and green once fixed
  - The bug is reproduced, minimised, and root-caused against that loop
  - A regression test locks the bug at a correct seam (or the absence of a seam is documented)
  - All tagged instrumentation and throwaway prototypes are removed
  - The correct hypothesis is recorded in the commit / PR message

Stop when: the original repro no longer reproduces, the regression test passes,
           and cleanup is complete.
```

When exploring the codebase, read `CONTEXT.md` (when present) for a mental model of the relevant modules, check the project CLAUDE.md, and read any ADRs in the area you are touching. When the surface is unfamiliar and the path is non-obvious, run `/recon` first and feed its brief into Phase 1.

## Relationship to /codex-review --hypothesis

These two skills sit at opposite ends of the same ordering, and the ordering is the point. This skill **forbids** forming a hypothesis until a red-capable loop exists; `/codex-review --hypothesis` reviews a hypothesis adversarially **after** one has formed. So the handoff runs loop-first: build and run the loop here (Phases 1-2), generate ranked hypotheses (Phase 3), then pass the `Top riskiest assumptions` to `/codex-review --hypothesis` when the hypothesis gates real implementation. Reaching for `/codex-review --hypothesis` before a loop exists inverts the discipline; build the loop first.

## Phase 1 — Build a feedback loop

**This is the skill.** Everything else is mechanical. With a **tight** pass/fail signal for the bug, one that goes **red** on _this_ bug, you will find the cause; bisection, hypothesis-testing, and instrumentation all just consume it. Without one, staring at code will not save you.

Spend disproportionate effort here. **Be aggressive. Be creative. Refuse to give up.**

### Ways to construct one — try them in roughly this order

1. **Failing test** at whatever seam reaches the bug: unit, integration, e2e.
2. **Curl / HTTP script** against a running dev server.
3. **CLI invocation** with a fixture input, diffing stdout against a known-good snapshot.
4. **Headless browser script** (Playwright is a good default for screenshots and visual validation; drive the UI, assert on DOM / console / network).
5. **Replay a captured trace.** Save a real network request, payload, or event log to disk; replay it through the code path in isolation.
6. **Throwaway harness.** Spin up a minimal subset of the system (one service, mocked deps) that exercises the bug code path with a single function call.
7. **Property / fuzz loop.** For "sometimes wrong output", run 1000 random inputs and watch for the failure mode.
8. **Bisection harness.** When the bug appeared between two known states (commit, dataset, version), automate "boot at state X, check, repeat" so `git bisect run` can drive it.
9. **Differential loop.** Run the same input through old-version vs new-version (or two configs) and diff outputs.
10. **Human-in-the-loop bash script.** Last resort, only when a human must physically click. Structure the loop in a small driver script so the loop stays disciplined: print the exact step for the human, read one keypress or a pasted artifact back in, capture that output, and feed it to the next check. The structure is what matters; even a click-driven loop should be scripted, deterministic in what it asserts, and re-runnable, so its captured output flows back to you the same way an automated loop's would.

Build the right feedback loop, and the bug is 90% fixed.

### Tighten the loop

Treat the loop as a product. Once you have _a_ loop, **tighten** it:

- Make it faster: cache setup, skip unrelated init, narrow the test scope.
- Make the signal sharper: assert on the specific symptom, not "didn't crash".
- Make it more deterministic: pin time, seed RNG, isolate filesystem, freeze network.

A 30-second flaky loop is barely better than no loop; a 2-second deterministic one is a debugging superpower.

### Non-deterministic bugs

The goal is a **higher reproduction rate**, not a clean repro. Loop the trigger 100×, parallelise, add stress, narrow timing windows, inject sleeps. A 50%-flake bug is debuggable; a 1% one is not; raise the rate until it is debuggable.

### When you genuinely cannot build a loop

Stop and say so explicitly. **This is a hard gate, not a soft preference.** List what you tried. Ask the user for one of: (a) access to whatever environment reproduces it, (b) a captured artifact (HAR file, log dump, core dump, screen recording with timestamps), or (c) permission to add temporary production instrumentation. Hold here until you have a loop; do not proceed to hypothesize without one.

### Completion criterion — a tight loop that goes red

Phase 1 is done when the loop is **tight** and **red-capable**: you can name **one command** (a script path, a test invocation, a curl) that you have **already run at least once** (paste the invocation and its output), and that is:

- [ ] **Red-capable** — it drives the actual bug code path and asserts the **user's exact symptom**, so it goes red on this bug and green once fixed. Not "runs without erroring"; it catches _this specific bug_.
- [ ] **Deterministic** — same verdict every run (flaky bugs: a pinned, high reproduction rate, per above).
- [ ] **Fast** — seconds, not minutes.
- [ ] **Agent-runnable** — you can run it unattended; a human enters the loop only through the structured human-in-the-loop driver above.

Catch yourself reading code to build a theory before this command exists, and **stop: jumping straight to a hypothesis is the exact failure this skill prevents.** No red-capable command, no Phase 2.

## Phase 2 — Reproduce + minimise

Run the loop. Watch it go red: the bug appears.

Confirm:

- [ ] The loop produces the failure mode the **user** described, not a different failure that happens to be nearby. Wrong bug = wrong fix.
- [ ] The failure reproduces across multiple runs (or, for non-deterministic bugs, at a high enough rate to debug against).
- [ ] You captured the exact symptom (error message, wrong output, slow timing) so later phases can verify the fix actually addresses it.

### Minimise

Once it is red, shrink the repro to the **smallest scenario that still goes red**. Cut inputs, callers, config, data, and steps **one at a time**, re-running the loop after each cut; keep only what is load-bearing for the failure.

Why bother: a minimal repro shrinks the hypothesis space in Phase 3 (fewer moving parts left to suspect) and becomes the clean regression test in Phase 5.

Done when **every remaining element is load-bearing**: removing any one of them makes the loop go green.

Reproduce **and** minimise before proceeding.

## Phase 3 — Hypothesise

Generate **3-5 ranked hypotheses** before testing any of them. Single-hypothesis generation anchors on the first plausible idea.

Make each hypothesis **falsifiable**: state the prediction it makes.

> Format: "If <X> is the cause, then <changing Y> makes the bug disappear / <changing Z> makes it worse."

A hypothesis with no prediction is a vibe; discard or sharpen it.

**Show the ranked list to the user before testing.** They often have domain knowledge that re-ranks instantly ("we just deployed a change to #3"), or know hypotheses already ruled out. Cheap checkpoint, big time saver. Proceed with your ranking when the user is AFK; do not block on it.

When the chosen hypothesis gates real implementation work, pass the ranked list (especially the `Top riskiest assumptions`) to `/codex-review --hypothesis` for a cross-model adversarial pass before you build on it. That review presumes the loop already exists; this phase is what produces the hypothesis it reviews.

## Phase 4 — Instrument

Map each probe to a specific prediction from Phase 3. **Change one variable at a time.**

Tool preference:

1. **Debugger / REPL inspection** when the env supports it. One breakpoint beats ten logs.
2. **Targeted logs** at the boundaries that distinguish hypotheses.
3. Reach past "log everything and grep"; it drowns the signal.

**Tag every debug log** with a unique prefix, e.g. `[DEBUG-a4f2]`. Cleanup at the end becomes a single grep. Untagged logs survive; tagged logs die.

**Perf branch.** For performance regressions, logs are usually the wrong tool. Establish a baseline measurement (timing harness, `performance.now()`, profiler, query plan), then bisect. Measure first, fix second; this is the **Measure, don't guess** principle applied to the perf loop.

## Phase 5 — Fix + regression test

Write the regression test **before the fix**, when a **correct seam** exists for it. Test-before-implementation is the house default; the seam check is what makes it honest here.

A correct seam exercises the **real bug pattern** as it occurs at the call site. When the only available seam is too shallow (a single-caller test for a bug that needs multiple callers; a unit test that cannot replicate the chain that triggered the bug), a regression test there gives false confidence.

**When no correct seam exists, that itself is the finding.** Note it. The codebase architecture is preventing the bug from being locked down. Flag it for Phase 6.

When a correct seam exists:

1. Turn the minimised repro into a failing test at that seam.
2. Watch it fail.
3. Apply the fix.
4. Watch it pass.
5. Re-run the Phase 1 feedback loop against the original (un-minimised) scenario.

## Phase 6 — Cleanup + post-mortem

Required before declaring done:

- [ ] Original repro no longer reproduces (re-run the Phase 1 loop)
- [ ] Regression test passes (or absence of a seam is documented)
- [ ] All `[DEBUG-...]` instrumentation removed (`grep` the prefix)
- [ ] Throwaway prototypes deleted, or moved to a clearly-marked debug location (per CLAUDE.md, move files to `~/to-delete/` and log them rather than deleting in place)
- [ ] The hypothesis that turned out correct is stated in the commit / PR message, so the next debugger learns

**Then ask: what would have prevented this bug?** When the answer involves architectural change (no good test seam, tangled callers, hidden coupling), hand off to the `/improve-codebase-architecture` skill with the specifics (the seam that was missing, the callers that were tangled, the coupling that hid the bug). Make the recommendation **after** the fix is in, not before; you have more information now than when you started.

Run `/verify` as a post-implementation self-check on the fix and regression test, then `/review` before committing.

Ported from mattpocock/skills (skills/engineering/diagnosing-bugs), release mattpocock-skills@1.0.0.
