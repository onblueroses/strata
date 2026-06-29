---
name: verify
description: "Post-implementation integrity gate with risk-based tiers. Classifies edited files by risk (Skip/Light/Full/Deep) and runs proportional checks. Skip auto-passes for knowledge-base files (`$STRATA_HOME/skills/**/*.md`, `$STRATA_HOME/reference/**/*.md`, `.claude/projects/*/memory/**/*.md`, `$KB_DIR/**/*.md`, etc.). Light runs inline checks for 1-3 code files in a single project (re-read, debris scan, tests). Full uses Codex review (`codex review --uncommitted`) plus inline mechanical checks for 4+ files or multi-project work. Deep requires explicit --deep flag for spec-driven multi-phase work (extended doc-currency, import-graph, config-affects-runtime trace). MANDATORY after editing files, before reporting task completion — the Stop hook (verify-gate.sh) auto-passes Skip-tier sessions and blocks all others until /verify passes. Triggers on: 'verify', '/verify', 'verify the changes', 'check the work', 'integrity check', 'before I close out', 'pre-completion check', 'did everything pass'. Also triggers when: files have been edited this session and the user is about to report task completion or end the session; the Stop hook fires with 'VERIFICATION REQUIRED' or 'FILES EDITED AFTER VERIFICATION' messages; /end is about to run (verify must pass first). Pairs with /review (downstream — review runs after verify), /end (downstream — end requires verify marker), /spec (Deep tier checks spec currency). Marker file at $STATE_DIR/.verify-passed-{sessionId} is the receipt the Stop hook checks. Manual invocation: /verify or /verify --deep."
tier: core
cost_hint: medium
parallelizable: false
when_to_use: After editing files, before reporting task completion
---

# Verify

Goal: Validate edited files by risk tier and emit a deterministic `/verify` result for the stop gate.
Success means:
  - Tier classification follows the existing Skip/Light/Full/Deep rules and the highest-risk file controls the session tier.
  - Selected tier checks run with current file-path patterns, command examples, marker path, and pass/fail semantics unchanged.
  - PASS writes the marker file and FAIL does not; the final output uses the required `VERIFY:` format.

Stop when: The selected tier completes and a single PASS/FAIL verdict is produced.

Classify edited files by risk (Skip/Light/Full/Deep) and run proportional checks from zero-cost auto-pass for safe files to Codex adversarial review for complex changes.

## Usage

Run one of:

```
/verify           # Run verification (tier auto-detected from edit list)
/verify --deep    # Force Deep tier (thorough review, spec-driven work)
```

Accept only these two invocation forms. Read the edit list from `$STATE_DIR/.session-edits-{sessionId}` automatically.

## Skip Conditions

Classify as Skip when either condition is true:
- zero files were edited this session (`.session-edits-{sessionId}` is absent from `$STATE_DIR/` or is empty)
- the only edits were to verify infrastructure files (`.session-edits-*`, `.verify-passed-*`, this skill file) during a meta-session

## Risk Classifier

Read `$STATE_DIR/.session-edits-{sessionId}` and classify every path using the **Verify Risk** system in `$STRATA_HOME/reference/tier-classification.md`. The **highest risk file** determines the tier for the whole session.

### Tier: Skip

Classify as Skip when all edited files match these patterns (every file matches one listed pattern; one mismatch escalates):

- `$KB_DIR/**/*.md` - knowledge base markdown
- `$KB_DIR/**/*.json` - knowledge base data (daily notes, items.json)
- `$SPECS_DIR/**` - spec files
- `$STRATA_HOME/commands/**/*.md` - skill/command definitions (not hooks or scripts)
- `$STRATA_HOME/skills/**/*.md` - skill definitions (SKILL.md + reference markdown inside skill dirs)
- `.claude/memory/**` - memory files
- `.claude/projects/*/memory/**/*.md` - per-project auto-memory (MEMORY.md and pointer files)
- `**/CLAUDE.md` - project instructions
- `$STRATA_HOME/reference/**/*.md` - reference docs

**Excludes** (these are NOT skip-safe even if they match .claude/):
- `.claude/settings.json` - affects runtime behavior
- `$STRATA_HOME/hooks/**` - executable scripts
- Any `.ps1`, `.sh`, `.js`, `.ts`, `.py`, `.rs` file regardless of location (including inside `$STRATA_HOME/skills/*/scripts/` or `$STRATA_HOME/skills/*/references/`)

**Action:** Output `VERIFY: [N files] SKIP - safe file types only. Auto-passed.` and write the marker file.

### Tier: Light

Classify as Light when all of these are true:
- 1-3 edited files
- All files in the same project directory (common path prefix up to the first project boundary)
- Edited files have zero import/require/reference links to each other (check this by grepping edited files for paths of other edited files)
- All files fall outside the Skip-excludes list above (settings.json, hooks, etc.)

**Action:** Run inline checks. See Light Tier Checks below.

### Tier: Full

Classify as Full when any of these are true:
- 4+ edited files
- Files span multiple project directories
- Edited files have cross-references (imports between them)
- `.claude/settings.json` or `$STRATA_HOME/hooks/*` was edited
- File is in a `src/`, `lib/`, `app/`, or `pages/` directory AND other files in the same directory were also edited

**Action:** Run Codex review + inline checks. See Full Tier Checks below. After completion, log to `$STATE_DIR/agent-log.jsonl`:
`{"timestamp":"[ISO]","command":"/verify","agent_type":"codex-review","model":"codex","purpose":"Full tier review: [N] files across [projects]","duration_estimate":"medium","outcome":"[success|error]","session_id":"[id]"}`

### Tier: Deep

Classify as Deep when the `--deep` flag was passed explicitly.

**Action:** Run Codex review + extended inline checks. See Deep Tier Checks below. After completion, log to `$STATE_DIR/agent-log.jsonl`:
`{"timestamp":"[ISO]","command":"/verify","agent_type":"codex-review","model":"codex","purpose":"Deep tier review: [N] files, spec-driven","duration_estimate":"slow","outcome":"[success|error]","session_id":"[id]"}`

---

<details>
<summary>Light Tier Checks (inline, no subagent)</summary>

Run these checks directly; keep the process inline for 1-3 files in a single project.

**L1. Fresh re-read.** Read every edited file using the Read tool. Read from disk through the tool.

**L2. Debris scan.** Grep all edited files for:
- `TODO` or `FIXME` without a description after it
- `console.log(` or `console.debug(` in non-test files (test files: `*.test.*`, `*.spec.*`, `__tests__/`)
- `debugger` statement
- Placeholder values: `CHANGEME`, `INSERT_HERE`, `your-`, `example.com` in non-example files

**L3. Run tests.** If the project containing the edited files has a test runner:
- `package.json` with `test` script: `npm test` or `npx vitest run`
- `Cargo.toml`: `cargo test`
- `pyproject.toml` with pytest: `pytest`
- If no test runner: note "No tests found" and continue without failure.

**L4. Verdict.** Produce verdict inline:

```
VERIFY: [N files] LIGHT
========================================

[PASS] Re-read N files, debris clean, tests pass
--- or ---
[FAIL] N issues found

  [L2] file.ts:42 - console.log left in production code
  [L3] Tests failed: [output snippet]
```

Write the marker file on PASS. Fix issues and re-run on FAIL.

</details>

<details>
<summary>Full Tier Checks (Codex first, then inline)</summary>

Run Codex as the primary adversarial reviewer, then run mechanical checks inline.

**F0. Codex review (primary reviewer).** Run Codex from the repo root that contains the edited files with a demanding adversarial prompt:

Use the canonical Codex flag set (see CLAUDE.md `Codex Invocation Standard` for flag rationale):

```bash
cd {repo-root} && timeout 600 codex \
  --dangerously-bypass-approvals-and-sandbox \
  -c tools.web_search=true \
  review --uncommitted
```

Keep `--skip-git-repo-check` and `--model` out of the `codex review` call (they are not valid). Use `~/.codex/config.toml` defaults for reasoning effort + service tier. Read CLAUDE.md `Codex Invocation Standard` -> `codex review` for full rationale.

Run once per repo when files span multiple repos. Capture its full output. Use `xhigh` reasoning + `~/.codex/AGENTS.md` priming for deep adversarial analysis covering security, logic, error handling, type safety, and code quality.

- Treat CRITICAL/HIGH findings from Codex as automatic FAIL items.
- Surface WARNING findings as non-blocking.
- Log "Codex: skipped" and fall back to the inline checks below when Codex is unavailable (missing, unauthenticated, or outside a git repo). Warn the user that this is a degraded mode.

**F1. Fresh re-read.** Read every edited file with the Read tool. Read from disk through the tool.

**F2. Cross-file consistency.** For files that reference each other:
- Imports/requires: verify each imported path resolves to a real file and each exported symbol exists.
- Config references: verify each referenced path/module/class exists.
- Mechanical check: grep all edited files for import/require/from statements, verify each target exists using Glob.

**F3. Debris scan.** Grep all edited files for:
- TODO/FIXME without description
- console.log/console.debug in non-test files
- debugger statement
- Placeholder values: CHANGEME, INSERT_HERE, your-, example.com
- `as any` casts in TypeScript (warning only)

**F4. Run tests.** Run the project test runner when one exists. Note missing test-runner config and keep PASS eligibility when one is absent.

**F5. Doc references.** For each edited file, grep *.md files in the same project for the filename. Check README.md and CLAUDE.md at project root.

**F6. Active spec.** Check for in-progress spec matching this session. Surface stale spec as warning.

**F7. Harness check.** Check for recent harness runs when active spec has `Harness: yes`. Nudge only.

**Verdict format:**

```
VERIFY: [N files checked] FULL
========================================

CODEX REVIEW
--------------------------------------
[Codex output verbatim, or "skipped (reason)"]

INLINE CHECKS
--------------------------------------
[PASS] All checks passed
  - F0: Codex [pass/N findings/skipped]
  - F1: Re-read N files
  - F2: Cross-refs valid
  - F3: No debris
  - F4: Tests pass / No tests
  - F5: Docs current
  - F6: Spec current / No spec
  - F7: Harness [status]
--- or ---
[FAIL] N issues found

  [F0] Codex: "description of critical finding"
  [F2] file.ts:42 - Import "./utils" resolves to non-existent file
```

Write the marker file on PASS. Fix issues yourself and re-run /verify on FAIL.

</details>

<details>
<summary>Deep Tier Checks (Codex first, then inline extended)</summary>

Run Full tier checks (Codex + inline), then run these additional inline checks:

**D1. Cross-project consistency.** Check shared facts (ports, versions, domains) agree when edits touched files in 2+ projects.

**D2. Config-affects-runtime.** If settings.json, hook scripts, or config files were edited, trace the config change to its runtime effect.

**D3. Thorough doc currency.** For all .md files in affected project directories, check that descriptions, file paths, and architecture claims match reality.

**D4. Import graph.** Build a dependency graph of all edited files' imports. Verify the import graph remains acyclic.

**D5. Spec conformance.** For spec-driven multi-phase work: when a `$SPECS_DIR/` spec is in play, verify that each Completed phase's `Produces` artifacts actually exist, that the `>> Current Step` pointer matches the real repo state, that no phase marked done has an unmet acceptance criterion, and that Decisions are reflected in the shipped code.

Report using the Full verdict format with `DEEP` label and D1-D5 items in the report.

</details>

---

## Marker File

Use the marker file exactly as the Stop hook expects.

**Path:** `$STATE_DIR/.verify-passed-{sessionId}`
**Content:** ISO timestamp on a single line (e.g., `2026-03-25T14:30:00`)
**Purpose:** Stop hook checks this file. Treat missing or stale marker files as blocked.

Use the Stop hook (`verify-gate.sh`) auto-written marker for Skip-tier sessions; knowledge-base-only work passes without explicit /verify.

---

## Rules

Apply these verification rules after tier classification.

- Classify any code edit, including a single `.ts`, at least as Light and reserve Skip for non-code files.
- Run Light tier checks inline in this session; reserve subagent dispatch for Full and Deep tiers where the cost is justified.
- Scope verify checks to edited files only and leave entity summaries to /end and /reconcile.
- DO NOT write the marker file on FAIL. The Stop hook checks for this. Writing on FAIL defeats the system.
- Treat warnings as non-blocking; for example, `as any` casts and missing tests remain warnings, and PASS remains valid when actual errors are absent.
- Verify only files from the session edit list.
- Stop after 3 failed /verify attempts on the same issue and ask the user.
- For /verify infrastructure edits (`verify-gate.sh` or this skill file), write the marker manually.
- Report only concrete findings and keep PASS for clean code.

<details>
<summary>Integration with Other Skills</summary>

Use these integration points with other skills.

- **/review**: Run /verify first; /review checks that /verify passed before proceeding (marker file exists).
- **/end**: Run /verify before /end. /end records session state that should be verified first.
- **/reconcile**: Keep deep entity verification against ground truth in /reconcile.
- **/spec**: Check that active specs are up to date in Full/Deep tiers.

</details>

<details>
<summary>Session Lifecycle</summary>

Use this session lifecycle:

```
Implement -> /verify (MANDATORY) -> /review -> git commit -> /end -> stop
                ^                                                    |
                |_______ Stop hook blocks if /verify not passed _____|
```

Use Stop hook auto-write for Skip-tier sessions (only .md/.json in $KB_DIR/, .claude/ config); Skip-tier sessions pass without explicit /verify.

</details>

<details>
<summary>Quality Self-Check</summary>

Apply this self-check before reporting the verdict.

1. **Re-read every edited file from disk** before reporting and cite concrete file reads. (Light: you did this. Full/Deep: subagent did this.)
2. **Run tests when they exist** and report results from execution. (All code tiers.)
3. **Mechanically check cross-file references with Glob** for imports before reporting. (Full/Deep only.)
4. **Write findings with specific file path and line number** and name the concrete failure mode.
5. **Reclassify the tier** against the session edit list and classifier rules.

</details>
