#!/usr/bin/env bash
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"; hook="$script_dir/allow-claude-dir-edits.sh"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/.claude"
payload='{"tool_name":"Write","tool_input":{"file_path":".claude/relative.md"}}'
out="$(cd "$tmp" && printf '%s' "$payload" | bash "$hook")"
[[ "$out" == *'"permissionDecision":"allow"'* ]]
printf 'allow-claude-dir-edits: relative .claude path allowed\n'
