---
description: |
  Review a plan, debugging hypothesis, or architecture decision with Codex. MANDATORY after /spec writes a plan touching 3+ files or 3+ phases.
  Triggers on: 'have Codex review this', 'run this past Codex', 'second opinion', 'adversarial check', 'cross-model review', 'sanity check this plan', 'what would Codex say', 'review the hypothesis', 'check this architecture decision', 'is this plan sound'.
  Also triggers for a load-bearing hypothesis, architecture choice, empirical plan, or consequential proposal. Manual: /codex-review --plan, --hypothesis, or --arch.
---

# /codex-review

Thin redirect to the canonical skill body at `$STRATA_HOME/skills/codex-review/SKILL.md`. Load that file and follow the protocol it defines.

## Invocation modes

- `/codex-review --plan <path-or-text>` — procedural review of a frozen plan or spec; PDMC remains a separate frontier gate.
- `/codex-review --hypothesis <text> [--evidence <path>]` — adversarial review of a debugging theory against its evidence.
- `/codex-review --arch <path-or-text>` — contrarian review of an architecture decision and its tradeoffs.

For framing selection, privacy preprocessing, panel behavior, invocation details, and result reporting, read `$STRATA_HOME/skills/codex-review/SKILL.md` start-to-finish.
