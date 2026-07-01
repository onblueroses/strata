#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="${ROOT_DIR}/hooks/gate-gh-public-actions.sh"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

run_hook() {
    local command="$1"

    jq -n --arg command "$command" '{tool_input: {command: $command}}' \
        | STRATA_HOME="$TMP_DIR/strata" "$HOOK" >/dev/null 2>&1
}

assert_allowed() {
    local command="$1"

    if ! run_hook "$command"; then
        printf 'expected allowed: %s\n' "$command" >&2
        exit 1
    fi
}

assert_blocked() {
    local command="$1"

    if run_hook "$command"; then
        printf 'expected blocked: %s\n' "$command" >&2
        exit 1
    fi
}

assert_blocked 'gh -R owner/repo issue create --title t --body b'
assert_blocked "'gh' issue create --title t --body b"
assert_blocked "bash -lc 'gh issue create --title t --body b'"
assert_blocked "bash -lc 'gh pr create --title t --body b'"
assert_blocked "echo \"\$(gh issue create --title t --body b)\""
assert_blocked "echo \"\$(gh api repos/owner/repo -X POST)\""
assert_blocked "echo \"\$(gh api repos/owner/repo -f foo=bar)\""
assert_blocked "echo \"\$(bash -lc 'gh pr create --title t --body b')\""
assert_blocked "echo \`gh issue create --title t --body b\`"
assert_allowed 'gh -R owner/repo issue list --limit 1'
assert_allowed 'gh issue list'
assert_allowed 'gh issue list --search create'
assert_allowed 'gh pr list --search "add login"'
assert_allowed 'gh issue view 5'
assert_allowed "'gh' issue list"
assert_allowed "bash -lc 'gh issue list --limit 1'"
assert_allowed "echo \"\$(date)\""
assert_allowed 'gh api repos/owner/repo'
assert_allowed 'gh api repos/owner/repo --method GET'
