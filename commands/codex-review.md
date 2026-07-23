---
description: |
  One-shot adversarial review by Codex (xhigh reasoning) for non-diff artifacts: plans, debugging hypotheses, architecture decisions. Returns categorized findings (BLOCKING / IMPORTANT / ADVISORY) plus AGREE notes for anti-bias balance. One-shot, no loop; use /harness when iterative correction is needed.

  MANDATORY after /spec writes a plan touching 3+ files or 3+ phases, before the user starts implementation (operationalizes the CLAUDE.md 'Codex plan review' rule).

  Triggers on: 'have Codex review this', 'run this past Codex', 'second opinion', 'adversarial check', 'cross-model review', 'sanity check this plan', 'what would Codex say', 'review the hypothesis', 'check this architecture decision', 'is this plan sound'.

  Also triggers when: the user proposes a non-trivial debugging hypothesis that gates real implementation work; an architecture decision is being locked in; a research/scientific plan with empirical claims is about to be executed; a proposal-shaped artifact (deliverables, timeline, budget framing) is up for review; a plan whose outputs touch users, subjects, or third parties asymmetrically is being finalized.

  Manual: /codex-review --plan path/to/spec.md, /codex-review --hypothesis 'the bug is X' --evidence path/to/log, /codex-review --arch 'decision text or path/to/decision.md'.
---

# /codex-review

Thin redirect to the canonical skill body at `$STRATA_HOME/skills/codex-review/SKILL.md`. Load that file and follow the protocol it defines.

## Invocation modes

- `/codex-review --plan <path-or-text>` — procedural review of a frozen plan or spec; PDMC remains a separate frontier gate.
- `/codex-review --hypothesis <text> [--evidence <path>]` — adversarial review of a debugging theory against its evidence.
- `/codex-review --arch <path-or-text>` — contrarian review of an architecture decision and its tradeoffs.

For framing selection, privacy preprocessing, panel behavior, invocation details, and result reporting, read `$STRATA_HOME/skills/codex-review/SKILL.md` start-to-finish.
