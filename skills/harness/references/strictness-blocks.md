# Strictness Blocks

Three text blocks injected into the Stage B evaluator prompt via `{{strictness}}`. Strictness is orthogonal to adversarial framings - it modifies the evaluator's accept/reject threshold, while framings modify what the evaluator looks for.

## Blocks

### strict

```
### Strictness: Strict

Apply a high bar for acceptance. Only accept implementations that are unambiguously correct -
fixing a clear bug, handling a documented edge case, or satisfying a criterion with zero
interpretation. When in doubt, FAIL. Surface ambiguity as evidence rather than resolving it
charitably. A "close enough" implementation is a FAIL under strict evaluation.
```

### standard

Empty string - no text injected. The evaluator uses its default judgment without a strictness modifier. This is the default for all invocations.

### lenient

```
### Strictness: Lenient

Apply a low bar for acceptance. Accept implementations unless they clearly violate a criterion
or introduce a demonstrable bug. When in doubt, PASS. Minor deviations from the literal
criterion text are acceptable if the intent is clearly satisfied. Style issues and debatable
design choices are not grounds for FAIL under lenient evaluation.
```

## Injection Point

The `{{strictness}}` template variable appears in the Stage B evaluator prompt, immediately after the adversarial framing preamble. This means:

1. Framing sets *what the evaluator looks for* (security gaps, spec violations, etc.)
2. Strictness sets *how strictly it judges what it finds* (high bar vs low bar)

## Interaction with Framings

Strictness and framings are independent dimensions. Any combination is valid:

| Combination | Effect |
|-------------|--------|
| security-audit + strict | Maximum scrutiny: looks for security issues with zero tolerance |
| security-audit + lenient | Looks for security issues but only fails on clear vulnerabilities |
| specification-lawyer + strict | Literal criterion reading with zero interpretation charity |
| specification-lawyer + lenient | Criterion checking with reasonable interpretation of intent |
| maintainability + strict | Flags any code a future reader might struggle with |
| maintainability + lenient | Only flags genuinely opaque or dangerous patterns |

## Recommended Combinations by Task Type

| Task type | Recommended strictness | Rationale |
|-----------|----------------------|-----------|
| Auth / payment / encryption | strict | False negatives (missing a real issue) are expensive |
| Public API contracts | strict | Breaking changes affect external consumers |
| Internal refactors | standard | Default judgment is appropriate |
| Cosmetic / UI changes | lenient | Style-level issues shouldn't block |
| First iteration of new feature | lenient | Get something working before tightening |
| Final iteration before ship | strict | Last pass should catch edge cases |
| Bug fix (targeted) | standard | Fix the bug, don't scope-creep |

## CLI Usage

```
/harness --strictness strict    # High bar
/harness --strictness standard  # Default (no injection)
/harness --strictness lenient   # Low bar
```

When `--strictness` is not passed, defaults to `standard` (no text injected).
