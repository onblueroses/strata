#!/usr/bin/env bash
# gate-gh-public-actions.sh - PreToolUse(Bash) deny gate.
#
# Two layers enforcing the no-public-posts + privacy rules on gh CLI usage:
#   Layer 1: deny public-facing gh actions (issue/pr/release/gist/repo
#            create/comment/edit/close/reopen/merge/delete/publish) AND
#            gh api WRITE calls (-X / --method POST|PATCH|PUT|DELETE, plus the
#            implicit POST that field flags force) without explicit approval.
#   Layer 2: privacy scrub. Deny any gh command whose PUBLISHABLE content
#            (inline --body/--title or a referenced --body-file) carries a
#            private identifier from the local denylist.
#
# Contract: matcher "Bash" (settings.json adds the per-hook gh filter). Input is
# tool JSON on STDIN. Deny = human-readable reason on stderr + exit 2. Allow =
# exit 0. Infrastructure failure (no jq) WARNS and allows (fail open); a gate
# never hard-blocks on its own broken plumbing.
#
# The denylist is NOT hardcoded: it is read from gitignored token files (see
# config/private-tokens.example.txt). Ship the .example.txt template only.
set -uo pipefail

# Fail open if jq is unavailable: warn, allow. (infra error, not a policy hit)
if ! command -v jq >/dev/null 2>&1; then
    echo "[gate-gh-public-actions] jq not found; allowing command without gh public-action check." >&2
    exit 0
fi

INPUT="$(cat)"
COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"

# Act only on gh commands; everything else is allowed untouched.
echo "$COMMAND" | grep -qE '(^|[^[:alnum:]_-])gh[[:space:]]' || exit 0

# --- Layer 1: public-facing / write actions require explicit approval ---
api_implicit_write() {
    # gh api defaults to GET but flips to POST when field flags are present.
    echo "$COMMAND" | grep -qE 'gh[[:space:]]+api([[:space:]]|$)' \
        && echo "$COMMAND" | grep -qE '(^|[[:space:]])(-f|-F|--field|--raw-field|--input)([[:space:]=]|$)' \
        && ! echo "$COMMAND" | grep -qiE '(-X[[:space:]]*GET|--method[[:space:]=]*GET)'
}

if echo "$COMMAND" | grep -qE 'gh[[:space:]]+(issue|pr|release|gist|repo)[[:space:]]+(create|comment|edit|close|reopen|merge|delete|publish|upload|delete-asset)' \
   || echo "$COMMAND" | grep -qiE 'gh[[:space:]]+api([[:space:]]|$).*(-X[[:space:]]*(POST|PATCH|PUT|DELETE)|--method[[:space:]=]*(POST|PATCH|PUT|DELETE))' \
   || api_implicit_write; then
    echo "BLOCKED: this gh command performs a public-facing or write action (issue/pr/release/repo/gist or a gh api write) and requires explicit user approval. Show the user the exact content you want to post and get confirmation first (no-public-posts rule)." >&2
    exit 2
fi

# --- Layer 2: privacy scrub of publishable content ---
# Collect text that could reach a public surface: --body-file/-F file contents +
# inline --body/-b and --title/-t values. Bare path arguments are deliberately
# NOT scanned, so a clean post written from a private-looking path is allowed.
PUB=""
for bf in $(printf '%s' "$COMMAND" | grep -oE -- '(--body-file|-F)[=[:space:]]+[^[:space:]]+' | sed -E 's/^(--body-file|-F)[=[:space:]]+//'); do
    [ -f "$bf" ] && PUB="$PUB
$(cat "$bf" 2>/dev/null)"
done
PUB="$PUB
$(printf '%s' "$COMMAND" | grep -oiE -- "(--body|-b|--title|-t)[=[:space:]]+(\"[^\"]*\"|'[^']*')" || true)"

# Build the denylist from gitignored token files. Format (per the .example.txt):
# one token per line, matched as a fixed string, case-insensitive; lines that
# start with # and blank lines are ignored.
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

# No denylist configured -> nothing to scrub against; allow.
if [ -n "$DENY_TOKENS" ] && printf '%s' "$PUB" | grep -qiF -f <(printf '%s' "$DENY_TOKENS"); then
    echo "BLOCKED (privacy): the publishable content of this gh command contains a private identifier from your local denylist. Replace it with generic, domain-neutral values and re-confirm before posting (privacy rule)." >&2
    printf '%s' "$PUB" | grep -iniF -f <(printf '%s' "$DENY_TOKENS") 2>/dev/null | head -3 >&2
    exit 2
fi

exit 0
