<!-- keywords: fowler, code smell, maintainability, refactoring, feature envy, shotgun surgery, refused bequest, long method, long function, duplicated code, data clumps, primitive obsession, repeated switches, divergent change, speculative generality, message chain, middle man, mysterious name -->
# Code Smell Baseline

A fixed, always-on maintainability lens for diff review: a curated subset of Martin Fowler's "Bad Smells in Code" (_Refactoring_, ch. 3). It layers onto `/review` Step 4, the inline `/verify` smell check, and the manual `code-reviewer` role. Keep it out of the independent `breadth` review pass so that pass contributes a separate signal instead of sharing this checklist.

The smell **names are the payload**. Each name is a compact cue that activates a familiar refactoring pattern; the cue and fix bound that pattern so it stays precise.

**Two rules bind every smell:**

- **The repo overrides.** A documented repo standard, or `code-quality-principles.md`, wins. Suppress a smell when the local standard endorses the design.
- **Use judgement.** Label each smell as a heuristic (for example, "possible Feature Envy"), and leave mechanically enforced rules to tooling.

## Quick Nav - hunk-level smells

Judge these on the diff plus the full file already in context.

| Smell | Diff cue | Fix / pointer |
|-------|----------|---------------|
| **Mysterious Name** | A name needs a comment to say what it holds or does (`data`, `tmp`, `mgr`, `handle`) | Rename to intent; if no honest name emerges, revisit the design. See `code-quality-principles.md` (Comment Discipline, Elegance Standard). |
| **Duplicated Code** | The same logic shape appears 3+ times **with the same reason to change** | Extract and share, gated by the rule of three: two copies are not yet Duplicated Code. See `code-quality-principles.md` (Elegance Standard). |
| **Data Clumps** | The same fields or parameters **keep** travelling together across several sites (`x,y,w,h`; `start,end`) | Bundle them into one type. A one-off co-occurrence in a single function is not a clump. |
| **Primitive Obsession** | A raw string, integer, or float stands in for a domain concept (`role == "admin"`, money as float) | Give the concept a small type or enum. See `code-quality-principles.md` (Elegance Standard, Non-Defensive Coding). |
| **Speculative Generality** | Abstraction, parameters, or hooks serve needs the specification does not have | Delete or inline until a real need appears. See `code-quality-principles.md` (Killing AI Slop). |
| **Message Chains** | A long `a.b().c().d()` navigation exposes object structure to the caller | Ask the first object for the result and hide the walk. |
| **Middle Man** | A class or function mostly delegates onward | Inline it and call the real target. See `code-quality-principles.md` (Killing AI Slop). |

## Quick Nav - codebase-level smells

These require object-level context that a bare hunk cannot hold. Grep the surrounding code before reporting one, or mark the candidate as needing whole-repo confirmation.

| Smell | Diff cue | Fix / how to confirm |
|-------|----------|----------------------|
| **Feature Envy** | A method uses another object's data **far** more than its own | Move the method to the data it envies after checking the envied type's call sites. A brief single access is not envy. |
| **Repeated Switches** | The same `switch` or `if` cascade appears on the same type tag | Replace repeated dispatch with polymorphism or one shared map. Confirm by grepping the tag across files. |
| **Shotgun Surgery** | One logical change forces scattered edits across many files | Gather the changing behavior into one module. Confirm across the whole changeset. |
| **Divergent Change** | One file or module changes for several unrelated reasons | Split it so each module has one reason to change. Confirm multiple concerns or history. |
| **Refused Bequest** | A subclass or implementer ignores or overrides most inherited behavior | Replace the inheritance relationship with composition after reading the parent class. |

## Deliberately covered elsewhere

- **Comments and Loops:** too broad for reliable diff-only findings.
- **Long Parameter List, Large Class, Long Method / Long Function:** `/review` and language tooling already carry concrete mechanical checks.
- **Dead Code:** the normal review checklist owns the mechanical check.
