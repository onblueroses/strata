#!/usr/bin/env bash
# Block gh issue/pr create/comment on public repos without user confirmation.
# PreToolUse hook for Bash(gh *)
set -euo pipefail

INPUT="$(cat)"
COMMAND="$(echo "$INPUT" | jq -r '.tool_input.command // empty')"

# Only care about gh commands
[[ "$COMMAND" == *"gh "* ]] || exit 0

# Check for public-facing actions
if echo "$COMMAND" | grep -qE 'gh (issue|pr) (create|comment|edit|close|reopen|merge)'; then
  echo '{"decision":"block","reason":"BLOCKED: gh issue/pr actions on public repos require explicit user approval. Show the user what you want to post and get confirmation first."}'
  exit 0
fi

exit 0
