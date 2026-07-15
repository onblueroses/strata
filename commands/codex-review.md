---
name: codex-review
description: "One-shot adversarial review by Codex (xhigh reasoning) for non-diff artifacts: plans, debugging hypotheses, architecture decisions. Cross-model asymmetry breaks Claude's same-model bias by construction — Codex catches blindspots a same-model self-review normalizes. Returns categorized findings (BLOCKING / IMPORTANT / ADVISORY) plus AGREE notes for anti-bias balance. One-shot, no loop — use /harness when iterative correction is needed. For diff/code review, /verify (Full/Deep) and /review already invoke Codex via `codex review --uncommitted`, so do not duplicate. MANDATORY after /spec writes a plan touching 3+ files or 3+ phases, before the user starts implementation (operationalizes the CLAUDE.md 'Codex plan review' rule). Triggers on: 'have Codex review this', 'run this past Codex', 'second opinion', 'adversarial check', 'cross-model review', 'sanity check this plan', 'what would Codex say', 'review the hypothesis', 'check this architecture decision', 'is this plan sound'. Also triggers when: the user proposes a non-trivial debugging hypothesis that gates real implementation work; an architecture decision is being locked in; a research/scientific plan with empirical claims is about to be executed; a proposal-shaped artifact (deliverables, timeline, budget framing) is up for review; a plan whose outputs touch users, subjects, or third parties asymmetrically is being finalized. Pairs with /spec (upstream — codex-review fires after spec writes), /harness (downstream — when iterative gen-eval is needed), /cross-model-critique (kin — same triage discipline applied to pasted external AI feedback). Manual: /codex-review --plan path/to/spec.md, /codex-review --hypothesis 'the bug is X' --evidence path/to/log, /codex-review --arch 'decision text or path/to/decision.md'."
tier: core
cost_hint: high
parallelizable: false
when_to_use: Before executing a non-trivial plan, debugging hypothesis, or architecture decision
---

# /codex-review

Goal: Return an independent adversarial review of a plan, debugging hypothesis, or architecture decision from a frozen artifact.

Success means:
  - Each selected framing runs from the same artifact and criteria with session reasoning excluded.
  - The merged report contains AGREE notes, severity-tagged findings, and exactly one `PROCEED`, `PROCEED_WITH_CONCERNS`, or `BLOCK` verdict.
  - Parallel panels launch every framing before any result is read; sequential single-framing calls retain the same output contract.

Stop when: The one-shot report is delivered and its findings are triaged; iterative correction escalates to `/harness`.

One-shot adversarial review by Codex. Hands the artifact, criteria, and minimal context to Codex via direct CLI - never the chat history, never your reasoning chain. This codifies the "Codex plan review" procedure documented in CLAUDE.md so you don't reconstruct it from prose every time.

## When to use this vs other Codex paths

| Need | Tool | Why |
|------|------|-----|
| Review a plan/spec before implementation | **/codex-review --plan** | Plans aren't diffs - need a prompt-based review |
| Review a debugging hypothesis | **/codex-review --hypothesis** | Theory needs adversarial probe, not git diff |
| Review an architecture decision | **/codex-review --arch** | Tradeoffs need a contrarian, not a code reviewer |
| Review staged code before commit | **/review** | Already invokes `codex review --uncommitted` |
| Review edited files post-implementation | **/verify --deep** (or Full) | Already invokes `codex review --uncommitted` |
| Iterative implementation with rework | **/harness** | When you need a generate-evaluate loop |

If the artifact under review is a git diff, this is the wrong tool.

## Skip Conditions

- **Skip if** the artifact is trivial (single-file change, 1-2 phases, no architectural choice)
- **Skip if** the user has already explicitly accepted this plan and just wants execution
- **Skip if** Codex CLI is unavailable - degrade gracefully and tell user, do not silently proceed

## The Asymmetry Principle

Codex must NOT see:

- The conversation history that produced the artifact
- Your (Claude's) reasoning chain or stated intent
- A summary of what you think the artifact does
- Other /codex-review iterations on the same artifact

Codex SHOULD see:

- The artifact verbatim
- Acceptance criteria as binary PASS/FAIL gates where derivable
- Relevant existing files - by path, Codex reads them itself
- Project standing rules from CLAUDE.md (constraints, not bias)
- One adversarial framing per call; a panel dispatches several calls against the same frozen artifact

This asymmetry is the entire mechanism. If Codex inherits Claude's reasoning, it starts predisposed to agree (positivity bias from priming). Cutting that forces independent ground-up evaluation.

## Modes

### --plan: Plan review

For new specs from /spec, design docs, or implementation plans.

**Default framing:** `specification-lawyer-plan`. Add `contrarian-architect` and `failure-mode-analyst` as panel members when the artifact warrants multiple lenses.

**Inputs Codex sees:** plan text + file paths it will touch (Codex reads them) + extracted goal + framing.

**Inputs Codex does NOT see:** the conversation that asked for this plan, the Plan subagent's reasoning, prior /codex-review iterations.

**PDMC boundary:** `/codex-review --plan` is a procedural review, not a methodological review. It does not satisfy PDMC. If the plan contains `Harness: yes` or probe/harness methodology, report that a separate PDMC review pass is required before `PROCEED` is valid, using `/spec` Step 3.6 and `skills/spec/references/pdmc-checklist.md`.

### --hypothesis: Debugging hypothesis review

For debugging theories about what's causing a bug, before you act on them.

**Default framing:** `alternative-cause-finder`. Add `counterexample-finder` as a panel member when a second independent causal lens is warranted.

**Inputs:** hypothesis text + evidence files (logs, error output, repro steps) + suspected code files.

**Inputs Codex does NOT see:** what you've already ruled out, your confidence level, your previous theories.

The frame asks: "What other cause fits this evidence equally well?" and "What would make this hypothesis wrong?"

### --arch: Architecture decision review

For design decisions where alternatives exist.

**Default framing:** `tradeoff-analyst`. Add `contrarian-architect` as a panel member for high-stakes or difficult-to-reverse decisions.

**Inputs:** the decision + the alternatives considered + the constraints driving it + relevant current-architecture files.

**Inputs Codex does NOT see:** which alternative you preferred or why.

## Adversarial Framings

Framings are defined in `$STRATA_HOME/reference/codex-framings.md` (single source of truth). Each framing is a one-paragraph preamble injected at the top of Codex's prompt. Framings rotate per invocation against the same artifact to surface different blindspots.

**Quick selection** (full table in the reference doc):

| Mode | Default rotation chain |
|------|----------------------|
| `--plan` (engineering) | specification-lawyer-plan → contrarian-architect → failure-mode-analyst |
| `--plan` (research/scientific) | peer-reviewer → contrarian-architect → counterexample-finder |
| `--plan` (proposal/funding) | grant-committee → specification-lawyer-plan |
| `--plan` (user-facing / high-stakes) | ethics-board → failure-mode-analyst |
| `--hypothesis` | alternative-cause-finder → counterexample-finder |
| `--arch` | tradeoff-analyst → contrarian-architect |

Read the reference doc to load the full preamble for the chosen framing into the Codex prompt at Step 1 of the invocation. Do not paraphrase - copy verbatim. The wording is calibrated to counter specific bias classes.

**Parallel panel:** When the artifact is high-stakes, spans several characteristics, or previously produced structural findings, run one call per warranted framing in parallel. Build prompt files that differ only in framing, launch every call before reading any report, and merge after all calls exit. Deduplicate overlaps at the highest severity. See `$STRATA_HOME/reference/load-bearing-iteration.md`, "Adversarial Lenses Run in Parallel".

**Re-review:** Freeze the revised artifact as a new one-shot input, verify that prior BLOCKING findings were addressed, prefer framings not yet used, and keep prior reports out of each new prompt. Record the framing history in the report and, for spec reviews, in the spec Decisions table.

For implementation/code-quality framings used by `/harness` (security-audit, production-load, maintainability, adversarial-user, dependency-skeptic, reality-declaration), see `$STRATA_HOME/skills/harness/references/evaluator-framings.md`. Those target code that exists; the codex-framings doc targets plans/theories/decisions.

## Codex Invocation

<details>
<summary>Codex Invocation</summary>

Per CLAUDE.md: direct `codex` CLI via Bash with `run_in_background: true`. xhigh reasoning + fast service tier can take 5-15 minutes - longer than Bash's 10-minute foreground cap.

**Step 1: Build the prompt file** at `$STATE_DIR/codex-review-{session-id}-{epoch}-{framing}.md`, one file per framing. Keep every panel prompt identical except for its framing preamble:

```
{framing preamble}

You are reviewing a {plan|hypothesis|architecture decision}. You have NOT seen
the conversation that produced this artifact. Trust nothing - verify against
the criteria and the actual files.

PLAN/PDMC BOUNDARY:
If this is a plan review and the artifact includes `Harness: yes` or
probe/harness methodology, this review remains PROCEDURAL ONLY. Do not claim
methodological approval. Add `PDMC_REQUIRED: separate PDMC review required
before PROCEED is valid` to the output. PDMC uses items 1-15 from
skills/spec/references/pdmc-checklist.md and cannot be substituted by this
/codex-review --plan verdict.

ARTIFACT:
{verbatim content of the plan/hypothesis/decision}

ACCEPTANCE CRITERIA (binary PASS/FAIL where applicable):
{C1, C2, ... derived from the artifact's stated goal, OR "No explicit criteria
- judge against goal:" followed by the one-sentence goal}

FILES TO READ FROM DISK (do not assume contents):
{list of file paths the artifact references or affects}

PROJECT CONSTRAINTS:
{relevant CLAUDE.md rules - privacy, code quality, deployment, etc.}

RECON BRIEF (when present):

Ground-truth recon is owned upstream by the `/recon` skill (Claude invokes it before
calling /codex-review when an artifact carries load-bearing premises). If a recon brief
path appears in FILES TO READ FROM DISK (typically `/tmp/recon-{slug}.md`), treat it as
validated context — cite it like any other file:line evidence.

Verify any claim that gates a finding by reading the cited file:line yourself. Inherited
premises from the artifact text alone are not ground truth. If a load-bearing premise has
no recon coverage and you cannot verify it from the listed files, mark the finding
EVIDENCE: "unverified — recon coverage missing" rather than asserting.

OUTPUT FORMAT (required):

First, list 3-5 aspects of this artifact that are correctly handled:
  AGREE: <what's right> (evidence: <file:line or section>)

Then, list issues:
  [BLOCKING|IMPORTANT|ADVISORY] (<criterion-id-or-topic>): <description>
  EVIDENCE: <file:line or "artifact section X">
  FIX: <specific change>

Severity guide:
- BLOCKING: criterion failure, security hole, broken assumption, contradicts existing code
- IMPORTANT: correctness risk, scope drift, ambiguity that will cause rework
- ADVISORY: optional improvement, style, micro-optimization

Final line:
  VERDICT: PROCEED | PROCEED_WITH_CONCERNS | BLOCK

For --plan artifacts with `Harness: yes`, include before the final line:
  PDMC_REQUIRED: separate PDMC review required before PROCEED is valid

Rules:
- If you cannot find issues, say "No issues found" and explain in one sentence
  why the artifact looks sound.
- Do NOT recommend changes outside the artifact's scope.
- Do NOT critique style if logic is correct.
- Do NOT manufacture findings to seem thorough.
```

**Step 2: Privacy preprocessing.**

Before writing the prompt file, scrub these patterns from artifact text and any included context (Codex API calls leave the local machine):

- Real name from the user's CLAUDE.md privacy section → `[USER]`
- Private project codenames from CLAUDE.md → `[PRIVATE-PROJECT-N]` (number them so Codex can refer back)
- Private IPs (VPS, internal hosts, mesh VPN) from CLAUDE.md → `[PRIVATE-IP-N]`

Code logic remains intact; only identifiers change.

**Step 3: Invoke Codex.**

Use the canonical Codex flag set (see CLAUDE.md `Codex Invocation Standard` for flag rationale):

```bash
PROMPT="$STATE_DIR/codex-review-{session-id}-{epoch}-{framing}.md"
LOG="$STATE_DIR/codex-review-{session-id}-{epoch}-{framing}.log"
codex exec \
  --dangerously-bypass-approvals-and-sandbox \
  --skip-git-repo-check \
  -c tools.web_search=true \
  -c model_reasoning_effort=xhigh \
  -c service_tier=fast \
  --model <PICK_REVIEW_MODEL> \
  "$(cat "$PROMPT")" \
  < /dev/null \
  > "$LOG" 2>&1
```

Run with `run_in_background: true`. The `< /dev/null` is mandatory for backgrounded `codex exec`: an unclosed stdin socket hangs codex forever at 0 CPU on "Reading additional input from stdin". For a panel, launch every framing before reading any log; each launched process must have its own prompt and log under `$STATE_DIR`.

**Step 4: Monitor progress.** Use the Monitor tool on every log file. If a process produces no new output for 5+ minutes or repeats errors, kill that process and fall back per Failure Modes.

**Step 5: Read the result.** Once every call exits, read each full log. Parse AGREE notes, severity-tagged issues, and final verdicts, then merge panel findings into one deduplicated brief. Resolve the final report to exactly one allowed verdict and verify that severity counts match.

</details>

## Result Reporting

Present to the user in this fixed format:

```
CODEX REVIEW: <plan|hypothesis|arch> review of <artifact-name>
Framing(s): <framing used, or panel list>
========================================

AGREE (Codex confirmed):
- <agree note 1>
- <agree note 2>
...

ISSUES (<N> total: <blocking-count> blocking, <important-count> important, <advisory-count> advisory):

[BLOCKING] <topic>: <description>
  EVIDENCE: <file:line or section>
  FIX: <suggested change>

[IMPORTANT] ...

[ADVISORY] ...

PDMC_REQUIRED: <only for --plan artifacts with Harness: yes; separate PDMC review required before PROCEED is valid>

VERDICT: <PROCEED|PROCEED_WITH_CONCERNS|BLOCK>

Recommendation: <one-line action - revise, accept, escalate>
```

If Codex returns "No issues found", show that as-is plus a brief recap of what it confirmed. Do not pad.

## Integration (acting on the review)

When the user accepts the review and asks for revisions, sort every Codex finding into one of four buckets before touching the artifact. Read the full report once, classify all findings, *then* edit. Adapted from `/cross-model-critique` — Codex's different training distribution catches what same-model self-review normalizes.

- **PROTECT** — Codex's AGREE notes plus anything it explicitly praised. These are load-bearing walls; revision must not damage them. Mark them in the artifact before editing if there's ambiguity about which lines are "the strong ones."
- **DIAGNOSE** — Findings where Codex is correct and the artifact must change. Map each diagnosis to a specific file:line or section. If a finding is vague ("the rollback story is thin"), locate the exact spot before acting.
- **TRANSLATE** — Codex's vocabulary may not match the artifact's idiom. "Specification under-determines the failure path" might translate to "add a behavior-on-timeout subsection." Restate the finding in the artifact's own terms before editing — that surfaces whether the finding is genuinely actionable or just register-mismatch.
- **REJECT (with reason)** — Suggestions that would damage the artifact's design. Name *why* — "this would remove the agency inversion in the rollout sequencing" is a reason; "I prefer the current approach" is not. Reject sparingly and explicitly.

Sequence the edits: PROTECT first (mark inviolate), then DIAGNOSE (smallest interventions first — single-word fixes before passage rewrites before structural changes), then re-read the full artifact between levels. REJECT findings get a one-line note in the response back to the user so the rejected reasoning is visible, not silently dropped.

## Wiring (where this is invoked from)

- **/spec** Step 3.5 (after Plan subagent returns content, before writing the spec to disk for plans with 3+ files OR 3+ phases). The spec skill writes the proposed spec to a temp file, calls /codex-review --plan for procedural review only, then revises the spec with the BLOCKING + IMPORTANT findings before persisting. If any phase has `Harness: yes`, `/spec` Step 3.6 must run a separate PDMC methodological review before the spec can proceed.
- **/verify --deep** when reviewing a spec-driven phase whose output included structural decisions (the spec's Phase has `Harness: yes` AND harness flagged structural-failure escalation).
- Manually for ad-hoc plan / hypothesis / decision review.

## Failure Modes

| Failure | Recovery |
|---------|----------|
| Codex CLI not installed | Tell user, suggest install. No automatic fallback - the cross-model property is the whole point. |
| Codex auth failure | Tell user to run `codex auth`. Do not proceed silently. |
| Codex hung (no log output for 5 min) | Kill background process. Optionally retry once with `--effort high` instead of xhigh. |
| Codex output unparseable | Re-run once with explicit format reminder appended. If still malformed, present raw output and let user judge. |
| All findings are ADVISORY (cosmetic only) | Surface as PROCEED with a one-line note. Do not escalate as if BLOCKING. |
| All findings are BLOCKING (Codex went into "criticize everything" mode) | Suspect framing-induced bias. Surface as-is but flag the pattern in the recommendation; consider re-running with a different framing. |

## DO NOT

- **DO NOT include conversation history in the prompt.** The asymmetry depends on Codex starting fresh.
- **DO NOT include Claude's reasoning** for why the artifact looks correct. That biases Codex toward agreement.
- **DO NOT loop on findings.** This is one-shot. If iteration is needed, escalate to /harness.
- **DO NOT auto-apply Codex's fixes.** Surface findings; let Claude (or user) decide. Codex's "fix" suggestions are hypotheses, not directives.
- **DO NOT skip privacy preprocessing.** Scrub private names, IPs, project identifiers first.
- **DO NOT use without `run_in_background: true` + Monitor.** xhigh reviews routinely exceed the 10-minute Bash cap.
- **DO NOT use this for code/diff review.** /verify (Full/Deep) and /review already invoke Codex on diffs.
- **DO NOT escalate ADVISORY findings to the user.** Either fix them silently or surface as a brief note.
- **DO NOT use the codex:rescue subagent or codex plugin entrypoint** for the underlying invocation. Per CLAUDE.md, plan review uses direct codex CLI.
- **DO NOT modify the artifact under review** while Codex is running. The on-disk state must match what's in the prompt.

## Quality Self-Check

Before reporting verdict to user:

1. **Codex prompt file exists** under `$STATE_DIR` with all required sections (one file per panel framing: framing, artifact, criteria, files, constraints, output format)
2. **Privacy preprocessing applied** - grep the prompt file for known private patterns; should find none
3. **Codex was actually invoked** with xhigh + fast tier, in background
4. **Log file fully captured** before parsing - check Codex's exit status
5. **Severity counts match** the parsed findings after panel deduplication
6. **AGREE notes present** if any aspects were confirmed (anti-bias requirement)
7. **VERDICT line parsed** correctly - one of three values, no improvisation
8. **No conversation context leaked** into the prompt file (re-read; should contain only artifact + criteria + framing)
9. **PDMC boundary honored** - for `--plan` artifacts containing `Harness: yes`, the report includes `PDMC_REQUIRED` and does not treat the procedural verdict as methodological approval
