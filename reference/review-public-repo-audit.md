<!-- keywords: public repo audit, privacy audit, git history scan, public-repos, secrets in history, review audit mode -->
# /review Public Repo Audit (`--public-repos`)

Goal: Audit the current state and relevant history of every public repository for exposed credentials, private identifiers, informal artifacts, and misleading metadata.

Success means:
  - List every public repository with its description and last push date.
  - Scan current content before selecting repositories for the capped history scan.
  - Match private identifiers as case-insensitive fixed strings from the install-local denylist.
  - Report actionable findings in the review severity format within the 200-line total output budget.

Stop when: Every public repository has a current-state result, each qualifying repository has a capped history result, and the findings identify the affected repository, file or commit, failure mode, and fix.

Use this workflow when making a repository public for the first time and every few months thereafter. The regular review privacy checks catch new leaks; this audit catches older exposure.

**Token budget:** Follow the caps below to keep the audit bounded.

## Quick Nav

| Need | Section |
|------|---------|
| Resolve the public account and private-token inputs | [Step 0](#step-0-resolve-the-handle-and-privacy-denylist) |
| Inventory public repositories | [Step 1](#step-1-list-public-repositories) |
| Scan current content | [Step 2](#step-2-scan-each-repositorys-current-state) |
| Inspect relevant history | [Step 3](#step-3-scan-full-history-where-warranted) |
| Triage and repair findings | [Step 4](#step-4-report-and-fix) |
| Keep the audit bounded | [Deep audit boundaries](#deep-audit-boundaries) |

## Workflow

### Step 0: Resolve the handle and privacy denylist

Resolve the GitHub handle from `--public-repos <handle>` when provided. Otherwise run:

```bash
gh api user --jq '.login'
```

Resolve the install root and load both local denylist lanes in order. Each non-comment, non-blank line is a literal token; `grep -iF -f` provides case-insensitive fixed-string matching. An empty denylist produces a clean private-identifier scan while universal secret scans continue.

```bash
STRATA_HOME="${STRATA_HOME:-$HOME/.strata}"
DENY_TOKENS=""
for tf in "$STRATA_HOME/config/private-tokens.txt" "$STRATA_HOME/.local/private-tokens.txt"; do
    [ -f "$tf" ] || continue
    while IFS= read -r line; do
        line="${line%$'\r'}"
        case "$line" in ''|'#'*) continue ;; esac
        DENY_TOKENS="$DENY_TOKENS$line
"
    done < "$tf"
done
```

### Step 1: List public repositories

```bash
gh repo list <handle> --visibility public --json name,description,pushedAt --limit 50
```

Print the repository name, description, and last push date.

### Step 2: Scan each repository's current state

Scan current state before any full-history scan; this inexpensive pass catches present exposure.

Create a fresh shallow clone in the disposable scratch tree:

```bash
rm -rf /tmp/gh-audit/$repo
gh repo clone <handle>/$repo /tmp/gh-audit/$repo -- --depth=1 --quiet 2>&1
```

Run the current-state checks:

```bash
# Metadata and source files: match the install-local identity, project, and infrastructure inventory.
if [ -n "$DENY_TOKENS" ]; then
  git -C /tmp/gh-audit/$repo grep -iF -f <(printf '%s' "$DENY_TOKENS") \
    HEAD -- LICENSE "*.json" "*.toml" "*.cfg" "*.py" "*.md" 2>/dev/null
fi

# Ignore-file coverage for local configuration.
grep -E "^\.env$|^\.claude|^CLAUDE\.md$" \
  /tmp/gh-audit/$repo/.gitignore 2>/dev/null

# README notes and unfinished placeholders.
grep -iE "hold myself accountable|CHANGEME|INSERT_HERE|your-company\.com|TODO.*clean" \
  /tmp/gh-audit/$repo/README.md 2>/dev/null
```

### Step 3: Scan full history where warranted

Run this step when a repository contains commits from before the current-state check was established or has been public for more than a week. Create a full clone and cap every grep result.

```bash
# Replace the shallow scratch clone with a full clone.
rm -rf /tmp/gh-audit/$repo
gh repo clone <handle>/$repo /tmp/gh-audit/$repo -- --quiet 2>&1

# Universal secret formats (cap at 50 lines).
git -C /tmp/gh-audit/$repo log -p --all 2>/dev/null \
  | grep -iE "(api[_-]?key|secret|password|sk-|AIza|AKIA|ghp_|ghr_|npm_)" \
  | grep -vE "^(--|Binary|@@|Author|Date|commit)" \
  | grep -vE "(test|mock|example|your_|<your|INSERT|fake|dummy|noreply@)" \
  | head -50

# Private identity, project, and infrastructure tokens from both local denylist lanes (cap at 30 lines).
if [ -n "$DENY_TOKENS" ]; then
  git -C /tmp/gh-audit/$repo log -p --all 2>/dev/null \
    | grep -iF -f <(printf '%s' "$DENY_TOKENS") \
    | grep -vE "^(--|commit|Author|Date|@@|Binary)" \
    | head -30
fi

# Process-revealing commit messages (cap at 30 lines).
git -C /tmp/gh-audit/$repo log --format="%H %s" --all 2>/dev/null \
  | grep -iE "(AI slop|anonymize|clean up public|AI-agent|remove Claude|review issues|banned word|genericize|tighten|sanitize|remove leaked|redact|was accidentally|AI patterns|cleanup rationale|internal process)" \
  | head -30

# Verbose commit bodies, more than three lines excluding Co-Authored-By (cap at 20).
git -C /tmp/gh-audit/$repo log --format="COMMIT:%H%n%B---END---" --all 2>/dev/null \
  | awk '/^COMMIT:/{hash=$0; body=""; lines=0; next} /^---END---/{if(lines>3) print hash" ("lines" body lines)"; next} /^Co-Authored-By:/{next} /^$/{next} {lines++}' \
  | head -20
```

**Token budget rule:** Stop the scan and report the collected evidence when grep output across all repositories reaches 200 lines. Name the matched pattern category so the user can run a targeted follow-up.

### Step 4: Report and fix

Report findings with the same severity format as pre-commit review. Offer one consolidated fix pass after the user reviews the report.

**Fix set available after confirmation:**

- Replace private identity metadata with the configured public handle.
- Replace domain-revealing examples with neutral finance or technology examples.
- Remove informal README notes.
- Verify word and line counts with `wc` and correct inaccurate claims.
- Extend `.gitignore` coverage with `.env`, `.claude/`, and `CLAUDE.md` plus a concise comment.

**Commit and push per repository:** Apply the regular public-push gate. Use a short, technical subject that describes the concrete change. When project policy requires attribution, resolve and render the configured public co-author identity through its symbolic lane.

```bash
cd /tmp/gh-audit/$repo
git add -A
git commit -m "Update author metadata"
git push origin main
```

### Deep audit boundaries

Preserve repository history when committed credentials appear. Report the exposure and recommend credential rotation.
Treat the configured public handle in CI badges, repository URLs, and badge links as expected public metadata.
Treat email addresses in commit Author metadata as standard history-bound metadata.
Classify public model names as software metadata according to repository context.
Treat reserved example-domain addresses and obvious fixture values as placeholders.
Read grep output only during the history scan and keep the evidence within the stated caps.
