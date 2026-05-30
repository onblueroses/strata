#!/usr/bin/env bash
# Pre-push gate: runs codex review on branch diff before git push.
# Checks code quality, logic, and elegance - not just correctness.
# Blocking hook: exits non-zero to prevent the push if critical issues found.

TOOL_INPUT="${CLAUDE_TOOL_INPUT:-}"

# Only trigger on git push commands
if ! echo "$TOOL_INPUT" | grep -qE '"command"\s*:\s*"[^"]*git\s+push'; then
    exit 0
fi

# Skip if pushing to life repo (knowledge base, not code)
if echo "$TOOL_INPUT" | grep -qE 'life\.git|life\s'; then
    exit 0
fi

# Check codex is available
if ! command -v codex &>/dev/null; then
    echo '{"result": "warn", "message": "Codex CLI not found - skipping pre-push review"}'
    exit 0
fi

# Determine the base branch - try origin/main, then origin/master
BASE_BRANCH=""
if git rev-parse --verify origin/main &>/dev/null 2>&1; then
    BASE_BRANCH="main"
elif git rev-parse --verify origin/master &>/dev/null 2>&1; then
    BASE_BRANCH="master"
else
    exit 0
fi

# Check if there are commits to push
COMMITS=$(git log "origin/${BASE_BRANCH}..HEAD" --oneline 2>/dev/null || true)
if [[ -z "$COMMITS" ]]; then
    exit 0
fi

# Run review via warm broker (fast) or fall back to cold CLI.
# The broker-review script connects to the already-running app-server,
# avoiding the 5-10s cold-start overhead of `codex review`.
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")/../scripts"
REVIEW_SCRIPT="${SCRIPT_DIR}/codex-broker-review.mjs"

if [[ -f "$REVIEW_SCRIPT" ]]; then
    CWD="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
    node "$REVIEW_SCRIPT" "$CWD" "$BASE_BRANCH" >/dev/null 2>&1
    EXIT_CODE=$?
else
    # Fallback: cold CLI with 30-min timeout
    timeout --kill-after=10 1800 codex review --base "origin/${BASE_BRANCH}" >/dev/null 2>&1
    EXIT_CODE=$?
fi

if [[ $EXIT_CODE -eq 2 ]]; then
    echo '{"result": "block", "reason": "Codex pre-push review found critical issues. Run `codex review --base origin/'"${BASE_BRANCH}"'` to see details."}'
    exit 2
fi

exit 0
