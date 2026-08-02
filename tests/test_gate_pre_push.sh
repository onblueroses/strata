#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$ROOT_DIR/hooks/gate-pre-push.sh"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

STATE_DIR="$TMP_DIR/state"
STRATA_HOME="$TMP_DIR/strata-home"
UNRELATED_DIR="$TMP_DIR/unrelated"
FAKE_BIN="$TMP_DIR/bin"
mkdir -p "$STATE_DIR" "$STRATA_HOME/config" "$UNRELATED_DIR" "$FAKE_BIN"

printf '%s\n' 'fixture-private-marker' > "$STRATA_HOME/config/private-tokens.txt"
printf '%s\n' '#!/usr/bin/env bash' "printf '%s\\n' false" > "$FAKE_BIN/gh"
chmod +x "$FAKE_BIN/gh"

init_repo() {
    local repo="$1"
    local content="$2"

    git init -q "$repo"
    printf '%s\n' "$content" > "$repo/fixture.txt"
    git -C "$repo" add fixture.txt
    git -C "$repo" -c user.name=Fixture -c user.email=fixture@example.invalid \
        commit -qm 'fixture commit'
}

FLAGGED_REPO="$TMP_DIR/flagged"
CLEAN_REPO="$TMP_DIR/clean"
init_repo "$FLAGGED_REPO" 'fixture-private-marker'
init_repo "$CLEAN_REPO" 'shareable fixture content'

LAST_STATUS=0
LAST_OUTPUT="$TMP_DIR/hook-output"
run_hook() {
    local command="$1"
    local session_id="$2"
    local hook_cwd="$3"

    set +e
    (
        cd "$hook_cwd"
        jq -n --arg command "$command" --arg session "$session_id" \
            '{tool_input: {command: $command}, session_id: $session}' \
            | env PATH="$FAKE_BIN:$PATH" \
                STRATA_HOME="$STRATA_HOME" \
                STATE_DIR="$STATE_DIR" \
                KB_DIR="$TMP_DIR/knowledge-base" \
                bash "$HOOK"
    ) > "$LAST_OUTPUT" 2>&1
    LAST_STATUS=$?
    set -e
}

failures=0
record_status() {
    local label="$1"
    local expected="$2"

    if [ "$LAST_STATUS" -ne "$expected" ]; then
        failures=$((failures + 1))
    fi
    printf '%s | expected %s | actual %s\n' "$label" "$expected" "$LAST_STATUS"
}

assert_output() {
    local pattern="$1"
    local label="$2"

    if ! grep -qF -- "$pattern" "$LAST_OUTPUT"; then
        printf 'missing output for %s: %s\n' "$label" "$pattern" >&2
        failures=$((failures + 1))
    fi
}

printf '%s\n' 'push form                          | expected   | actual'
printf '%s\n' '-----------------------------------+------------+-------'

flagged_commands=(
    'git push'
    'git push origin main'
    'git push --force-with-lease'
    "git -C $FLAGGED_REPO push"
    "cd $FLAGGED_REPO && git push"
    'git -c user.name=x push'
    '/usr/bin/git push'
    'sudo git push'
    'env git push'
    'env GIT_TRACE=1 git push'
    'timeout 60 git push'
    'nohup git push'
)
flagged_cwds=(
    "$FLAGGED_REPO"
    "$FLAGGED_REPO"
    "$FLAGGED_REPO"
    "$UNRELATED_DIR"
    "$UNRELATED_DIR"
    "$FLAGGED_REPO"
    "$FLAGGED_REPO"
    "$FLAGGED_REPO"
    "$FLAGGED_REPO"
    "$FLAGGED_REPO"
    "$FLAGGED_REPO"
    "$FLAGGED_REPO"
)

for i in "${!flagged_commands[@]}"; do
    # Four prefix characters plus four digits match the hook's eight-character session key.
    printf -v session_id 'flag%04d' "$((i + 1))"
    : > "$STATE_DIR/.verify-passed-$session_id"
    run_hook "${flagged_commands[$i]}" "$session_id" "${flagged_cwds[$i]}"
    record_status "${flagged_commands[$i]}" 2
done

clean_commands=(
    'git push'
    'git push origin main'
    "git -C $CLEAN_REPO push"
    "cd $CLEAN_REPO && git push"
    'git -c user.name=x push'
    'git push --force-with-lease'
)
clean_cwds=(
    "$CLEAN_REPO"
    "$CLEAN_REPO"
    "$UNRELATED_DIR"
    "$UNRELATED_DIR"
    "$CLEAN_REPO"
    "$CLEAN_REPO"
)

for i in "${!clean_commands[@]}"; do
    # Five prefix characters plus three digits match the hook's eight-character session key.
    printf -v session_id 'clean%03d' "$((i + 1))"
    : > "$STATE_DIR/.verify-passed-$session_id"
    run_hook "${clean_commands[$i]}" "$session_id" "${clean_cwds[$i]}"
    record_status "clean: ${clean_commands[$i]}" 0
done

wrapper_commands=(
    'doas git push'
    'command git push'
    'builtin git push'
    'exec git push'
    "env -S 'git push'"
    "env --split-string 'git push'"
    'nice git push'
    'ionice git push'
    'stdbuf git push'
    'time git push'
    'setsid git push'
    'xargs git push'
    'chronic git push'
)
for i in "${!wrapper_commands[@]}"; do
    # Four prefix characters plus four digits match the hook's eight-character session key.
    printf -v session_id 'wrap%04d' "$((i + 1))"
    : > "$STATE_DIR/.verify-passed-$session_id"
    run_hook "${wrapper_commands[$i]}" "$session_id" "$FLAGGED_REPO"
    record_status "${wrapper_commands[$i]}" 2
done

resolved_wrapper_commands=(
    "/usr/bin/git -C $FLAGGED_REPO push"
    "sudo git -C $FLAGGED_REPO push"
    "cd $FLAGGED_REPO && env git push"
    "env GIT_TRACE=1 git -c user.name=x -C $FLAGGED_REPO push"
)
for i in "${!resolved_wrapper_commands[@]}"; do
    # Four prefix characters plus four digits match the hook's eight-character session key.
    printf -v session_id 'path%04d' "$((i + 1))"
    : > "$STATE_DIR/.verify-passed-$session_id"
    run_hook "${resolved_wrapper_commands[$i]}" "$session_id" "$UNRELATED_DIR"
    record_status "resolved: ${resolved_wrapper_commands[$i]}" 2
done

: > "$STATE_DIR/.verify-passed-assign01"
run_hook "repo=$FLAGGED_REPO; git -C \"\$repo\" push" 'assign01' "$UNRELATED_DIR"
record_status 'same-command literal repository assignment' 2

: > "$STATE_DIR/.verify-passed-assign02"
run_hook "repo=$CLEAN_REPO; git -C \"\$repo\" push" 'assign02' "$UNRELATED_DIR"
record_status 'same-command literal clean repository assignment' 0

: > "$STATE_DIR/.verify-passed-dynamic1"
run_hook 'git -C "$repo" push' 'dynamic1' "$UNRELATED_DIR"
record_status 'unresolved repository variable fails closed' 2
assert_output 'could not resolve the repository target' 'unresolved repository variable'

: > "$STATE_DIR/.verify-passed-shell001"
run_hook "bash -lc 'git -C $FLAGGED_REPO push'" 'shell001' "$UNRELATED_DIR"
record_status 'combined shell flags preserve push target' 2

: > "$STATE_DIR/.verify-passed-shell002"
run_hook "bash --login -c 'git -C $FLAGGED_REPO push'" 'shell002' "$UNRELATED_DIR"
record_status 'long shell option preserves push target' 2

negative_commands=(
    'echo git push'
    'echo /usr/bin/git push'
    'grep "git push" README.md'
    'git status'
    'git pull'
    'sudo git pull'
    'git -c push.default=current status'
    'timeout 60 echo git push'
    'gitpush'
    'printf git push'
)
for i in "${!negative_commands[@]}"; do
    # Four prefix characters plus four digits match the hook's eight-character session key.
    printf -v session_id 'none%04d' "$((i + 1))"
    : > "$STATE_DIR/.verify-passed-$session_id"
    run_hook "${negative_commands[$i]}" "$session_id" "$FLAGGED_REPO"
    record_status "no push: ${negative_commands[$i]}" 0
done

: > "$STATE_DIR/.verify-passed-unknown1"
run_hook 'unknown-launcher git push' 'unknown1' "$FLAGGED_REPO"
record_status 'unrecognized plausible wrapper' 2
: > "$STATE_DIR/.verify-passed-unknown2"
run_hook "awk 'BEGIN { system(\"git push\") }'" 'unknown2' "$FLAGGED_REPO"
record_status 'unrecognized embedded launcher' 2
: > "$STATE_DIR/.verify-passed-malform1"
run_hook 'git push "unterminated' 'malform1' "$FLAGGED_REPO"
record_status 'ambiguous shell tokenization' 2
: > "$STATE_DIR/.verify-passed-notpush2"
run_hook "git push && printf '%s' '-C $CLEAN_REPO'" 'notpush2' "$FLAGGED_REPO"
record_status 'later unrelated -C argument' 2

: > "$STATE_DIR/.verify-passed-multi001"
run_hook "git -C $CLEAN_REPO push && git -C $FLAGGED_REPO push" 'multi001' "$UNRELATED_DIR"
record_status 'compound push: clean then flagged' 2
run_hook "git -C $CLEAN_REPO push && git -C $FLAGGED_REPO push" 'multi001' "$UNRELATED_DIR"
record_status 'compound same-HEAD re-push' 0
: > "$STATE_DIR/.verify-passed-multi002"
run_hook "git -C $FLAGGED_REPO push && git -C $CLEAN_REPO push" 'multi002' "$UNRELATED_DIR"
record_status 'compound push: flagged then clean' 2

# Use two clones with byte-identical outgoing commits so their HEAD object IDs are equal.
# That makes a session-only surfaced marker reproduce the cross-repository collision.
BASE_REPO="$TMP_DIR/base"
REPO_A="$TMP_DIR/repo-a"
REPO_B="$TMP_DIR/repo-b"
init_repo "$BASE_REPO" 'shared base'
git clone -q "$BASE_REPO" "$REPO_A"
git clone -q "$BASE_REPO" "$REPO_B"
for repo in "$REPO_A" "$REPO_B"; do
    printf '%s\n' 'same outgoing content' > "$repo/outgoing.txt"
    git -C "$repo" add outgoing.txt
    # The calendar value carries no policy meaning; sharing it makes both commit IDs equal.
    GIT_AUTHOR_DATE='2026-01-01T00:00:00Z' \
    GIT_COMMITTER_DATE='2026-01-01T00:00:00Z' \
        git -C "$repo" -c user.name=Fixture -c user.email=fixture@example.invalid \
            commit -qm 'identical outgoing commit'
done

HEAD_A="$(git -C "$REPO_A" rev-parse HEAD)"
HEAD_B="$(git -C "$REPO_B" rev-parse HEAD)"
if [ "$HEAD_A" != "$HEAD_B" ]; then
    printf '%s\n' 'fixture error: two-repository HEADs differ' >&2
    exit 1
fi

run_hook 'git push' 'tworepos' "$REPO_A"
record_status 'repo A first push' 2
run_hook 'git push' 'tworepos' "$REPO_A"
record_status 'repo A same-HEAD re-push' 0
run_hook 'git push' 'tworepos' "$REPO_B"
record_status 'repo B first push' 2

# Removing the install-local denylist must surface a configuration decision, while
# the universal credential matcher continues to run independently.
mv "$STRATA_HOME/config/private-tokens.txt" "$STRATA_HOME/config/private-tokens.saved"
: > "$STATE_DIR/.verify-passed-nodeny01"
run_hook "git -C $CLEAN_REPO push" 'nodeny01' "$UNRELATED_DIR"
record_status 'public repo without denylist' 2
assert_output 'no denylist configured; private-identifier scanning is off' 'missing denylist'
run_hook "git -C $CLEAN_REPO push" 'nodeny01' "$UNRELATED_DIR"
record_status 'same-HEAD no-denylist re-push' 0

SECRET_REPO="$TMP_DIR/secret"
git init -q "$SECRET_REPO"
# The matcher defines twenty characters as the minimum provider-token payload.
SECRET_VALUE="sk-$(printf 'a%.0s' {1..20})"
printf '%s\n' "$SECRET_VALUE" > "$SECRET_REPO/credential.txt"
git -C "$SECRET_REPO" add credential.txt
git -C "$SECRET_REPO" -c user.name=Fixture -c user.email=fixture@example.invalid \
    commit -qm 'credential fixture'
: > "$STATE_DIR/.verify-passed-secret01"
run_hook "git -C $SECRET_REPO push" 'secret01' "$UNRELATED_DIR"
record_status 'secret scan without denylist' 2
assert_output '[SECRET] credential-shaped string' 'secret scan without denylist'

if [ "$failures" -ne 0 ]; then
    printf '%s\n' "$failures gate-pre-push assertion(s) failed" >&2
    exit 1
fi
