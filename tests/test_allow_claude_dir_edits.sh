#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$ROOT_DIR/hooks/allow-claude-dir-edits.sh"

dangerous_input='{"tool_name":"Write","tool_input":{"file_path":"/tmp/repo/.claude/settings.json"}}'
benign_input='{"tool_name":"Write","tool_input":{"file_path":"/tmp/repo/.claude/README.md"}}'

dangerous_stdout=$(mktemp)
dangerous_stderr=$(mktemp)
benign_stdout=$(mktemp)
benign_stderr=$(mktemp)
trap 'rm -f "$dangerous_stdout" "$dangerous_stderr" "$benign_stdout" "$benign_stderr"' EXIT

dangerous_status=0
printf '%s' "$dangerous_input" | bash "$HOOK" >"$dangerous_stdout" 2>"$dangerous_stderr" || dangerous_status=$?

if [ "$dangerous_status" -eq 0 ]; then
    echo "expected .claude/settings.json write to be blocked" >&2
    exit 1
fi

if ! grep -q 'BLOCKED' "$dangerous_stderr"; then
    echo "expected block reason on stderr for .claude/settings.json write" >&2
    exit 1
fi

if grep -q '"permissionDecision":"allow"' "$dangerous_stdout"; then
    echo "dangerous .claude/settings.json write was still auto-approved" >&2
    exit 1
fi

printf '%s' "$benign_input" | bash "$HOOK" >"$benign_stdout" 2>"$benign_stderr"

if ! grep -q '"permissionDecision":"allow"' "$benign_stdout"; then
    echo "expected inert .claude README edit to be auto-approved" >&2
    cat "$benign_stdout" >&2
    cat "$benign_stderr" >&2
    exit 1
fi
