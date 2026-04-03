#!/usr/bin/env bash
# Run codex review on branch diff before git push. Blocks on critical issues.
# Event: PreToolUse (Bash)
# Config: {"hooks":{"PreToolUse":[{"matcher":{"tool_name":"Bash"},"hooks":[{"type":"command","command":"hooks/gate-codex-pre-push.sh"}]}]}}

TOOL_INPUT="${CLAUDE_TOOL_INPUT:-}"

# Only trigger on git push commands
if ! echo "$TOOL_INPUT" | grep -qE '"command"\s*:\s*"[^"]*git\s+push'; then
    exit 0
fi

# Check codex is available and authenticated
if ! command -v codex &>/dev/null; then
    echo '{"result": "warn", "message": "Codex CLI not found - skipping pre-push review"}'
    exit 0
fi

if [[ ! -f "$HOME/.codex/auth.json" ]]; then
    echo '{"result": "warn", "message": "Codex not authenticated - skipping pre-push review"}'
    exit 0
fi

# Determine the base branch - try origin/main, then origin/master
BASE_BRANCH=""
if git rev-parse --verify origin/main &>/dev/null 2>&1; then
    BASE_BRANCH="main"
elif git rev-parse --verify origin/master &>/dev/null 2>&1; then
    BASE_BRANCH="master"
else
    # No remote tracking branch found - skip review
    exit 0
fi

# Check if there are commits to push
COMMITS=$(git log "origin/${BASE_BRANCH}..HEAD" --oneline 2>/dev/null || true)
if [[ -z "$COMMITS" ]]; then
    exit 0
fi

# Run codex review on the branch diff
REVIEW_OUTPUT=$(codex review --base "origin/${BASE_BRANCH}" 2>&1 || true)

# Check for critical findings - match Codex severity markers [P0], [P1], and common keywords
if echo "$REVIEW_OUTPUT" | grep -qiE '(\[P0\]|CRITICAL|blocking issue|unsafe to ship)'; then
    echo '{"result": "block", "reason": "Codex pre-push review found critical issues. Run `codex review --base origin/'"${BASE_BRANCH}"'` to see details. Fix issues before pushing."}'
    exit 2
fi

exit 0
