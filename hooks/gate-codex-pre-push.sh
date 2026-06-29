#!/usr/bin/env bash
# gate-codex-pre-push.sh - PreToolUse(Bash) review gate
# Runs a cross-model review on the branch diff before `git push` (quality, logic, elegance),
# not just correctness. A critical finding blocks the push so issues are fixed before they ship.
#
# Config: matcher "Bash" + per-hook filter `Bash(git push*)`. Input: stdin JSON.
# Deny: a critical review finding writes a human-readable reason on stderr + exit 2
#       (the PreToolUse deny signal).
# Fails OPEN (exit 0) on infrastructure errors: missing jq, an unavailable review CLI, or a
# broker/CLI crash WARN on stderr and allow the push. A tooling gap never hard-blocks, and a
# crash is never conflated with a clean pass.
set -uo pipefail

# Fail open when jq is missing: an infra gap should warn, never block a push.
if ! command -v jq >/dev/null 2>&1; then
    echo "[pre-push] jq not found; skipping pre-push review." >&2
    exit 0
fi

INPUT="$(cat)"
COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"

# Act only on git push commands; anything else is allowed.
echo "$COMMAND" | grep -qE 'git[[:space:]]+push' || exit 0

# Skip the knowledge-base repo (notes, not code) when $KB_DIR marks it.
KB="${KB_DIR:-}"
TOPLEVEL="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [ -n "$KB" ] && [ -n "$TOPLEVEL" ]; then
    if command -v realpath >/dev/null 2>&1; then
        [ "$(realpath -m "$TOPLEVEL")" = "$(realpath -m "$KB")" ] && exit 0
    elif [ "$TOPLEVEL" = "$KB" ]; then
        exit 0
    fi
fi

# Need a review CLI available; warn and allow if absent.
if ! command -v codex >/dev/null 2>&1; then
    echo "[pre-push] review CLI not found; skipping pre-push review." >&2
    exit 0
fi

# Determine the base branch.
if git rev-parse --verify origin/main >/dev/null 2>&1; then
    BASE_BRANCH="main"
elif git rev-parse --verify origin/master >/dev/null 2>&1; then
    BASE_BRANCH="master"
else
    exit 0
fi

# Any commits to push?
COMMITS="$(git log "origin/${BASE_BRANCH}..HEAD" --oneline 2>/dev/null || true)"
[ -z "$COMMITS" ] && exit 0

# Run review via warm broker (fast) when present, else fall back to cold CLI.
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")/../scripts"
REVIEW_SCRIPT="${SCRIPT_DIR}/codex-broker-review.mjs"

if [ -f "$REVIEW_SCRIPT" ]; then
    CWD="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
    node "$REVIEW_SCRIPT" "$CWD" "$BASE_BRANCH" >/dev/null 2>&1
    EXIT_CODE=$?
else
    timeout --kill-after=10 1800 codex review --base "origin/${BASE_BRANCH}" >/dev/null 2>&1
    EXIT_CODE=$?
fi

if [ "$EXIT_CODE" -eq 2 ]; then
    echo "Pre-push review found critical issues. Run: codex review --base origin/${BASE_BRANCH} to see details, fix them, then re-push." >&2
    exit 2
elif [ "$EXIT_CODE" -ne 0 ]; then
    # A broker/CLI crash is not a clean pass: warn and allow rather than hard-block on infra.
    echo "[pre-push] WARNING: review did not complete (exit ${EXIT_CODE}); push allowed without review. Run 'codex review --base origin/${BASE_BRANCH}' manually." >&2
    exit 0
fi

exit 0
