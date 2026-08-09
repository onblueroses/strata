#!/usr/bin/env bash
# shellcheck disable=SC2016  # Command substitutions below are literal hook inputs.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="${ROOT_DIR}/hooks/gate-paid-compute-destroy.sh"
TMP_DIR="$(mktemp -d)"
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
    'runpodctl stop pod pod-id' \
    'sudo runpodctl stop pod pod-id' \
    'doas runpodctl stop pod pod-id' \
    'command runpodctl stop pod pod-id' \
    'builtin runpodctl stop pod pod-id' \
    'exec runpodctl stop pod pod-id' \
    'env A=1 runpodctl stop pod pod-id' \
    'env -S "runpodctl stop pod pod-id"' \
    'env --split-string="runpodctl stop pod pod-id"' \
    'nice runpodctl stop pod pod-id' \
    'ionice runpodctl stop pod pod-id' \
    'nohup runpodctl stop pod pod-id' \
    'stdbuf -oL runpodctl stop pod pod-id' \
    'time runpodctl stop pod pod-id' \
    'timeout 60 runpodctl stop pod pod-id' \
    'setsid runpodctl stop pod pod-id' \
    'xargs runpodctl stop pod pod-id' \
    'chronic runpodctl stop pod pod-id' \
    '/usr/bin/runpodctl stop pod pod-id' \
    'true ; runpodctl stop pod pod-id' \
    'true && runpodctl stop pod pod-id' \
    'false || runpodctl stop pod pod-id' \
    'printf x | runpodctl stop pod pod-id' \
    'true & runpodctl stop pod pod-id' \
    $'true\nrunpodctl stop pod pod-id' \
    $'echo runpodctl stop pod as data\nrunpodctl stop pod pod-id' \
    '(runpodctl stop pod pod-id)' \
    'echo "$(runpodctl stop pod pod-id)"' \
    'echo `runpodctl stop pod pod-id`' \
    "bash -c 'runpodctl stop pod pod-id'" \
    "bash -O extglob -lc 'runpodctl stop pod pod-id'" \
    "eval 'runpodctl stop pod pod-id'" \
    'aws ec2 stop-instances' \
    'aws ec2 terminate-instances' \
    'gcloud compute instances stop' \
    'gcloud compute instances delete' \
    'vastai destroy instance' \
    'vastai stop instance'; do
    assert_blocked "$command"
done

CUSTOM_HOOK="$TMP_DIR/gate-paid-compute-destroy-custom.sh"
sed "s@EXTRA_TEARDOWN_PATTERNS=()@EXTRA_TEARDOWN_PATTERNS=('gpupod[[:space:]]+(stop|remove|delete)')@" \
    "$HOOK" >"$CUSTOM_HOOK"
chmod +x "$CUSTOM_HOOK"
HOOK="$CUSTOM_HOOK"
assert_blocked 'gpupod remove instance-id'

for command in \
    'grep "runpodctl stop pod" notes.md' \
    'grep runpodctl stop pod notes.md' \
    'echo runpodctl stop pod pod-id' \
    'cat file-about-runpodctl-stop-pod.md' \
    'ls runpodctlfoo/' \
    'runpodctl list pod' \
    'aws ec2 describe-instances' \
    'gcloud compute instances list' \
    'vastai show instances'; do
    assert_allowed "$command"
done

for command in \
    'sudo -u runpodctl echo stop pod' \
    'env -u runpodctl echo stop pod' \
    'timeout --signal runpodctl 60 echo stop pod' \
    'xargs -I runpodctl echo stop pod' \
    'command -v runpodctl stop pod' \
    'timeout --help runpodctl stop pod'; do
    assert_allowed "$command"
done
