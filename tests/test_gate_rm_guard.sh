#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="${ROOT_DIR}/hooks/gate-rm-guard.sh"

run_hook() {
    local command="$1"

    jq -n --arg command "$command" '{tool_input: {command: $command}}' \
        | bash "$HOOK" >/dev/null 2>&1
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

assert_blocked 'rm -rf /home/user/project/important /tmp/scratch'
assert_blocked "rm \$HOME/.ssh/id_rsa"
assert_allowed 'rm -rf /tmp/scratch'
