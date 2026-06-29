#!/usr/bin/env bash
# gate-rm-guard.sh - PreToolUse(Bash) blocking hook
# Blocks rm on project/home files. Redirects to the ~/to-delete/ workflow.
# Allows rm on safe targets: /tmp/, *.pyc, __pycache__, node_modules, build/dist artifacts.
# Config: matcher "Bash" + if "Bash(rm *)". Input: hook JSON on stdin. Deny: exit 2 + stderr.
set -uo pipefail

INPUT="$(cat)"

# Fail open on infra problems: without jq we cannot parse, so allow rather than hard-block.
if ! command -v jq >/dev/null 2>&1; then
    echo "gate-rm-guard: jq unavailable, allowing command" >&2
    exit 0
fi

COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)"

# Only act on rm commands; anything else is allowed.
echo "$COMMAND" | grep -qE '\brm\b' || exit 0

# Allow safe targets: /tmp/, caches, and obvious build artifacts.
SAFE_PATTERN='/tmp/|\.pyc($|[^a-z])|__pycache__|/node_modules/|/\.cache/|/build/|/dist/|/target/|\.o($|[^a-z])|\.class($|[^a-z])'
if echo "$COMMAND" | grep -qE "$SAFE_PATTERN"; then
    exit 0
fi

# Allow rm of /dev/null or shell-variable targets.
if echo "$COMMAND" | grep -qE 'rm[[:space:]]+/dev/null|rm[[:space:]]+\$[A-Z_]+\b'; then
    exit 0
fi

cat >&2 <<'EOF'
Direct deletion blocked. Use the to-delete workflow instead:
  mv <file> ~/to-delete/<name>
  echo '<name> | <original-path> | <YYYY-MM-DD> | <reason>' >> ~/to-delete/manifest.txt
If the file is a true temp/artifact (/tmp, __pycache__, node_modules, build/dist), rm is fine.
EOF
exit 2
