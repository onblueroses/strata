#!/usr/bin/env bash
# gate-pre-push.sh - PreToolUse(Bash) gate on `git push`.
#
# Push-time work has usually already iterated through review. This gate performs two
# focused checks and surfaces either result as a DECISION rather than a hard wall:
#
#   1. PRIVACY SCAN. Scan the outgoing diff for secrets in every repo and, on PUBLIC
#      repos, for private identifiers from the install-local denylist.
#
#   2. REVIEW CHECK. Confirm that the outgoing work carries a fresh `.verify-passed`
#      marker from this session with no later edits.
#
# A clean, reviewed diff proceeds immediately. Otherwise the push stops once per HEAD
# (exit 2) and prints the findings; repeating the SAME push records the decision to
# proceed. Redacting a real hit creates a new commit and triggers a new scan. Running
# /verify writes the marker and clears the review check.
#
# Input: stdin JSON with .tool_input.command and .session_id.
# Allow: exit 0. Surface/stop: exit 2 + stderr (fed back to the calling agent).
set -uo pipefail

STRATA_HOME="${STRATA_HOME:-$HOME/.strata}"
KB_DIR="${KB_DIR:-$STRATA_HOME/workspace}"
STATE_DIR="${STATE_DIR:-$KB_DIR/state}"

INPUT="$(cat)"
COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"
SESSION_ID="$(printf '%s' "$INPUT" | jq -r '.session_id // "unknown"' 2>/dev/null || echo unknown)"
SID8="${SESSION_ID:0:8}"

emit_block() {  # $1 = reason slug; additive, fail-open telemetry (no command/identifier leak)
    local B S
    B=$(jq -cn --arg h pre-push --arg t Bash --arg r "$1" --arg d deny '{hook:$h,tool:$t,reason:$r,decision:$d}' 2>/dev/null)
    S=$(printf '%s' "$INPUT" | jq -r '.session_id//"unknown"' 2>/dev/null || echo unknown)
    bash "$STRATA_HOME/telemetry/telemetry-emit.sh" hook_block "$S" "$B" 2>/dev/null || true
}

# Only trigger on git push.
echo "$COMMAND" | grep -qE 'git[[:space:]]+push' || exit 0

# Need git and a work tree.
command -v git &>/dev/null || exit 0
git rev-parse --is-inside-work-tree &>/dev/null || exit 0

# The knowledge base is expected to contain private identifiers and is not a public code repo.
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
case "$ROOT" in
    "$KB_DIR"|"$KB_DIR/"*) exit 0 ;;
esac

# --- What is actually going out? ---
# Prefer the tracked upstream, then origin/main|master, else (first push, no counterpart)
# the whole history from the empty tree.
RANGE=""
if UP="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)" && [ -n "$UP" ]; then
    RANGE="${UP}..HEAD"
elif git rev-parse --verify origin/main &>/dev/null; then
    RANGE="origin/main..HEAD"
elif git rev-parse --verify origin/master &>/dev/null; then
    RANGE="origin/master..HEAD"
else
    EMPTY_TREE="$(git hash-object -t tree /dev/null 2>/dev/null || true)"
    [ -n "$EMPTY_TREE" ] && RANGE="${EMPTY_TREE}..HEAD"
fi
[ -z "$RANGE" ] && exit 0

# Nothing to push (e.g. delete/tags-only) -> nothing to gate.
[ -z "$(git log "$RANGE" --oneline 2>/dev/null | head -1)" ] && exit 0

# Keep a location map beside the matcher input so findings can identify a source line
# without repeating the sensitive content that triggered the match.
added_context() {
    awk '
        /^\+\+\+ / {
            path = substr($0, 5)
            sub(/^b\//, "", path)
            next
        }
        /^@@ / {
            if (match($0, /\+[0-9]+(,[0-9]+)?/)) {
                next_line = substr($0, RSTART + 1, RLENGTH - 1)
                sub(/,.*/, "", next_line)
            }
            next
        }
        /^\+/ && $0 !~ /^\+\+\+/ {
            shown_path = (path == "" || path == "/dev/null") ? "<outgoing diff>" : path
            printf "%s:%d\n", shown_path, next_line
            next_line++
            next
        }
        /^\+/ { next_line++; next }
        /^ / { next_line++; next }
    '
}

# The endpoint diff is the fail-open fallback if history enumeration cannot be completed.
CUMULATIVE_PATCH="$(git diff "$RANGE" 2>/dev/null || true)"
CUMULATIVE_ADDED="$(printf '%s\n' "$CUMULATIVE_PATCH" | grep -E '^\+' | grep -vE '^\+\+\+' || true)"
CUMULATIVE_CONTEXT="$(printf '%s\n' "$CUMULATIVE_PATCH" | added_context || true)"
CUMULATIVE_FILES="$(git diff --name-only "$RANGE" 2>/dev/null || true)"
ADDED="$CUMULATIVE_ADDED"
ADDED_CONTEXT="$CUMULATIVE_CONTEXT"
ADDED_FILES="$CUMULATIVE_FILES"

# Endpoint diffs hide content added and removed in separate outgoing commits. Build the
# scan input from every commit, but publish it only when the complete walk succeeds.
if COMMITS="$(git rev-list "$RANGE" 2>/dev/null)" && [ -n "$COMMITS" ]; then
    PER_COMMIT_ADDED=""
    PER_COMMIT_CONTEXT=""
    PER_COMMIT_FILES=""
    per_commit_ok=1
    while IFS= read -r sha; do
        [ -n "$sha" ] || continue
        if ! PATCH="$(git show -U0 --format= "$sha" 2>/dev/null)"; then
            per_commit_ok=0
            break
        fi
        if ! COMMIT_FILES="$(git show --format= --name-only "$sha" 2>/dev/null)"; then
            per_commit_ok=0
            break
        fi

        COMMIT_ADDED="$(printf '%s\n' "$PATCH" | grep -E '^\+' | grep -vE '^\+\+\+' || true)"
        COMMIT_CONTEXT="$(printf '%s\n' "$PATCH" | added_context || true)"
        if [ -n "$COMMIT_ADDED" ]; then
            PER_COMMIT_ADDED+="${PER_COMMIT_ADDED:+$'\n'}$COMMIT_ADDED"
            PER_COMMIT_CONTEXT+="${PER_COMMIT_CONTEXT:+$'\n'}$COMMIT_CONTEXT"
        fi
        [ -n "$COMMIT_FILES" ] && PER_COMMIT_FILES+="${PER_COMMIT_FILES:+$'\n'}$COMMIT_FILES"
    done <<< "$COMMITS"

    if [ "$per_commit_ok" -eq 1 ]; then
        ADDED="$PER_COMMIT_ADDED"
        ADDED_CONTEXT="$PER_COMMIT_CONTEXT"
        ADDED_FILES="$(printf '%s\n' "$PER_COMMIT_FILES" | sed '/^$/d' | sort -u)"
    fi
fi

# Commit messages publish with the push and are permanent, but no diff contains them
# (`git show --format=` strips them by construction), so they need their own scan input.
MESSAGES="$(git log --format=%B "$RANGE" 2>/dev/null || true)"

# ============================================================================
# 1. PRIVACY SAFETY NET
# ============================================================================

# grep helper: case-insensitive ERE, `-e` so a leading '-' in the pattern (PEM headers) is
# never parsed as an option, and grep's no-match (1) never aborts under pipefail.
grepadd() { printf '%s\n' "$ADDED" | grep -inE -e "$1" 2>/dev/null || true; }
grepmsg() { printf '%s\n' "$MESSAGES" | grep -inE -e "$1" 2>/dev/null || true; }
# Filters for the FUZZY matchers only (never applied to strong token formats, to avoid
# false negatives like a real key on a line that happens to contain the word "test").
drop_placeholder() { grep -viE 'example|placeholder|your[_-]|xxxx+|<[^>]+>|dummy|changeme|redacted|sample|fake|env\[|environ|getenv|process\.env|import\.meta\.env|\$\{|os\.getenv|test[_-]?(key|token)|00000|123456|foo:bar' || true; }
drop_url_placeholder() { grep -viE 'example\.(com|org|net)|localhost|127\.0\.0\.1|your[_-]|xxxx+|<[^>]+>|user:(pass|password)@|placeholder' || true; }

# --- Secrets & credentials: blocked on ANY repo (a leaked key is bad everywhere). ---
# (a) Structural token formats. Front boundary (^|[^[:alnum:]]) stops substrings like "risk-".
SECRET_RE='(^|[^[:alnum:]])sk-ant-(api|admin|oat|sid)[0-9A-Za-z_-]{16,}' # Anthropic (key/admin/oauth)
SECRET_RE+='|(^|[^[:alnum:]])sk-(proj-)?[A-Za-z0-9_-]{20,}'        # OpenAI
SECRET_RE+='|(^|[^[:alnum:]])(sk|rk)_(live|test)_[A-Za-z0-9]{16,}' # Stripe secret/restricted
SECRET_RE+='|gh[porsu]_[A-Za-z0-9]{36,}'                           # GitHub token
SECRET_RE+='|github_pat_[A-Za-z0-9_]{40,}'                         # GitHub fine-grained PAT
SECRET_RE+='|glpat-[A-Za-z0-9_-]{20,}'                             # GitLab PAT
SECRET_RE+='|(AKIA|ASIA)[0-9A-Z]{16}'                              # AWS access key id
SECRET_RE+='|AIza[0-9A-Za-z_-]{35}'                                # Google API key
SECRET_RE+='|ya29\.[0-9A-Za-z_-]{20,}'                             # Google OAuth access token
SECRET_RE+='|(^|[^0-9A-Za-z_])1//0[A-Za-z0-9_-]{20,}'             # Google OAuth refresh token
SECRET_RE+='|xox[baprs]-[0-9A-Za-z-]{10,}'                         # Slack token
SECRET_RE+='|npm_[A-Za-z0-9]{36}'                                  # npm token
SECRET_RE+='|dop_v1_[a-f0-9]{64}'                                  # DigitalOcean token
SECRET_RE+='|hf_[A-Za-z0-9]{30,}'                                  # HuggingFace token
SECRET_RE+='|dckr_pat_[A-Za-z0-9_-]{20,}'                          # Docker Hub PAT
SECRET_RE+='|(FlyV1[[:space:]]|fm2_)[A-Za-z0-9+/=_-]{20,}'         # Fly.io token
SECRET_RE+='|tskey-(auth|api|client|reusable)-[A-Za-z0-9_-]{10,}' # Tailscale auth key
SECRET_RE+='|SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}'            # SendGrid
SECRET_RE+='|AC[0-9a-f]{32}'                                       # Twilio account SID
SECRET_RE+='|(^|[^0-9])[0-9]{8,10}:AA[A-Za-z0-9_-]{32,}'          # Telegram bot token
SECRET_RE+='|rpa_[A-Za-z0-9]{20,}'                                 # RunPod API key
SECRET_RE+='|(^|[^[:alnum:]])eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}' # JWT
SECRET_RE+='|-----BEGIN [A-Z ]*PRIVATE KEY-----'                   # PEM private key block

# (b) Credentials carried inside URLs, webhooks, DSNs, and auth headers.
SECRET_URL_RE='[a-z][a-z0-9+.-]*://[^/@:[:space:]]+:[^/@[:space:]]+@[^[:space:]/]'  # scheme://user:pass@host (DB/basic-auth/tokenised remote)
SECRET_URL_RE+='|https://hooks\.slack\.com/services/T[0-9A-Z]+/B[0-9A-Z]+/[0-9A-Za-z]{16,}'  # Slack webhook
SECRET_URL_RE+='|https://(ptb\.|canary\.)?discord(app)?\.com/api/webhooks/[0-9]{15,}/[0-9A-Za-z_-]{40,}'  # Discord webhook
SECRET_URL_RE+='|https://[0-9a-f]{16,}@[a-z0-9.-]*sentry\.io'      # Sentry DSN
SECRET_URL_RE+='|[Aa]uthorization:[[:space:]]*(Bearer|Basic)[[:space:]]+[A-Za-z0-9+/._=-]{20,}'  # auth header

# (c) Secret-named key assigned a long opaque value (catches ad-hoc secrets the formats miss).
GENERIC_SECRET_RE="(secret|token|passwd|password|api[_-]?key|access[_-]?key|client[_-]?secret|auth[_-]?token|private[_-]?key|aws_secret)([\"' ]*[:=]| =>)[[:space:]]*[\"'\`]?[A-Za-z0-9+/_=-]{24,}"

FINDINGS=""

# Render only source context plus a one-way fingerprint of the full matched line. The
# fingerprint distinguishes repeated findings without disclosing usable secret material.
mask_hits() {
    local hits="$1" hit lineno content context fp
    while IFS= read -r hit; do
        [ -n "$hit" ] || continue
        lineno="${hit%%:*}"
        content="${hit#*:}"
        context="$(printf '%s\n' "$ADDED_CONTEXT" | awk -v wanted="$lineno" 'NR == wanted { print; exit }')"
        [ -n "$context" ] || context="<outgoing added line>"
        fp="$(printf '%s' "$content" | git hash-object --stdin 2>/dev/null | cut -c1-8)"
        [ -n "$fp" ] || fp="unavailable"
        printf '%s: %s [redacted: sha8:%s; length:%d]\n' "$lineno" "$context" "$fp" "${#content}"
    done <<< "$hits"
}

# Message hits carry no diff context, and fixing one means rewriting the commit rather
# than adding a redacting commit, so they are labelled separately from diff findings.
mask_msg_hits() {
    local hits="$1" hit lineno content fp
    while IFS= read -r hit; do
        [ -n "$hit" ] || continue
        lineno="${hit%%:*}"
        content="${hit#*:}"
        fp="$(printf '%s' "$content" | git hash-object --stdin 2>/dev/null | cut -c1-8)"
        [ -n "$fp" ] || fp="unavailable"
        printf 'message line %s [redacted: sha8:%s; length:%d]\n' "$lineno" "$fp" "${#content}"
    done <<< "$hits"
}

MSGHITS="$(grepmsg "$SECRET_RE|$SECRET_URL_RE" | head -4 || true)"
[ -n "$MSGHITS" ] && MSGHITS="$(mask_msg_hits "$MSGHITS")"
[ -n "$MSGHITS" ] && FINDINGS+=$'[SECRET] credential-shaped string in an outgoing COMMIT MESSAGE (amend or rebase to fix; a later commit cannot redact it):\n'"$MSGHITS"$'\n'

HITS="$(grepadd "$SECRET_RE" | head -6 || true)"
[ -n "$HITS" ] && HITS="$(mask_hits "$HITS")"
[ -n "$HITS" ] && FINDINGS+=$'[SECRET] credential-shaped string in outgoing diff:\n'"$HITS"$'\n'

UHITS="$(grepadd "$SECRET_URL_RE" | drop_url_placeholder | head -6 || true)"
[ -n "$UHITS" ] && UHITS="$(mask_hits "$UHITS")"
[ -n "$UHITS" ] && FINDINGS+=$'[SECRET] credential inside a URL / webhook / DSN / auth header:\n'"$UHITS"$'\n'

GHITS="$(grepadd "$GENERIC_SECRET_RE" | drop_placeholder | head -6 || true)"
[ -n "$GHITS" ] && GHITS="$(mask_hits "$GHITS")"
[ -n "$GHITS" ] && FINDINGS+=$'[SECRET?] secret-named var assigned an opaque value (confirm not a real key):\n'"$GHITS"$'\n'

# A real .env file being committed (filename-level; .env.example/.sample/.template are safe).
ENVF="$(printf '%s\n' "$ADDED_FILES" | grep -E '(^|/)\.env($|\.[a-z]+$)' | grep -vE '\.(example|sample|template|dist|md|txt)$' | head -4 || true)"
[ -n "$ENVF" ] && FINDINGS+=$'[SECRET?] a real .env file is being committed (use .env.example for shareable keys):\n'"$ENVF"$'\n'

# --- Private identifiers: only meaningful when the destination is a PUBLIC repo. ---
IS_PUBLIC=0
if command -v gh &>/dev/null; then
    PRIV="$( (cd "$ROOT" && gh repo view --json isPrivate --jq '.isPrivate') 2>/dev/null || echo true )"
    [ "$PRIV" = "false" ] && IS_PUBLIC=1
fi

if [ "$IS_PUBLIC" -eq 1 ]; then
    # Load the install-local leak inventory as fixed strings. Comments and blank lines
    # carry no tokens; matching is case-insensitive.
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

    # An unconfigured denylist is a clean no-op; universal secret checks still apply.
    if [ -n "$DENY_TOKENS" ]; then
        PHITS="$(printf '%s\n' "$ADDED" | grep -iniF -f <(printf '%s' "$DENY_TOKENS") 2>/dev/null | head -8 || true)"
        [ -n "$PHITS" ] && PHITS="$(mask_hits "$PHITS")"
        [ -n "$PHITS" ] && FINDINGS+=$'[PRIVATE] private identifier from the local denylist in diff to a PUBLIC repo:\n'"$PHITS"$'\n'

        PMHITS="$(printf '%s\n' "$MESSAGES" | grep -iniF -f <(printf '%s' "$DENY_TOKENS") 2>/dev/null | head -6 || true)"
        [ -n "$PMHITS" ] && PMHITS="$(mask_msg_hits "$PMHITS")"
        [ -n "$PMHITS" ] && FINDINGS+=$'[PRIVATE] private identifier from the local denylist in an outgoing COMMIT MESSAGE to a PUBLIC repo (amend or rebase to fix):\n'"$PMHITS"$'\n'
    fi
fi

# ============================================================================
# 2. DECISION: stop and surface once per HEAD (privacy findings and/or unreviewed work).
# ============================================================================

# Fresh verify marker = /verify passed this session with no edits after it.
VERIFY="$STATE_DIR/.verify-passed-$SID8"
EDITS="$STATE_DIR/.session-edits-$SID8"
reviewed=0
if [ -f "$VERIFY" ] && { [ ! -f "$EDITS" ] || [ ! "$EDITS" -nt "$VERIFY" ]; }; then
    reviewed=1
fi

# Clean diff and already reviewed -> nothing to surface, push through.
[ -z "$FINDINGS" ] && [ "$reviewed" -eq 1 ] && exit 0

# Surface once per HEAD: a re-push of the same commits is the decision -> allow.
HEAD_SHA="$(git rev-parse HEAD 2>/dev/null || echo none)"
SURFACED="$STATE_DIR/.pushgate-surfaced-$SID8"
[ -f "$SURFACED" ] && [ "$(cat "$SURFACED" 2>/dev/null)" = "$HEAD_SHA" ] && exit 0
printf '%s' "$HEAD_SHA" > "$SURFACED" 2>/dev/null || true

REASON="unreviewed-surface"
{
    if [ -n "$FINDINGS" ]; then
        REASON="privacy-surface"
        echo "PAUSE (privacy): the diff you are about to push contains strings that look sensitive."
        echo "$FINDINGS"
        echo "Decide, then re-run the SAME push to proceed:"
        echo "  - Redact anything that is a real secret or private identifier (a new commit re-scans)."
        echo "  - If you have confirmed these are false positives, the re-push carries them through."
        [ "$reviewed" -eq 0 ] && echo
    fi
    if [ "$reviewed" -eq 0 ]; then
        echo "PAUSE (unreviewed push): these commits were not verified this session (no fresh .verify-passed marker)."
        echo "  - Run /verify or /review if this has not been reviewed and iterated."
        echo "  - Otherwise re-run the same push; the re-push is your decision and the gate allows it."
    fi
    echo "Pushing: $RANGE"
} >&2
emit_block "$REASON"
exit 2
