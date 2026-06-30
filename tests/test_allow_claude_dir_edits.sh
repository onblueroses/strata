#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$ROOT_DIR/hooks/allow-claude-dir-edits.sh"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT

fail() {
    printf '%s\n' "$1" >&2
    exit 1
}

run_hook() {
    local file_path="$1"

    jq -n --arg file_path "$file_path" \
        '{tool_name: "Write", tool_input: {file_path: $file_path}}' \
        | bash "$HOOK"
}

assert_blocked() {
    local file_path="$1"
    local stdout
    local stderr
    local status

    stdout=$(mktemp "$TMP_DIR/stdout.XXXXXX")
    stderr=$(mktemp "$TMP_DIR/stderr.XXXXXX")
    status=0

    run_hook "$file_path" >"$stdout" 2>"$stderr" || status=$?

    [ "$status" -ne 0 ] || fail "expected blocked: $file_path"
    grep -q 'BLOCKED' "$stderr" || fail "expected block reason on stderr: $file_path"
    ! grep -q '"permissionDecision":"allow"' "$stdout" || fail "expected no allow decision: $file_path"
}

assert_allowed() {
    local file_path="$1"
    local stdout
    local stderr
    local status

    stdout=$(mktemp "$TMP_DIR/stdout.XXXXXX")
    stderr=$(mktemp "$TMP_DIR/stderr.XXXXXX")
    status=0

    run_hook "$file_path" >"$stdout" 2>"$stderr" || status=$?

    [ "$status" -eq 0 ] || fail "expected allowed: $file_path"
    grep -q '"permissionDecision":"allow"' "$stdout" || fail "expected allow decision: $file_path"
}

REPO_DIR="$TMP_DIR/repo"
CLAUDE_DIR="$REPO_DIR/.claude"
mkdir -p "$CLAUDE_DIR"

printf '{}\n' >"$CLAUDE_DIR/settings.json"
ln -s settings.json "$CLAUDE_DIR/README.md"

assert_blocked "$CLAUDE_DIR/settings.json"
assert_blocked "$CLAUDE_DIR/README.md"

rm "$CLAUDE_DIR/README.md"
printf '# Notes\n' >"$CLAUDE_DIR/README.md"

assert_allowed "$CLAUDE_DIR/README.md"
