#!/usr/bin/env bash
# gate-nested-clone.sh - PreToolUse(Bash(git clone*)) advisory hook
# Warns when `git clone` would create a clone inside an existing git repo.
# Catches the "clone-inside-clone" footgun: running `git clone <url>` while
# already inside a working tree silently nests the new repo as a subdirectory,
# which is almost never intended.

TOOL_INPUT="${CLAUDE_TOOL_INPUT:-}"

# Only trigger on git clone
if ! echo "$TOOL_INPUT" | grep -qE '"command"[[:space:]]*:[[:space:]]*"[^"]*git[[:space:]]+clone'; then
    exit 0
fi

# Extract the target dir from the command if specified; otherwise the cwd matters
COMMAND=$(echo "$TOOL_INPUT" | grep -oE '"command"[[:space:]]*:[[:space:]]*"[^"]*"' | sed 's/.*"command"[[:space:]]*:[[:space:]]*"\(.*\)"/\1/')

# Are we currently inside a git repo? (If yes, clone target lands inside it.)
PARENT_REPO=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0

# We're inside a git repo. Is the clone going elsewhere via absolute path? Skip the warning then.
if echo "$COMMAND" | grep -qE 'git clone [^ ]+ +/'; then
    exit 0
fi

# Inside a repo + clone with relative target = footgun.
echo "{\"result\": \"block\", \"reason\": \"git clone inside existing repo at ${PARENT_REPO}. This creates a nested clone-inside-clone, which is almost never intended. If you really want a nested clone, pass an absolute path target or cd to a parent dir first. If you meant to clone a fresh repo, run 'cd ~ && git clone ...' instead.\"}"
exit 2
