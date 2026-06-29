---
name: review
description: "Pre-commit code review — checks staged changes against project constraints. Automatically adds privacy checks when the current repo is public (per the public-repo commit-message discipline in CLAUDE.md). Invokes Codex first as the primary adversarial reviewer (`codex review --uncommitted`), then runs mechanical checks (privacy sweep, secrets scan, debris check). MANDATORY before any git commit — runs first, then commit. Triggers on: 'review my changes', 'review what we did', 'critically review all the changes', 'critique your changes', 'pre-commit review', 'check before commit', 'review before pushing', 'self-critique', 'audit my work', 'go over the changes', 'sanity check this diff', 'final review', 'ready to commit', 'review what you did'. Also triggers when: the user says 'commit this' or 'let's commit' (review runs first, then commit); the user says 'critically review all the changes you've made' or similar self-critique requests (runs in self-critique mode, see the Self-Critique Mode section in the body); git diff shows staged or unstaged code changes that haven't been reviewed this session. Pairs with /verify (upstream — verify runs before review, marker file required), /codex-review (different scope — codex-review handles non-diff artifacts like plans; /review handles diffs), /commit (downstream — review must pass first), /ship (downstream for frontend — ship runs after review on frontend changes), /security-review (downstream — for explicit security audit). Self-critique mode applies when the user invokes review on Claude's own work in the same session."
tier: core
predecessors: [verify]
conflicts_with: [commit]
cost_hint: medium
parallelizable: false
when_to_use: Before committing code changes
---

# Review

Goal: Run `/review` as the pre-commit or requested review workflow and return a concrete commit-readiness, self-critique, or public-repo audit report.

Success means:
  - MANDATORY before any git commit: run `/review` first, then commit.
  - `/review` checks the relevant diff, invokes Codex first, applies project constraints, and reports actionable findings by severity.
  - PUBLIC_REPO=true -> APPLY PRIVACY CHECKS.
  - Pre-commit review blocks commit readiness on CRITICAL/HIGH findings and treats LOW findings as advisory.
  - Self-Critique Mode activates on the listed trigger phrases and evaluates whether Claude's own changes match the stated task.
  - Public Repo Audit scans public repositories with the capped current-state and history workflow.

Stop when: The report names every finding with file, line, failure mode, and fix direction, or returns PASS with the applicable gates recorded.
Run a lightweight pre-commit review against staged changes, CLAUDE.md constraints, and common issue patterns. Detect public repositories automatically and apply privacy checks in the normal flow.

## Usage

Run the command variant that matches the review scope.
```
/review                          # Review staged changes (git diff --cached)
/review --all                    # Review all uncommitted changes
/review --public-repos           # Deep audit of ALL public repos (history + current)
/review --public-repos <handle>  # Same, for a specific GitHub handle
```

Arguments via `$ARGUMENTS`.

---

## Instructions (pre-commit review)

Follow the pre-commit sequence from prerequisite check through final recommendation.
### 0. Check /verify prerequisite

Check whether `/verify` has passed this session before running `/review`. Look for `$STATE_DIR/.verify-passed-{sessionId}`. When that marker is absent and `$STATE_DIR/.session-edits-{sessionId}` has entries, tell Claude to run `/verify` first. For Skip-tier sessions (only knowledge-base files edited), the Stop hook auto-writes the marker and completes the prerequisite. /verify checks code correctness and consistency; /review checks commit readiness. They are complementary.

### 1. Get the diff

Inspect the staged diff first, then expand to all uncommitted changes when requested.
```bash
git diff --cached --stat
git diff --cached
```

Use `git diff HEAD` when the `--all` flag is present. When the staged diff is empty, tell the user and stop.

### 1a. Codex review (first pass)

Run OpenAI Codex as the first adversarial reviewer before manual checks. Use the canonical Codex flag set (see CLAUDE.md `Codex Invocation Standard` for flag rationale): `xhigh` reasoning + `fast` service tier + web search + `~/.codex/AGENTS.md` priming for maximum finding depth.

```bash
# From the repo root containing the staged changes:
timeout 600 codex \
  --dangerously-bypass-approvals-and-sandbox \
  -c tools.web_search=true \
  review --uncommitted

# Or for branch diff:
codex \
  --dangerously-bypass-approvals-and-sandbox \
  -c tools.web_search=true \
  review --base main
```

- Codex runs in read-only sandbox with `xhigh` reasoning for deep analysis.
- `~/.codex/AGENTS.md` primes every session with adversarial behavior, severity format ([P0]-[P3]), and the full checklist (security, logic, error handling, type safety, code quality, performance).
- Capture its output and include any findings in the final report under a `CODEX REVIEW` section.
- When Codex authentication or execution fails, log a warning and continue with the manual review; Codex availability is advisory for this pass.
- Treat Codex findings as already-covered items in manual checks. When Codex already flagged something, skip that item in steps 4+.

### 1b. Categorize files (fan-out preparation)

Categorize each file in the diff into one of 6 buckets using path patterns. Apply the first matching bucket; order matters.

| Priority | Bucket | Path patterns |
|----------|--------|--------------|
| 1 | test | `*.test.*`, `*.spec.*`, `__tests__/**`, `test/**`, `tests/**`, `*_test.go`, `*_test.rs` |
| 2 | deps | `package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `Cargo.toml`, `Cargo.lock`, `go.mod`, `go.sum`, `requirements.txt`, `pyproject.toml`, `composer.json`, `Gemfile*` |
| 3 | config | `.env*`, `*.config.*`, `tsconfig*`, `.eslintrc*`, `.prettierrc*`, `Dockerfile*`, `docker-compose*`, `.github/**`, `.gitignore`, `*.yaml` (not in `docs/`), `*.yml` (not in `docs/`) |
| 4 | docs | `*.md`, `*.mdx`, `docs/**`, `LICENSE*`, `CHANGELOG*`, `*.txt` (root only) |
| 5 | api | `**/api/**`, `**/routes/**`, `**/endpoints/**`, `**/handler*.*`, `**/middleware/**`, `**/controllers/**` |
| 6 | code | Everything else |

Store the categorization as a map: `{bucket: [filepath, ...]}`. Count total files and total lines changed (from `git diff --stat`).

**Threshold gate (zero LLM cost):**
- If total files < 10 AND total lines changed < 500: **single reviewer** - proceed with Steps 2-6 as normal.
- If total files >= 10 OR total lines changed >= 500: **fan-out mode** - proceed with Steps 2-4d as normal, AND also run Fan-Out Review (Step 4e) in parallel. Merge all findings.

Record the routing decision silently. The report header will show `[FAN-OUT]` when fan-out activates.

### 2. Detect public repo (automatic - zero user action)

Detect repository visibility with GitHub CLI before applying privacy gates.

```bash
gh repo view --json isPrivate --jq '.isPrivate' 2>/dev/null
```

- If output is `false` → this is a **public repo**. Set a mental flag: `PUBLIC_REPO=true`.
- If command fails or returns `true` → treat as a private repo and leave the privacy checks below inactive.

Keep this detection silent. Apply the right checks based on the result.

### 3. Read constraints

Read `.claude/CLAUDE.md` from the repo root (fall back to `$HOME/.claude/CLAUDE.md`).
Extract constraints, style rules, and the pre-ship review checklist.

### 4. Check against constraints

Read the full file for each changed file, using the diff plus surrounding context. Apply:

**Security:**
- No API keys, tokens, passwords, or secrets in code
- No `.env` contents committed
- No `eval()` or `innerHTML` with user input
- No SQL string concatenation

**Style:**
- No emojis (unless the file already had them)
- Hyphens, not em dashes
- No AI vocabulary (delve, crucial, landscape, tapestry, leverage, robust)
- German text has proper umlauts. **Test:** grep diff for `ue|ae|oe` inside German words

**Code Quality:**
- No `console.log` / `print()` debug statements in non-test files
- No commented-out code blocks (>3 lines)
- No TODO/FIXME without context
- No obvious copy-paste errors

**AI Code Slop** - check changed lines for:

*Structure:* single-method classes that should be functions; god functions >50 lines; unnecessary wrappers; star imports; unused dead exports in the file.

*Defensive theater:* bare `except:` that swallows silently; empty `catch (e) {}`; try/catch around guaranteed-safe code; null checks on type-guaranteed-non-null values.

*Noise:* comments that restate the code; hedging comments ("this should work", "hopefully"); `// Helper function to...` wrappers.

*Python lies:* `.push()` / `.size()` / `.length` on Python objects; mutable default args `def f(items=[])`; bare `pass` with missing docstring.

*TypeScript drift:* `as any` casts; non-null assertions `!` on uncertain values; `@ts-ignore` added.

**Concrete mechanical tests:**
- **Secret test:** any added line with `sk-`, `ghp_`, `AKIA`, `Bearer `, or 32+ char hex/base64 near a key-like var name?
- **Debug test:** any added line in non-test file with `console.log(`, `console.debug(`, `print(`, or `debugger`?
- **Umlaut test:** any added line with German text containing `ae`, `oe`, `ue` where umlaut belongs?
- **Co-author test:** does commit message include `Co-Authored-By: Claude`?
- **Bare except:** any added generic `except` with missing specific exception type?
- **Any cast:** any added `as any` or `): any`?
- **Mutable default:** any `=[]` or `={}` in a function signature?
- **Empty catch:** any `catch` block with empty body?

### 4a. Privacy checks (PUBLIC_REPO=true only)

Apply privacy checks exactly when `PUBLIC_REPO=true`.

**PUBLIC_REPO=true -> APPLY PRIVACY CHECKS.** Grep the diff you already have; these checks cost nothing extra.

Grep the diff for each of the following. Any match is a finding:

**[CRITICAL] Secrets in diff:**
```
sk-  ghp_  ghr_  npm_  AKIA  AIza  Bearer [A-Za-z0-9+/]{20,}
```

**[HIGH] Real name in diff:**
The user's privacy denylist lives in their CLAUDE.md (typically under a `## Constraints` -> `Privacy` section) and/or in a project-local `.private-tokens.txt`. Read it before this gate. If a real name appears in a metadata file (LICENSE, package.json, Cargo.toml, pyproject.toml, go.mod), offer to replace with the user's public handle.

**[HIGH] Private project names in diff:**
Pull the project-codename list from the user's CLAUDE.md privacy section. Flag any match in the diff as `[HIGH]`.

**[HIGH] Private IPs in diff:**
Pull the IP list (VPS, Tailscale, internal hosts) from the user's CLAUDE.md privacy section. Flag matches.

**[MEDIUM] Domain-revealing example data in diff:**
If the CLAUDE.md privacy section enumerates domain-specific vocabulary (industry jargon, client-specific terminology) that leaks the user's market or clients, flag matches in example/test/README files and propose neutral replacements.

**[LOW] .gitignore gap:**
If the diff modifies `.gitignore` or this is the first commit, check that `.env`, `.claude/`, and `CLAUDE.md` are excluded.

Report these findings alongside the normal review findings. Fold them into the same report with clear labels.

### 4b. Run linters

Run language-specific linters and type checks for changed files when tools are available.
For `.py` files in the diff (if tools available):
```bash
ruff check <file>
ruff format --check <file>
pyright <file>
mypy <file> --ignore-missing-imports   # fallback or second opinion when useful
```

For `.ts/.tsx/.js/.jsx/.mjs/.cjs` files:
```bash
biome check <file>   # preferred when available
eslint <file>        # fallback if biome is unavailable; prefer local node_modules/.bin/eslint
tsgo --noEmit        # at project root when tsconfig.json exists
```

For `.rs` files:
```bash
cargo clippy --quiet -- -D warnings    # at crate root
rustfmt --check <file>
```

Report tool findings alongside manual checks.

### 4c. Doc staleness check

For each changed file in the diff, check whether the changes invalidate facts in nearby docs. In the repo, read `CLAUDE.md` at root and any touched subdirs, `README.md`/`README.mdx` at root, and any `docs/*.md` that reference changed modules.

Scan for stale values introduced or contradicted by the staged changes: port numbers, PM2 app names, URLs, file/route/test counts (e.g. "72 city pages"), architecture descriptions, deploy commands, env vars, API paths.

Report stale docs as `[MEDIUM]` findings with the specific stale value and what it should be. If a doc needs a full rewrite, report as `[LOW] Docs TODO: path/to/file`.

### 4d. Commit message gate (PUBLIC_REPO=true only)

Gate public-repo commit messages for external-facing privacy and process signals.
**Banned patterns in commit messages:** Flag these terms because they reveal internal process or cleanup rationale to public readers:

```
AI slop|anonymize|clean up public|remove AI|banned word|review issues|genericize|
tighten|sanitize|remove leaked|redact|was accidentally|AI-agent|AI patterns|
remove Claude|cleanup rationale|internal process
```

Also flag banned private project names (from the CLAUDE.md privacy section), private IPs, and verbose bodies (>2 lines excluding Co-Authored-By).

**Pre-commit (no message exists yet):** Output the banned list as a `[GATE]` block at the end of the review so the committing agent has it in context:

```
[GATE] PUBLIC REPO COMMIT MESSAGE - banned patterns:
  AI slop, anonymize, clean up public, remove AI, banned word, review issues,
  genericize, tighten, sanitize, remove leaked, redact, was accidentally,
  AI-agent, AI patterns, remove Claude, cleanup rationale, internal process,
  private project codenames (per CLAUDE.md privacy section)
  Subject-only. No body unless strictly necessary (1-2 lines max).
  Write as if a stranger is reading it.
```

**Post-commit (reviewing existing commits, e.g. `--all` or self-critique):** If recent unpushed commits exist, grep their messages against the banned patterns. Report matches as `[HIGH]` findings with a suggested rewrite. This catches messages written by raw `git commit` outside of `/commit`.

### 4e. Fan-out review (threshold exceeded only)

Run fan-out review when the threshold gate selects specialist review.
<details>
<summary>Fan-out review (threshold exceeded only)</summary>

Run only when Step 1b's threshold gate triggered fan-out (>= 10 files OR >= 500 lines changed). For smaller diffs, use the single-reviewer path entirely.

**Specialist reviewers:** Spawn subagents in parallel (Agent-tool review panel), one per non-empty bucket from Step 1b's categorization. Each specialist gets only the files in its bucket.

| Bucket | Specialist perspective | Focus |
|--------|----------------------|-------|
| code | Logic reviewer | Correctness, edge cases, type safety, dead code |
| api | API contract reviewer | Breaking changes, auth gaps, input validation, error responses |
| docs | Documentation reviewer | Accuracy vs code, stale references, broken links |
| config | Config reviewer | Security (secrets in config), environment consistency, missing defaults |
| deps | Dependency reviewer | Version conflicts, license issues, unused deps, lockfile consistency |
| test | Test reviewer | Coverage gaps, flaky patterns, assertion quality, missing edge cases |

**Specialist prompt template:**
```
Goal: Review {N} files in the "{bucket}" category of a {total_files}-file diff from the {focus} perspective.

Success means:
  - Read the project constraints and every provided file.
  - Report each concrete finding that affects this bucket, with file, line, failure mode, and fix direction in the description.
  - Use severity values from this set: CRITICAL, HIGH, MEDIUM, LOW.
  - Return one finding per line in the required format.
  - Return an empty response when the review finds zero issues.

Stop when: Every provided file has been reviewed and the response contains every real finding in the required format.

CONSTRAINTS (from project CLAUDE.md):
{constraints}

FILES TO REVIEW:
{file_list_with_full_content}

PUBLIC_REPO: {true|false}

Required format:
[SEVERITY] file:line - description

Severity mapping:
CRITICAL = security/data loss
HIGH = correctness/breaking
MEDIUM = quality
LOW = style/minor

Trace the impact of each issue through the changed code before reporting it.
```

**Dedup and merge:** After all specialists return, deduplicate findings using the key `${file}:${line}:${description_normalized}`. When two findings share the same file:line and describe the same issue (fuzzy match on description), keep the one with higher severity. Merge all findings into a single list sorted by severity (CRITICAL first), then by file path.

**Quality gate for specialists:** If a specialist returns more than 20 findings, it's likely being too noisy. Truncate to the 10 highest-severity findings and note "[N additional LOW/MEDIUM findings omitted]".

Steps 4, 4a-4d still run in fan-out mode but their findings merge with specialist output. The Codex pass (Step 1a) always runs regardless of fan-out - it sees the whole diff.

</details>

### 5. Report

Return the review in the fixed report shape.
```
REVIEW: [N files changed] [public repo] [FAN-OUT: N specialists]
========================================

CODEX REVIEW (OpenAI Codex - first pass)
-----------------------------------------
[Codex findings here, verbatim or summarized]
[If Codex unavailable: "Codex: skipped (not authenticated / error)"]

SPECIALIST REVIEW (fan-out only)
-----------------------------------------
[Only shown when fan-out activated]
  code (N files): [N findings]
  api (N files): [N findings]
  docs (N files): [N findings]
  ...

MANUAL REVIEW (Claude - second pass)
--------------------------------------
[PASS] No issues found
--- or ---
[WARN] N issues found

  [CRITICAL] file.ts:42 - Hardcoded API key (sk-...)
  [HIGH]     LICENSE:1 - Real name "<owner real name>" - replace with public handle
  [MEDIUM]   examples/demo.py:30 - domain-specific jargon reveals private market
  [MEDIUM]   utils.ts:89 - console.log left in production code

Recommendation: [ready to commit / fix N issues first]
```

Show `[public repo]` in the header when `PUBLIC_REPO=true`. Show `[FAN-OUT: N specialists]` when fan-out activated. When all checks pass, say so and stop. Keep the report tight.

**Good vs bad findings:**

| Bad | Good |
|-----|------|
| "Consider adding more error handling" | `[HIGH] api.ts:34 - SQL built with string concatenation` |
| "console.log in test file" | `[MEDIUM] utils.ts:89 - console.log('debug') in production code` |
| "This function could be more readable" | `[HIGH] page.tsx:12 - umlaut missing in user-facing string` |
| "Missing type annotations" | `[CRITICAL] config.ts:5 - API key hardcoded: sk-proj-abc...` |

### 6. Offer fixes

Offer fixes after the report, separating safe autofixes from user-reviewed security work.
- Auto-fix: style issues, debug statements, real name replacements, .gitignore gaps
- Flag and leave for user review first: CRITICAL security issues

### Quality self-check

Verify these checks before reporting:
1. Read every changed file with full-file context plus the diff?
2. Checked the project CLAUDE.md plus the global fallback?
3. Checked security issues across every changed area, including boring changes?
4. All findings backed by a specific constraint or concrete test?
5. Correct severity? CRITICAL = security/data loss only.
6. Fan-out: threshold gate applied correctly (>= 10 files OR >= 500 lines)?
7. Fan-out: specialist findings deduplicated by file:line:description?
8. Fan-out: noisy specialists truncated to 10 highest-severity findings?

**Optional final step (non-blocking).** Before signing off, name what this change leaves comfortably unaddressed: the risk the diff satisfies on paper but not in reality. Name the error path it never added, the assumption it left unstated, the test the green checkmark made feel unnecessary. A clean review confirms the present code is sound; this asks what a sound-looking change quietly leaves out. Skip it for trivial, low-stakes, or purely mechanical diffs (renames, formatting, dependency bumps) where there is no design surface to hide an absence. It adds an author-facing note only and never changes the PASS/FAIL verdict.

### Review Boundaries

Report real issues only. Clean diff → PASS. Normal, not suspicious.
Treat `console.log` in test files as expected.
Anchor style findings to CLAUDE.md. "More readable" is an opinion.
Keep review scope to the diff.
Reserve CRITICAL for secrets, injection, and data loss. Missing umlaut = HIGH.
Mention LOW issues and still recommend ready to commit when only LOW issues remain.
Keep public-repo detection silent before results. Detect silently and apply the right checks.

---

## Self-Critique Mode

Activate when user says "critically review all the changes you've made", "review what you did", "critique your changes", or similar. Run this as a design/correctness critique focused separately from commit readiness.

**Read the source of truth for session edits:** Read `$STATE_DIR/.session-edits-{sessionId}`. When the file is absent, fall back to git diff HEAD.

**Run the steps inline:** Use this session for the critique; subagents are unnecessary.

**S0. Codex adversarial review.** Run Codex first as a demanding external critic, using the canonical flag set (see CLAUDE.md `Codex Invocation Standard`):
```bash
timeout 600 codex \
  --dangerously-bypass-approvals-and-sandbox \
  -c tools.web_search=true \
  review --uncommitted
```
Capture Codex output. Use its findings as input to the manual self-critique steps below; Codex flags things Claude systematically misses (logic holes, edge cases, unnecessary complexity). When Codex is unavailable, log "Codex: skipped" and continue.

**S1. Re-read every edited file from disk.** Use the Read tool and ground the critique in disk state.

**S2. Check against the stated task.** Reconstruct the task from context (user's original request, active spec at `$SPECS_DIR/`, or recent conversation). For each edited file, ask:
- Does this change actually do what was asked?
- Which requirements from the stated task remain unaddressed by this file?
- Which implementation approaches diverge from the request and require flagging?

**S3. Check for design issues introduced.** For each edit:
- Which existing codebase patterns does it conflict with?
- Which invariants stated in CLAUDE.md, specs, or comments does it break?
- Which inconsistencies with referenced files does it introduce?
- Mechanical: grep edited files for cross-references, verify those still hold.

**S4. Check for things that were missed.** Read the original task description again. List every requirement. Verify each one is addressed. Name any open requirement.

**S5. Assess the quality of the changes themselves.** Focus on logic over style:
- Which task-implied edge cases remain unhandled?
- Which correct implementation paths are fragile under reasonable adjacent changes?
- Which implementation paths exceed the requested scope and could cause side effects?

**Report format:**

```
SELF-CRITIQUE: [N files reviewed]
========================================

[PASS] Implementation matches stated task
  - S2: All requirements addressed
  - S3: No design conflicts
  - S4: No missed requirements
  - S5: No fragile logic
--- or ---
[ISSUES] N problems found

  [MISSED] Requirement X from task not implemented in any edited file
  [CONFLICT] file.md line 42 contradicts invariant in other-file.md line 17
  [SCOPE] file.ts adds feature Y which was not part of the stated task
  [FRAGILE] pattern at file.ts:30 will break if sibling file changes Z
  [WRONG] file.md describes X but task asked for Y
```

Offer to fix any identified issues after the report.

Run only the design/correctness critique in this mode. Keep normal pre-commit checks (secrets, linters, style) for the separate commit-readiness review. Focus purely on "did this do the right thing correctly."

---

## Public Repo Audit (`--public-repos`)

Run the capped public-repository audit workflow for current-state and history exposure checks.
Run a periodic deep audit that scans full git history across all public repos. Use this when making a repo public for the first time, or every few months as a sanity check. The pre-commit privacy checks (Step 4a above) catch new leaks on every commit; this catches anything that was already there.

**Token budget:** This mode can get expensive. Follow the caps below precisely; they keep it manageable.

### Step 0 - Resolve handle

Resolve the GitHub handle from `--public-repos <handle>` when provided. Otherwise:
```bash
gh api user --jq '.login'
```

### Step 1 - List public repos

List the target account public repositories before scanning them.
```bash
gh repo list <handle> --visibility public --json name,description,pushedAt --limit 50
```

Print the list. Show name + description + last push date.

### Step 2 - For each repo: current-state scan (fast)

Scan current state first because it is cheap and catches present exposure.
Scan every repo current state **before** any full-history scan. Current-state is cheap.

```bash
# Metadata files: real name, private project refs.
# DENYLIST_RE is built from the user's CLAUDE.md privacy section + project-local
# .private-tokens.txt; load it before running. Example shape: "Owner Name|CodeA|CodeB".
git -C /tmp/gh-audit/$repo grep -iE \
  "$DENYLIST_RE" \
  HEAD -- LICENSE "*.json" "*.toml" "*.cfg" "*.py" "*.md" 2>/dev/null

# .gitignore gaps
cat /tmp/gh-audit/$repo/.gitignore 2>/dev/null | grep -E "^\.env$|^\.claude|^CLAUDE\.md$"

# README informal notes and placeholder text
grep -iE "hold myself accountable|CHANGEME|INSERT_HERE|your-company\.com|TODO.*clean" \
  /tmp/gh-audit/$repo/README.md 2>/dev/null
```

Clone with `--depth=1` for current-state check (shallow clone, fast):
```bash
gh repo clone <handle>/$repo /tmp/gh-audit/$repo -- --depth=1 --quiet 2>&1
```

### Step 3 - Full history scan (capped)

Run this when the repo had commits from before the current-state check looked clean **or** when the repo has been live for more than a week. Use a full clone and **cap all grep output**.

```bash
# Re-clone without depth limit (only for repos that need history scan)
gh repo clone <handle>/$repo /tmp/gh-audit/$repo -- --quiet 2>&1

# Secret patterns - cap at 50 lines
git -C /tmp/gh-audit/$repo log -p --all 2>/dev/null \
  | grep -iE "(api[_-]?key|secret|password|sk-|AIza|AKIA|ghp_|ghr_|npm_)" \
  | grep -vE "^(--|Binary|@@|Author|Date|commit)" \
  | grep -vE "(test|mock|example|your_|<your|INSERT|fake|dummy|noreply@)" \
  | head -50

# Private names in history - cap at 30 lines
git -C /tmp/gh-audit/$repo log -p --all 2>/dev/null \
  | grep -iE "$DENYLIST_RE" \
  | grep -vE "^(--|commit|Author|Date|@@|Binary)" \
  | head -30

# Private IPs in history - cap at 20 lines
git -C /tmp/gh-audit/$repo log -p --all 2>/dev/null \
  | grep -E "$DENYLIST_IP_RE" \
  | grep -vE "^(--|commit|Author|Date|@@)" \
  | head -20

# Process-revealing commit messages - cap at 30 lines
git -C /tmp/gh-audit/$repo log --format="%H %s" --all 2>/dev/null \
  | grep -iE "(AI slop|anonymize|clean up public|AI-agent|remove Claude|review issues|banned word|genericize|tighten|sanitize|remove leaked|redact|was accidentally|AI patterns|cleanup rationale|internal process)" \
  | head -30

# Verbose commit bodies (>3 lines excluding Co-Authored-By) - cap at 20
git -C /tmp/gh-audit/$repo log --format="COMMIT:%H%n%B---END---" --all 2>/dev/null \
  | awk '/^COMMIT:/{hash=$0; body=""; lines=0; next} /^---END---/{if(lines>3) print hash" ("lines" body lines)"; next} /^Co-Authored-By:/{next} /^$/{next} {lines++}' \
  | head -20
```

**Token budget rule:** If grep output across all repos exceeds 200 lines total, stop and report what you have. Flag the pattern and let the user dig deeper manually if needed.

### Step 4 - Report and fix

Report with the same severity format as pre-commit review. After reporting, offer to fix everything in one pass:

**Auto-fixes (apply immediately if user confirms):**
- Real name → GitHub handle in LICENSE, `package.json` author, `pyproject.toml`, `Cargo.toml`
- Domain-revealing example items → neutral finance/tech equivalents
- Informal README notes → removed
- Incorrect word/line count claims → corrected (verify with `wc -w`)
- .gitignore gaps → append `.env`, `.claude/`, `CLAUDE.md` with a comment

**Commit and push per repo:**
```bash
cd /tmp/gh-audit/$repo
git add -A
git commit -m "Privacy and quality cleanup

Co-Authored-By: Claude <noreply@anthropic.com>"
git push origin main
```

### Deep Audit Boundaries

Preserve git history when committed secrets appear. Mention the exposure and recommend rotating the credential instead.
Treat the GitHub handle in CI badges, repo URLs, or shield.io badges as expected.
Treat emails in git commit Author metadata as standard and history-bound.
Treat public model names (`org/model-name` identifiers in configs and code) as model names, not secrets.
Treat `test@example.com` and other obvious placeholder emails in test fixtures as placeholders.
Read grep output only during the history scan. Keep tokens low.
