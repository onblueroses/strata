#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="${ROOT_DIR}/hooks/gate-codex-exec.sh"

run_hook() {
    local command="$1"

    jq -n --arg command "$command" '{tool_input: {command: $command}}' \
        | "$HOOK" >/dev/null 2>&1
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

assert_blocked 'codex exec "prompt --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check"'
assert_allowed 'codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check "prompt"'
assert_blocked "codex review --uncommitted \`codex exec \"prompt\"\`"
assert_allowed 'codex review --uncommitted'
assert_blocked 'codex exec "unterminated'
assert_allowed 'printf "unterminated'
