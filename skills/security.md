# Security

Security bugs are the most expensive kind. Check before shipping.

## Input Validation

- All user input validated and sanitized at the system boundary
- SQL queries use parameterized statements, never string concatenation
- HTML output escapes user-provided content (prevent XSS)
- File paths from user input canonicalized and checked against allowed directories
- URL redirects validated against an allowlist (prevent open redirect)

## Authentication & Authorization

- Auth checks on every protected endpoint (not just the UI)
- Passwords hashed with bcrypt/argon2/scrypt, never MD5/SHA
- Session tokens are cryptographically random with sufficient length
- Token expiry enforced server-side
- Failed auth attempts rate-limited

## Secrets Management

- No secrets in code, config files, or git history
- API keys scoped to minimum required permissions
- Secrets rotated on any suspected exposure
- Different secrets for dev, staging, production

## Common Vulnerabilities

| Vulnerability | Mechanical Test |
|--------------|-----------------|
| SQL injection | String concatenation in a query? |
| XSS | User input rendered without escaping? |
| CSRF | State-changing endpoint without CSRF token? |
| Path traversal | User input in file paths without canonicalization? |
| Insecure deserialization | Untrusted data passed to deserialize/unpickle/eval? |
| Hardcoded secrets | `grep -rE "(sk-\|ghp_\|AKIA\|password\s*=)" .` |

## Anti-Examples

| Bad | Why | Better |
|-----|-----|--------|
| `eval(userInput)` | Remote code execution | Parse structured input with a safe parser |
| `SELECT * FROM users WHERE id = ${id}` | SQL injection | Parameterized queries |
| Checking auth in the frontend only | Trivially bypassed | Server-side auth on every endpoint |
| `cors: { origin: '*' }` in production | Any site can make authenticated requests | Explicit origin allowlist |
| Logging full request bodies | May contain passwords, tokens, PII | Log only structured, sanitized fields |

## Quality Self-Check

Before shipping code that touches security:
1. All user inputs validated at the system boundary?
2. No secrets in code or committed config?
3. Auth checked server-side on every protected path?
4. Error messages don't leak internal details (stack traces, DB schemas)?
