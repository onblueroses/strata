# Review

Lightweight pre-commit review. Checks staged changes against CLAUDE.md constraints and common issues. Automatically detects public repos and adds privacy checks to the normal flow - no flag needed.

## Usage

```
/review                          # Review staged changes (git diff --cached)
/review --all                    # Review all uncommitted changes
/review --public-repos           # Deep audit of ALL public repos (history + current)
/review --public-repos <handle>  # Same, for a specific GitHub handle
```

Arguments via `$ARGUMENTS`.

---

## Instructions (pre-commit review)

### 0. Check /verify prerequisite

Before running /review, check if `/verify` has passed this session. Look for `.claude/.verify-passed-{sessionId}`. If the file doesn't exist but `.claude/.session-edits-{sessionId}` has entries, tell the agent to run `/verify` first. Note: for Skip-tier sessions (only knowledge-base files edited), the Stop hook auto-writes the marker - no explicit /verify needed. /verify checks code correctness and consistency; /review checks commit readiness. They are complementary.

### 1. Get the diff

```bash
git diff --cached --stat
git diff --cached
```

If `--all` flag, use `git diff HEAD` instead. If nothing is staged, tell the user and stop.

### 2. Detect public repo (automatic - no user action needed)

```bash
gh repo view --json isPrivate --jq '.isPrivate' 2>/dev/null
```

- If output is `false` → this is a **public repo**. Set a mental flag: `PUBLIC_REPO=true`.
- If command fails or returns `true` → private repo, skip all privacy checks below.

This detection is silent. Do not announce it to the user. Just apply the right checks.

### 3. Read constraints

Read `.claude/CLAUDE.md` from the repo root (fall back to `~/.claude/CLAUDE.md`).
Extract constraints, style rules, and the pre-ship review checklist.

### 4. Check against constraints

For each changed file, read the full file (not just the diff) for context. Apply:

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

*Structure:* single-method classes that should be functions; god functions >50 lines; unnecessary wrappers; star imports; dead exports never used in the file.

*Defensive theater:* bare `except:` that swallows silently; empty `catch (e) {}`; try/catch around code that cannot throw; null checks on type-guaranteed-non-null values.

*Noise:* comments that restate the code; hedging comments ("this should work", "hopefully"); `// Helper function to...` wrappers.

*Python lies:* `.push()` / `.size()` / `.length` on Python objects; mutable default args `def f(items=[])`; bare `pass` with no docstring.

*TypeScript drift:* `as any` casts; non-null assertions `!` on uncertain values; `@ts-ignore` added.

**Concrete mechanical tests:**
- **Secret test:** any added line with `sk-`, `ghp_`, `AKIA`, `Bearer `, or 32+ char hex/base64 near a key-like var name?
- **Debug test:** any added line in non-test file with `console.log(`, `console.debug(`, `print(`, or `debugger`?
- **Umlaut test:** any added line with German text containing `ae`, `oe`, `ue` where umlaut belongs?
- **Co-author test:** does commit message include `Co-Authored-By: Claude`?
- **Bare except:** any added `except` without a specific exception type?
- **Any cast:** any added `as any` or `): any`?
- **Mutable default:** any `=[]` or `={}` in a function signature?
- **Empty catch:** any `catch` block with empty body?

### 4a. Privacy checks (PUBLIC_REPO=true only)

**Only run these when `PUBLIC_REPO=true`. They cost nothing extra - just grep the diff you already have.**

Grep the diff for each of the following. Any match is a finding:

**[CRITICAL] Secrets in diff:**
```
sk-  ghp_  ghr_  npm_  AKIA  AIza  Bearer [A-Za-z0-9+/]{20,}
```

**[HIGH] Real name in diff:**
If a real personal name appears in metadata files (LICENSE, package.json, Cargo.toml, pyproject.toml, go.mod): offer to replace with the GitHub handle.

**[HIGH] Private project names in diff:**
Read from CLAUDE.md for the list of private project names that must not appear in public repos.

**[HIGH] Private IPs in diff:**
Read from CLAUDE.md for the list of VPS/internal IP addresses.

**[MEDIUM] Domain-revealing example data in diff:**
Any project-specific domain names or product identifiers appearing in example/test/README files. Offer neutral replacements.

**[LOW] .gitignore gap:**
If the diff modifies `.gitignore` or this is the first commit, check that `.env`, `.claude/`, and `CLAUDE.md` are excluded.

Report these findings alongside the normal review findings. No separate section - they just appear in the same report with clear labels.

### 4b. Run linters

For `.py` files in the diff (if tools available):
```bash
ruff check <file>
mypy <file> --ignore-missing-imports
```

For `.ts/.tsx/.js/.jsx` files:
```bash
eslint <file>        # use local node_modules/.bin/eslint if available
tsc --noEmit         # at project root
```

Report tool findings alongside manual checks.

### 4c. Doc staleness check

For each changed file in the diff, check whether the changes invalidate facts in nearby docs. In the repo, read `CLAUDE.md` at root and any touched subdirs, `README.md`/`README.mdx` at root, and any `docs/*.md` that reference changed modules.

Scan for stale values introduced or contradicted by the staged changes: port numbers, PM2 app names, URLs, file/route/test counts, architecture descriptions, deploy commands, env vars, API paths.

Report stale docs as `[MEDIUM]` findings with the specific stale value and what it should be. If a doc needs a full rewrite, report as `[LOW] Docs TODO: path/to/file`.

### 4d. Commit message gate (PUBLIC_REPO=true only)

When reviewing for a public repo, output this block at the end of the review:

```
COMMIT MESSAGE RULES (public repo):
- Subject only. No body unless strictly necessary (1-2 lines max).
- Never reference internal process: development workflow, AI tooling, cleanup rationale.
- Never mention private project names.
- Write as if a stranger is reading it - because they are.
```

This is a reminder, not a check (the commit message doesn't exist yet). But it ensures the committing agent sees the rules right before writing the message.

### 5. Report

```
REVIEW: [N files changed] [public repo]
========================================

[PASS] No issues found
--- or ---
[WARN] N issues found

  [CRITICAL] file.ts:42 - Hardcoded API key (sk-...)
  [HIGH]     LICENSE:1 - Real name in metadata - replace with GitHub handle
  [MEDIUM]   examples/demo.py:30 - Domain-specific term in example data
  [MEDIUM]   utils.ts:89 - console.log left in production code

Recommendation: [ready to commit / fix N issues first]
```

Only show `[public repo]` in the header when `PUBLIC_REPO=true`. If all checks pass, say so and stop. Don't pad the report.

**Good vs bad findings:**

| Bad | Good |
|-----|------|
| "Consider adding more error handling" | `[HIGH] api.ts:34 - SQL built with string concatenation` |
| "console.log in test file" | `[MEDIUM] utils.ts:89 - console.log('debug') in production code` |
| "This function could be more readable" | `[HIGH] page.tsx:12 - "Steuererklärung" misspelled` |
| "Missing type annotations" | `[CRITICAL] config.ts:5 - API key hardcoded: sk-proj-abc...` |

### 6. Offer fixes

- Auto-fix: style issues, debug statements, real name replacements, .gitignore gaps
- Flag but don't auto-fix: CRITICAL security issues (user should review first)

### Quality self-check

Before reporting, verify:
1. Read every changed file (not just the diff)?
2. Checked the project CLAUDE.md (not just global)?
3. Checked for security issues even in "boring" changes?
4. All findings backed by a specific constraint or concrete test?
5. Correct severity? CRITICAL = security/data loss only.

### DO NOT

- **DO NOT invent issues.** Clean diff → PASS. Normal, not suspicious.
- **DO NOT flag test files for `console.log`.** Expected there.
- **DO NOT report style issues not in CLAUDE.md.** "More readable" is an opinion.
- **DO NOT suggest refactoring unrelated code.** Review only the diff.
- **DO NOT use CRITICAL for non-security issues.** Missing umlaut = HIGH. CRITICAL = secrets/injection/data loss.
- **DO NOT block a commit for LOW issues.** Mention them; still recommend ready to commit.
- **DO NOT announce "this is a public repo" to the user** before showing results. Just detect silently and apply the right checks.

---

## Public Repo Audit (`--public-repos`)

**Purpose:** Periodic deep audit - scans full git history across all public repos. Run this when making a repo public for the first time, or every few months as a sanity check. The pre-commit privacy checks (Step 4a above) catch new leaks on every commit; this catches anything that was already there.

**Token budget:** This mode can get expensive. Follow the caps below precisely - they keep it manageable.

### Step 0 - Resolve handle

If `--public-repos <handle>` was given, use that. Otherwise:
```bash
gh api user --jq '.login'
```

### Step 1 - List public repos

```bash
gh repo list <handle> --visibility public --json name,description,pushedAt --limit 50
```

Print the list. Show name + description + last push date.

### Step 2 - For each repo: current-state scan (fast)

Do this for every repo **before** doing any full-history scan. Current-state is cheap.

```bash
# Metadata files: real name, private project refs
git -C /tmp/gh-audit/$repo grep -iE \
  "[private-names-from-CLAUDE.md]" \
  HEAD -- LICENSE "*.json" "*.toml" "*.cfg" "*.py" "*.md" 2>/dev/null

# .gitignore gaps
cat /tmp/gh-audit/$repo/.gitignore 2>/dev/null | grep -E "^\.env$|^\.claude|^CLAUDE\.md$"

# README informal notes and placeholder text
grep -iE "CHANGEME|INSERT_HERE|your-company\.com|TODO.*clean" \
  /tmp/gh-audit/$repo/README.md 2>/dev/null
```

Clone with `--depth=1` for current-state check (shallow clone, fast):
```bash
gh repo clone <handle>/$repo /tmp/gh-audit/$repo -- --depth=1 --quiet 2>&1
```

### Step 3 - Full history scan (capped)

Only do this if the repo had commits from before the current-state check looked clean **or** if the repo has been live for more than a week. Use a full clone (not shallow) but **cap all grep output**.

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
  | grep -iE "[private-names-from-CLAUDE.md]" \
  | grep -vE "^(--|commit|Author|Date|@@|Binary)" \
  | head -30

# Private IPs in history - cap at 20 lines
git -C /tmp/gh-audit/$repo log -p --all 2>/dev/null \
  | grep -E "[private-ips-from-CLAUDE.md]" \
  | grep -vE "^(--|commit|Author|Date|@@)" \
  | head -20

# Process-revealing commit messages - cap at 30 lines
git -C /tmp/gh-audit/$repo log --format="%H %s" --all 2>/dev/null \
  | grep -iE "(AI slop|anonymize|clean up public|AI-agent|remove Claude|review issues)" \
  | head -30

# Verbose commit bodies (>3 lines excluding Co-Authored-By) - cap at 20
git -C /tmp/gh-audit/$repo log --format="COMMIT:%H%n%B---END---" --all 2>/dev/null \
  | awk '/^COMMIT:/{hash=$0; body=""; lines=0; next} /^---END---/{if(lines>3) print hash" ("lines" body lines)"; next} /^Co-Authored-By:/{next} /^$/{next} {lines++}' \
  | head -20
```

**Token budget rule:** If grep output across all repos exceeds 200 lines total, stop and report what you have. Don't try to be exhaustive - flag the pattern, let the user dig deeper manually if needed.

### Step 4 - Report and fix

Same severity format as pre-commit review. After reporting, offer to fix everything in one pass:

**Auto-fixes (apply immediately if user confirms):**
- Real name → GitHub handle in LICENSE, `package.json` author, `pyproject.toml`, `Cargo.toml`
- Domain-revealing example items → neutral equivalents
- Informal README notes → removed
- Incorrect word/line count claims → corrected (verify with `wc -w`)
- .gitignore gaps → append `.env`, `.claude/`, `CLAUDE.md` with a comment

**Commit and push per repo:**
```bash
cd /tmp/gh-audit/$repo
git add -A
git commit -m "Privacy and quality cleanup

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
git push origin main
```

### DO NOT (deep audit mode)

- **DO NOT rewrite git history** to remove committed secrets. Mention it; recommend rotating the credential instead.
- **DO NOT flag the GitHub handle** in CI badges, repo URLs, or shield.io badges - expected.
- **DO NOT flag emails in git commit Author metadata** - standard, not fixable without history rewrite.
- **DO NOT flag public model names** (e.g. `deepseek/deepseek-r1`, `google/gemma-3-12b`) as secrets.
- **DO NOT flag `test@example.com`** or other obvious placeholder emails in test fixtures.
- **DO NOT read full file contents** of source files during the history scan - grep output only. Keep tokens low.
