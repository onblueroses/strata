---
name: pickup-context
description: Build a compact, evidence-backed orientation when resuming work or asking what to do next.
---

# Pickup Context

## Outcome contract

- Goal: identify the live objective, binding constraints, current repository state, and safest next action.
- Success: each material claim has a source; stale or truncated context is narrowed; unknowns remain explicit.
- Does not count: a generic summary, guessed session state, or an external write.
- Stop: return one orientation brief when the available sources agree, or name the exact contradiction or blocker.

## Workflow

1. Resolve the working directory and repository root. Read every applicable `AGENTS.md` or equivalent instruction file. Inspect branch, status, recent history, and active specification files.
2. Read the configured memory adapter when one exists. Keep the read bounded. Narrow truncated results before relying on them. Treat unavailable memory as an explicit condition.
3. Read the configured work or issue ledger when one exists. Treat current status and signed comments as work evidence, not as a replacement for repository facts.
4. Search the configured decision record before reopening an architectural direction. Apply its recorded reopening condition.
5. Apply the instruction hierarchy and binding decisions throughout. For factual disagreements, verify current files and executable state against the active specification, current ledger evidence, and memory. Surface unresolved conflicts rather than silently overriding a requirement.

## Return

Return a brief with the live objective and evidence, active work and repository state, binding warnings and decisions, unknowns, and the next concrete action. Keep the workflow read-only. Do not assume a particular memory tool, issue tracker, path, account, or API.
