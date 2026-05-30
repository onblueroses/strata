---
name: security-review
description: |
  Mandatory security review gate for code and architecture. Run a 7-step workflow:
  threat model, review against security checklist, emulate attack paths, mitigate
  findings, pen-test mitigations, deliver. Acts as a security-conscious reviewer
  with Security+ knowledge covering auth, authz, encryption, logging, input validation,
  segmentation, privacy, and common vulnerability patterns.
  Auto-trigger: when the user asks to review security, threat model, harden, pen test,
  or check for vulnerabilities. Also auto-trigger when writing authentication, authorization,
  cryptographic, or payment-handling code.
---

# Security Review Skill

Every security-sensitive code path and every explicit security request passes through this gate.

## Core Identity

Operate as a security-focused reviewer with Security+ certification knowledge. The entire
internet of breach postmortems, CVE databases, and OWASP reports has been ingested — use
that pattern recognition to predict and prevent the next disaster, not recreate the last one.

## When This Skill Activates

Specifically:

- **Explicitly** when the user asks for security review, threat modeling, hardening, or pen testing
- **When writing authentication, authorization, or cryptographic code**
- **When designing architecture** or system interactions involving data flow, trust boundaries, or external APIs
- **When reviewing existing code** the user provides for security issues

## Mandatory Workflow

<details>
<summary>Mandatory Workflow</summary>

Every qualifying task follows this sequence. Do not skip steps.

```
1. PLAN REVIEW        → Evaluate the plan against the security checklist
2. THREAT MODEL       → Identify assets, threats, attack surfaces
3. SECURE IMPL        → Write code that embeds security controls from the start
4. ATTACK EMULATION   → Agentically walk each attack path from the threat model
5. MITIGATE           → Fix every finding from step 4
6. PEN TEST           → Agentically re-test mitigations; confirm they hold
7. DELIVER            → Only after steps 1-6 pass
```

### Step 1: Plan Review

Before writing any code, review the plan against the security checklist.
Load and apply `references/security-checklist.md` if available, otherwise apply the
embedded checklist below.

For each checklist category, answer:
- Does the plan address this? (yes / no / not applicable)
- If no: what must change before implementation begins?

Block implementation until all applicable categories are addressed.

**Embedded Security Checklist (use when references/security-checklist.md unavailable):**

| Category | Key Questions |
|----------|---------------|
| Authentication | Who can authenticate? MFA? Session expiry? Brute force protection? |
| Authorization | Default-deny? Least privilege? Role checks at every endpoint? |
| Input Validation | Allowlist over denylist? Validated at boundary? Injection risks? |
| Output Encoding | HTML encoding? SQL parameterization? Shell escaping? |
| Secrets Management | No secrets in code/logs/URLs? Env vars or secret stores only? |
| Cryptography | TLS in transit? Encryption at rest for PII? No custom crypto? |
| Logging & Monitoring | Auth events logged? No PII/secrets in logs? Alerting on anomalies? |
| Error Handling | Fail closed? Generic messages to users, details to logs? |
| Dependencies | Pinned versions? Known CVEs checked? Minimal surface? |
| Least Privilege | Minimum permissions for each component, user, service? |
| Network Segmentation | Trust levels isolated? Control plane from data plane? |
| Privacy | Minimal collection? Purpose-limited? Deletion supported? |

### Step 2: Threat Model

Produce a lightweight threat model covering:

1. **Assets** — What is being protected? (data, credentials, sessions, PII, secrets, availability)
2. **Trust boundaries** — Where do privilege levels change? (client/server, service/service, user/admin, internal/external)
3. **Entry points** — Every input surface (API endpoints, form fields, file uploads, CLI args, env vars, message queues, webhooks)
4. **Threat actors** — Who attacks this? (anonymous internet user, authenticated low-priv user, compromised dependency, malicious insider, automated scanner)
5. **Attack paths** — For each entry point × threat actor, enumerate concrete attack scenarios
6. **Risk rating** — Rank each path: Critical / High / Medium / Low based on impact × likelihood

Format as a numbered list of attack paths with ratings so step 4 can reference them by number.

**Evidence Rule:** Every trust boundary, entry point, and attack path must cite
at least one file:line as evidence (e.g., `src/auth/middleware.ts:42`). If you
cannot cite a specific location, mark the item as ASSUMPTION and list what you
would need to verify it. Findings without evidence or ASSUMPTION labels are
invalid.

### Step 3: Secure Implementation

Write code with security controls baked in from line one. Non-negotiable defaults:

- **Authentication**: Verify identity before any privileged operation. No implicit trust.
- **Authorization**: Check permissions at every access point. Default-deny.
- **Input validation**: Validate, sanitize, and reject bad input at the boundary. Allowlists over denylists.
- **Output encoding**: Context-appropriate encoding for every output (HTML, SQL, shell, logs).
- **Encryption**: TLS in transit. Encrypt sensitive data at rest. Use vetted libraries, never roll custom crypto.
- **Secrets management**: No secrets in code, logs, URLs, or error messages. Use env vars or secret stores.
- **Logging and monitoring**: Log security-relevant events (auth attempts, access control decisions, input validation failures). Never log secrets or PII.
- **Error handling**: Fail closed. Generic error messages to users; detailed errors to logs only.
- **Dependency hygiene**: Pin versions. Prefer well-maintained libraries. Minimal dependency surface.
- **Least privilege**: Minimum permissions for every component, user, service account, and process.
- **Segmentation**: Isolate components by trust level. Separate data planes from control planes.
- **Privacy**: Minimize data collection. Purpose-limit data use. Support deletion.

### Step 3.5: Codex Security Review

Before attack emulation, run Codex as an adversarial security reviewer to catch issues from a second-model perspective:

```bash
timeout 600 codex -c model_reasoning_effort='"xhigh"' review --uncommitted
```

- Uses `xhigh` reasoning + `~/.codex/AGENTS.md` adversarial priming for maximum security depth.
- Any security-relevant findings are added to the attack paths list for Step 4 emulation.
- If Codex identifies attack vectors not in the threat model, add them as supplementary paths.
- If Codex is unavailable or errors, log "Codex: skipped" and continue to Step 4.

### Step 4: Attack Emulation

For each attack path identified in step 2 (plus any from Codex in step 3.5), agentically emulate the attack:

1. Read the code or configuration you just wrote
2. Trace the attack path through the actual implementation
3. Attempt to construct a concrete exploit or proof-of-concept (in comments/pseudocode — do not produce weaponized exploits)
4. Document result: **BLOCKED** (control stops it) or **VULNERABLE** (attack succeeds or partially succeeds)

If ANY path returns VULNERABLE, proceed to step 5. If all paths return BLOCKED, skip to step 6.

### Step 5: Mitigate

For each VULNERABLE finding:

1. Identify the root cause (missing control, misconfiguration, logic flaw)
2. Implement the fix in the actual code
3. Verify the fix does not break functionality
4. Mark the finding as MITIGATED

Return to step 4 and re-run emulation only on the paths that were VULNERABLE.
Repeat the step 4 / step 5 cycle until all paths return BLOCKED.

### Step 6: Pen Test Verification

Final pass — agentically test the complete implementation:

1. Re-run all attack paths from step 2 against the final code
2. Additionally test for issues not in the original threat model:
   - Race conditions and TOCTOU
   - Integer overflow / underflow
   - Path traversal beyond documented inputs
   - Deserialization attacks if serialization is used
   - Dependency confusion if packages are installed
3. Verify all logging produces expected output for security events
4. Confirm error handling does not leak internals
5. Check that all secrets are externalized

All paths must return BLOCKED. Any failure loops back to step 5.

### Step 7: Deliver

Only after all steps pass, deliver the code with a brief security summary:

```
## Security Summary
- Threat model: X attack paths analyzed
- Controls: [list key controls implemented]
- Pen test: All paths BLOCKED
- Residual risks: [anything the user should know]
```

</details>

## Quality Self-Check

After delivering the security summary, verify:
1. **No threat paths skipped** - does every attack path from step 2 have a BLOCKED/VULNERABLE result?
2. **Controls match threats** - does each identified threat have a corresponding control in the implementation?
3. **No residual risks hidden** - did you disclose anything that's mitigated-but-not-eliminated?
4. **Pen test actually tested** - did step 6 re-run the specific attack paths, or just assert "looks good"?
5. **Secrets externalized** - grep the output code for any hardcoded strings that look like keys, tokens, or passwords.

## Lightweight Mode

For trivial code (e.g., a pure formatting function with no I/O, no auth, no network, no data):

1. Scan the security checklist mentally
2. Confirm nothing applies
3. Note "Security review: no applicable attack surface" and deliver

If there is **any doubt**, run the full workflow.

## Common Anti-Patterns (Real-World Breach Origins)

| Pattern | Risk | Example Breach |
|---------|------|----------------|
| Hardcoded credentials | Critical | Multiple supply chain attacks |
| Missing authorization check | Critical | IDOR vulnerabilities everywhere |
| SQL string concatenation | Critical | Equifax breach vector |
| `eval()` on user input | Critical | Code injection |
| MD5/SHA1 for passwords | High | Countless credential dumps |
| Verbose error messages | Medium | Information disclosure |
| No rate limiting on auth | High | Credential stuffing |
| JWT without signature verification | Critical | Auth bypass |
| CORS `*` on sensitive APIs | High | Cross-origin data theft |
| Logging request bodies | Medium | PII/secret exposure in logs |

## Reference Files

If available in the skill directory:
- `references/security-checklist.md` — Category-level checklist applied in step 1
- `references/anti-patterns.md` — Known-bad patterns from real-world breaches
- `references/attack-emulation-guide.md` — Per-vulnerability-class emulation methodology
- `references/nextjs-security-rules.md` — Next.js-specific security rules with IDs and detection patterns
