# Structured Evidence Schema

Every evaluator verdict (PASS or FAIL) must include a 5-field structured evidence block. This forces the evaluator to reason through consequences rather than pattern-matching "looks wrong" or rubber-stamping "looks fine."

## XML Verdict Template

```xml
<verdict criterion="C1" result="PASS|FAIL">
  <staged>What the current implementation does for this criterion</staged>
  <fix>What would need to change (for FAIL) or why nothing needs to change (for PASS)</fix>
  <rationale>Why this verdict - the objective issue or its absence</rationale>
  <if-accepted>Consequence if this implementation ships as-is</if-accepted>
  <if-rejected>Consequence if this implementation is sent back for rework</if-rejected>
</verdict>
```

All 5 child elements are required on every verdict. Missing elements invalidate the verdict - the orchestrator re-prompts the evaluator.

## Field Semantics

| Field | Purpose | Bad example | Good example |
|-------|---------|-------------|--------------|
| `staged` | Describe what the code actually does | "Handles auth" | "src/auth.ts:15 - checks JWT expiry via `Date.now() > payload.exp * 1000`, returns 401 on failure" |
| `fix` | What specifically changes (FAIL) or why no change needed (PASS) | "Needs fixing" | "Missing `* 1000` conversion - `payload.exp` is Unix seconds, `Date.now()` is milliseconds" |
| `rationale` | The objective reason for the verdict | "Looks wrong" | "Off-by-1000x comparison means all tokens appear expired, breaking auth for every request" |
| `if-accepted` | What happens if this ships | "Could cause issues" | "All authenticated requests return 401; users cannot access protected endpoints" |
| `if-rejected` | What happens if sent back | "Gets fixed" | "Generator must fix the timestamp comparison; 1-line change, no structural risk" |

## PASS Verdict Example

```xml
<verdict criterion="C1" result="PASS">
  <staged>src/api/resource.ts:15 - validates JWT via jsonwebtoken.verify(), extracts user_id from payload, queries database with parameterized query</staged>
  <fix>No change needed - token validation, payload extraction, and database query are all correct</fix>
  <rationale>JWT verification uses the correct secret from env, parameterized query prevents injection, user_id type matches database schema</rationale>
  <if-accepted>Authenticated users access their resources correctly; token forgery is rejected by signature verification</if-accepted>
  <if-rejected>Unnecessary rework on a correct implementation; wastes a generator iteration</if-rejected>
</verdict>
```

## FAIL Verdict Example

```xml
<verdict criterion="C2" result="FAIL">
  <staged>src/api/resource.ts:28 - catch block returns `res.status(401).end()` with no response body</staged>
  <fix>Return structured error body: `res.status(401).json({ error: 'unauthorized', message: 'Invalid or expired token' })`</fix>
  <rationale>Criterion C2 requires "structured error body on 401" - empty response violates the literal requirement and breaks API clients that parse error responses</rationale>
  <if-accepted>API clients receive empty 401 responses, cannot distinguish between expired token, invalid token, or missing token - debugging becomes guesswork</if-accepted>
  <if-rejected>Generator adds error body to the catch block; minimal change, well-scoped fix</if-rejected>
</verdict>
```

## Strict Improvement Criteria (for Fixer Arbitration)

When the evaluator arbitrates between generator originals and fixer changes, a fix is a **strict improvement** if and only if ALL of:

1. **Objective correctness** - fixes something demonstrably wrong (would fail, crash, or violate a criterion)
2. **Intent preservation** - the generator's design decisions remain intact
3. **Minimal scope** - the change addresses only the identified issue
4. **No side effects** - the change doesn't alter behavior for cases already handled correctly

Accept patterns: missing null check, missing await, off-by-one, injection fix, resource leak, missing error handling.
Reject patterns: refactors approach, changes error strategy, removes optional features, restructures code.
