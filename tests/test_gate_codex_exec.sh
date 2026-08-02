#!/usr/bin/env bash
# shellcheck disable=SC2016  # Command substitutions below are literal hook inputs.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="${ROOT_DIR}/hooks/gate-codex-exec.sh"
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

run_hook_with_fake_python() {
    local command="$1"

    jq -n --arg command "$command" '{tool_input: {command: $command}}' \
        | PATH="$FAKE_BIN:$PATH" PYTHON_MARKER="$PYTHON_MARKER" \
            "$HOOK" >/dev/null 2>&1
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

assert_blocked 'codex exec "prompt --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check"'
assert_blocked 'codex -C /tmp exec prompt'
assert_blocked "'co''dex' 'ex''ec' prompt"
assert_allowed 'codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check "prompt"'
assert_blocked "codex review --uncommitted \`codex exec \"prompt\"\`"
assert_allowed 'codex review --uncommitted'
assert_blocked 'codex exec "unterminated'
assert_allowed 'printf "unterminated'
assert_python_started 'sudo codex exec prompt'
assert_python_started 'codex -C /tmp exec prompt'
assert_python_started "'co''dex' 'ex''ec' prompt"
assert_python_skipped 'echo hello world'
assert_python_skipped 'echo codextra executor'
assert_python_skipped 'echo codex exec prompt'
assert_python_skipped 'grep codex exec README.md'

for command in \
    'codex exec "prompt"' \
    'sudo codex exec x' \
    'doas codex exec x' \
    'command codex exec x' \
    'builtin codex exec x' \
    'exec codex exec x' \
    'env A=1 codex exec y' \
    'env -S "codex exec y"' \
    'env --split-string="codex exec y"' \
    'nice codex exec x' \
    'ionice codex exec x' \
    'nohup codex exec x' \
    'stdbuf -oL codex exec x' \
    'time codex exec x' \
    'timeout 60 codex exec v' \
    'setsid codex exec x' \
    'xargs codex exec x' \
    'chronic codex exec x' \
    '/usr/bin/codex exec z' \
    'true ; codex exec x' \
    'true && codex exec x' \
    'false || codex exec x' \
    'printf x | codex exec x' \
    'true & codex exec x' \
    $'true\ncodex exec x' \
    $'echo codex exec as data\ncodex exec x' \
    '(codex exec x)' \
    'echo "$(codex exec x)"' \
    'echo `codex exec x`' \
    "bash -c 'codex exec x'" \
    "eval 'codex exec x'"; do
    assert_blocked "$command"
done

for command in \
    'echo codex exec prompt' \
    'grep codex exec README.md' \
    'grep "codex exec" README.md' \
    'cat file-about-codex-exec.md' \
    'ls codexfoo/'; do
    assert_allowed "$command"
done

for command in \
    'sudo -u codex echo exec' \
    'env -u codex echo exec' \
    'timeout --signal codex 60 echo exec' \
    'xargs -I codex echo exec' \
    'command -v codex exec' \
    'timeout --help codex exec'; do
    assert_allowed "$command"
done
