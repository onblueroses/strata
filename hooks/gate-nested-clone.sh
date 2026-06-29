#!/usr/bin/env bash
# gate-nested-clone.sh - PreToolUse(Bash) deny gate
# Denies `git clone` that would create a clone inside an existing git repo.
# The clone-inside-clone footgun: running `git clone <url>` while already inside
# a working tree silently nests the new repo as a subdirectory, almost never intended.
# Config: matcher "Bash" + if "Bash(git clone*)". Input: stdin JSON. Deny: exit 2 + stderr.
set -uo pipefail

# Fail OPEN on infra problems: without jq we cannot parse the input, so warn and allow.
if ! command -v jq >/dev/null 2>&1; then
    echo "[nested-clone] jq not found; skipping nested-clone check." >&2
    exit 0
fi

INPUT="$(cat)"
COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"

# Only act on git clone; any other command is allowed.
echo "$COMMAND" | grep -qE 'git[[:space:]]+clone' || exit 0

# Are we inside a git repo? If yes, a relative-target clone lands inside it.
# Fail OPEN when git is unavailable or we are not inside a repo (nothing to nest into).
PARENT_REPO=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0

# Clone targeting an absolute path goes elsewhere; allow.
if echo "$COMMAND" | grep -qE 'git[[:space:]]+clone[[:space:]]+[^ ]+[[:space:]]+/'; then
    exit 0
fi

# Inside a repo + relative (or default) target = nested clone-inside-clone. Deny.
echo "git clone inside existing repo at ${PARENT_REPO}. This creates a nested clone-inside-clone, which is almost never intended. Pass an absolute-path target, or cd to a parent directory first (e.g. 'cd ~ && git clone ...')." >&2
exit 2
