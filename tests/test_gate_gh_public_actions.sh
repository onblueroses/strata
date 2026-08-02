#!/usr/bin/env bash
# shellcheck disable=SC2016  # Command substitutions below are literal hook inputs.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="${ROOT_DIR}/hooks/gate-gh-public-actions.sh"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT
FAKE_BIN="$TMP_DIR/fake-bin"
PYTHON_MARKER="$TMP_DIR/python-started"
mkdir -p "$FAKE_BIN"
cat > "$FAKE_BIN/python3" <<'EOF'
#!/usr/bin/env bash
printf 'started\n' >> "${PYTHON_MARKER:?}"
printf 'none\n'
EOF
chmod +x "$FAKE_BIN/python3"

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

run_hook_with_fake_python() {
    local command="$1"

    jq -n --arg command "$command" '{tool_input: {command: $command}}' \
        | PATH="$FAKE_BIN:$PATH" PYTHON_MARKER="$PYTHON_MARKER" \
            STRATA_HOME="$TMP_DIR/strata" "$HOOK" >/dev/null 2>&1
}

assert_python_skipped() {
    local command="$1"

    : > "$PYTHON_MARKER"
    if ! run_hook_with_fake_python "$command"; then
        printf 'expected fast-path allow: %s\n' "$command" >&2
        exit 1
    fi
    if [[ -s $PYTHON_MARKER ]]; then
        printf 'expected Python parser to be skipped: %s\n' "$command" >&2
        exit 1
    fi
}

assert_python_started() {
    local command="$1"

    : > "$PYTHON_MARKER"
    if ! run_hook_with_fake_python "$command"; then
        printf 'expected fake parser allow: %s\n' "$command" >&2
        exit 1
    fi
    if [[ ! -s $PYTHON_MARKER ]]; then
        printf 'expected Python parser to start: %s\n' "$command" >&2
        exit 1
    fi
}

assert_blocked 'gh -R owner/repo issue create --title t --body b'
assert_blocked "'gh' issue create --title t --body b"
assert_blocked "bash -lc 'gh issue create --title t --body b'"
assert_blocked "bash -lc 'gh pr create --title t --body b'"
assert_blocked "bash -O extglob -lc 'gh issue create --title t --body b'"
assert_blocked "echo \"\$(gh issue create --title t --body b)\""
assert_blocked "echo \"\$(gh api repos/owner/repo -X POST)\""
assert_blocked "echo \"\$(gh api repos/owner/repo -f foo=bar)\""
assert_blocked "echo \"\$(bash -lc 'gh pr create --title t --body b')\""
assert_blocked "echo \`gh issue create --title t --body b\`"
assert_blocked "'g''h' issue create --title t --body b"
assert_blocked 'sudo gh issue create --title t --body b'
assert_blocked 'env X=1 gh issue create --title t --body b'
assert_blocked 'cd dir && gh issue create --title t --body b'
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
assert_python_started 'sudo gh issue list'
assert_python_started 'env X=1 gh issue list'
assert_python_started 'cd dir && gh issue list'
assert_python_started "'g''h' issue list"
assert_python_skipped 'echo "gh"'
assert_python_skipped "echo 'g''h'"
assert_python_skipped 'ghost && highlight file'
assert_python_skipped 'echo gh issue create'
assert_python_skipped 'grep gh README.md'

for command in \
    'sudo gh issue create --title t --body b' \
    'doas gh issue create --title t --body b' \
    'command gh issue create --title t --body b' \
    'builtin gh issue create --title t --body b' \
    'exec gh issue create --title t --body b' \
    'env A=1 gh issue create --title t --body b' \
    'env -S "gh issue create --title t --body b"' \
    'env --split-string="gh issue create --title t --body b"' \
    'nice gh issue create --title t --body b' \
    'ionice gh issue create --title t --body b' \
    'nohup gh issue create --title t --body b' \
    'stdbuf -oL gh issue create --title t --body b' \
    'time gh issue create --title t --body b' \
    'timeout 60 gh issue create --title t --body b' \
    'setsid gh issue create --title t --body b' \
    'xargs gh issue create --title t --body b' \
    'chronic gh issue create --title t --body b' \
    '/usr/bin/gh issue create --title t --body b' \
    'true ; gh issue create --title t --body b' \
    'true && gh issue create --title t --body b' \
    'false || gh issue create --title t --body b' \
    'printf x | gh issue create --title t --body b' \
    'true & gh issue create --title t --body b' \
    $'true\ngh issue create --title t --body b' \
    $'echo gh issue create as data\ngh issue create --title t --body b' \
    '(gh issue create --title t --body b)' \
    "eval 'gh issue create --title t --body b'"; do
    assert_blocked "$command"
done

for command in \
    'echo gh issue create --title t --body b' \
    'grep gh issue create README.md' \
    'grep "gh issue create" README.md' \
    'cat file-about-gh-issue-create.md' \
    'ls ghfoo/'; do
    assert_allowed "$command"
done

for command in \
    'sudo -u gh echo issue create' \
    'env -u gh echo issue create' \
    'timeout --signal gh 60 echo issue create' \
    'xargs -I gh echo issue create' \
    'command -v gh issue create' \
    'timeout --help gh issue create'; do
    assert_allowed "$command"
done
