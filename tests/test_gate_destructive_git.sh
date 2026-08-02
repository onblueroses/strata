#!/usr/bin/env bash
# shellcheck disable=SC2016  # Command substitutions below are literal hook inputs.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="${ROOT_DIR}/hooks/gate-destructive-git.sh"

run_hook() {
    local command="$1"

    jq -n --arg command "$command" '{tool_input: {command: $command}}' \
        | "$HOOK" 2>/dev/null
}

assert_allowed() {
    local command="$1" output

    output="$(run_hook "$command")"
    if [[ -n $output ]]; then
        printf 'expected allowed without decision: %s\n' "$command" >&2
        exit 1
    fi
}

assert_asked() {
    local command="$1" output

    output="$(run_hook "$command")"
    if ! jq -e '.hookSpecificOutput.permissionDecision == "ask"' <<<"$output" >/dev/null; then
        printf 'expected ask decision: %s\n' "$command" >&2
        exit 1
    fi
}

for command in \
    'git reset --hard' \
    'sudo git reset --hard' \
    'doas git reset --hard' \
    'command git reset --hard' \
    'builtin git reset --hard' \
    'exec git reset --hard' \
    'env A=1 git reset --hard' \
    'env -S "git reset --hard"' \
    'env --split-string="git reset --hard"' \
    'nice git reset --hard' \
    'ionice git reset --hard' \
    'nohup git reset --hard' \
    'stdbuf -oL git reset --hard' \
    'time git reset --hard' \
    'timeout 60 git reset --hard' \
    'setsid git reset --hard' \
    'xargs git reset --hard' \
    'chronic git reset --hard' \
    '/usr/bin/git reset --hard' \
    'git -C /path reset --hard' \
    'true ; git reset --hard' \
    'true && git reset --hard' \
    'false || git reset --hard' \
    'printf x | git reset --hard' \
    'true & git reset --hard' \
    $'true\ngit reset --hard' \
    $'echo git reset --hard as data\ngit reset --hard' \
    '(git reset --hard)' \
    'echo "$(git reset --hard)"' \
    'echo `git reset --hard`' \
    "bash -c 'git reset --hard'" \
    "bash -O extglob -lc 'git reset --hard'" \
    "eval 'git reset --hard'" \
    'git clean -fd' \
    'git branch -D topic' \
    'git branch -Dtopic' \
    'git checkout -- file' \
    'git restore .' \
    'git stash clear' \
    'git stash drop'; do
    assert_asked "$command"
done

for command in \
    'grep "git reset --hard" README.md' \
    'grep git reset --hard README.md' \
    'echo git reset --hard' \
    'cat file-about-git-reset-hard.md' \
    'ls gitfoo/' \
    'git status' \
    'git reset --soft HEAD~1' \
    'git clean -n' \
    'git branch -d topic' \
    'git checkout topic' \
    'git stash list'; do
    assert_allowed "$command"
done

for command in \
    'sudo -u git echo reset --hard' \
    'env -u git echo reset --hard' \
    'timeout --signal git 60 echo reset --hard' \
    'xargs -I git echo reset --hard' \
    'command -v git reset --hard' \
    'timeout --help git reset --hard'; do
    assert_allowed "$command"
done
