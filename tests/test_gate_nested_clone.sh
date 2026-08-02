#!/usr/bin/env bash
# shellcheck disable=SC2016  # Command substitutions below are literal hook inputs.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="${ROOT_DIR}/hooks/gate-nested-clone.sh"
TMP_DIR="$(mktemp -d)"
OUTSIDE_DIR="$TMP_DIR/outside"
OUTSIDE_REPO="$TMP_DIR/existing-repo"
mkdir -p "$OUTSIDE_DIR"
git init -q "$OUTSIDE_REPO"
trap 'rm -rf "$TMP_DIR"' EXIT

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
    local command="$1" status

    set +e
    run_hook "$command"
    status=$?
    set -e
    if [[ $status -ne 2 ]]; then
        printf 'expected blocked with rc=2, got rc=%s: %s\n' "$status" "$command" >&2
        exit 1
    fi
}

for command in \
    'git clone https://example.invalid/x' \
    'sudo git clone https://example.invalid/x' \
    'doas git clone https://example.invalid/x' \
    'command git clone https://example.invalid/x' \
    'builtin git clone https://example.invalid/x' \
    'exec git clone https://example.invalid/x' \
    'env A=1 git clone https://example.invalid/x' \
    'env -S "git clone https://example.invalid/x"' \
    'env --split-string="git clone https://example.invalid/x"' \
    'nice git clone https://example.invalid/x' \
    'ionice git clone https://example.invalid/x' \
    'nohup git clone https://example.invalid/x' \
    'stdbuf -oL git clone https://example.invalid/x' \
    'time git clone https://example.invalid/x' \
    'timeout 60 git clone https://example.invalid/x' \
    'setsid git clone https://example.invalid/x' \
    'xargs git clone https://example.invalid/x' \
    'chronic git clone https://example.invalid/x' \
    '/usr/bin/git clone https://example.invalid/x' \
    'true ; git clone https://example.invalid/x' \
    'true && git clone https://example.invalid/x' \
    'false || git clone https://example.invalid/x' \
    'printf x | git clone https://example.invalid/x' \
    'true & git clone https://example.invalid/x' \
    $'true\ngit clone https://example.invalid/x' \
    $'echo git clone as data\ngit clone https://example.invalid/x' \
    '(git clone https://example.invalid/x)' \
    'echo "$(git clone https://example.invalid/x)"' \
    'echo `git clone https://example.invalid/x`' \
    "bash -c 'git clone https://example.invalid/x'" \
    "cd $ROOT_DIR && git clone https://example.invalid/x dest" \
    "git -C $ROOT_DIR clone https://example.invalid/x dest" \
    "git -C $OUTSIDE_REPO clone https://example.invalid/x dest" \
    "eval 'git clone https://example.invalid/x'"; do
    assert_blocked "$command"
done


for command in \
    "cd $OUTSIDE_DIR && git clone https://example.invalid/x dest" \
    "git -C $OUTSIDE_DIR clone https://example.invalid/x dest"; do
    assert_allowed "$command"
done

for command in \
    'echo git clone https://example.invalid/x' \
    'grep git clone notes.md' \
    'grep "git clone" notes.md' \
    'cat file-about-git-clone.md' \
    'ls gitfoo/' \
    'git status' \
    'git clone' \
    'git clone https://example.invalid/x /tmp/strata-clone-target'; do
    assert_allowed "$command"
done

for command in \
    'sudo -u git echo clone' \
    'env -u git echo clone' \
    'timeout --signal git 60 echo clone' \
    'xargs -I git echo clone' \
    'command -v git clone' \
    'timeout --help git clone'; do
    assert_allowed "$command"
done
