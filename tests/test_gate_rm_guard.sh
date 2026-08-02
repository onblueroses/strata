#!/usr/bin/env bash
# Differential regression coverage for hooks/gate-rm-guard.sh.
# Commands are passed to the hook as JSON and are never executed by this test.
set -euo pipefail

SCRIPT_DIR="${BASH_SOURCE[0]%/*}"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd -P)"
HOOK="$ROOT_DIR/hooks/gate-rm-guard.sh"

for dependency in bash jq python3 git; do
    if ! command -v "$dependency" >/dev/null 2>&1; then
        printf 'missing test dependency: %s\n' "$dependency" >&2
        exit 1
    fi
done

JQ_BIN="$(command -v jq)"
TEMP_ROOT="$(mktemp -d)"
EMPTY_PATH="$TEMP_ROOT/empty-path"
mkdir -p "$EMPTY_PATH" "$TEMP_ROOT/home" "$TEMP_ROOT/trash"
trap 'rm -rf "$TEMP_ROOT"' EXIT

LAST_RC=0
LAST_OUTPUT=""
PASS_COUNT=0
FAIL_COUNT=0

run_hook() {
    local command="$1"
    local payload
    payload="$($JQ_BIN -n --arg command "$command" '{tool_input:{command:$command}}')"

    set +e
    LAST_OUTPUT="$(
        printf '%s' "$payload" \
            | HOME="$TEMP_ROOT/home" STRATA_TRASH_DIR="$TEMP_ROOT/trash" \
                bash "$HOOK" 2>&1
    )"
    LAST_RC=$?
    set -e
}

run_raw_payload() {
    local payload="$1"

    set +e
    LAST_OUTPUT="$(
        printf '%s' "$payload" \
            | HOME="$TEMP_ROOT/home" STRATA_TRASH_DIR="$TEMP_ROOT/trash" \
                bash "$HOOK" 2>&1
    )"
    LAST_RC=$?
    set -e
}

pass() {
    PASS_COUNT=$((PASS_COUNT + 1))
    printf 'ok - %s\n' "$1"
}

fail() {
    FAIL_COUNT=$((FAIL_COUNT + 1))
    printf 'not ok - %s\n' "$1" >&2
    printf '  rc: %s\n' "$LAST_RC" >&2
    if [[ -n $LAST_OUTPUT ]]; then
        printf '  output: %s\n' "$LAST_OUTPUT" >&2
    fi
}

assert_allowed() {
    local label="$1"
    local command="$2"
    run_hook "$command"
    if [[ $LAST_RC -eq 0 ]]; then
        pass "$label"
    else
        fail "$label (expected ALLOW: $command)"
    fi
}

assert_blocked() {
    local label="$1"
    local command="$2"
    run_hook "$command"
    if [[ $LAST_RC -eq 2 && $LAST_OUTPUT == *"BLOCKED"* ]]; then
        pass "$label"
    else
        fail "$label (expected BLOCK: $command)"
    fi
}

printf '%s\n' '== required bypass regressions =='
assert_blocked 'sudo wrapper' 'sudo rm -rf "$HOME/important"'
assert_blocked 'git rm' 'git rm important.py'
assert_blocked 'find -exec rm' 'find . -name "*.md" -exec rm {} \;'
assert_blocked 'sh -c recursion' 'sh -c "rm -rf $HOME/x"'
assert_blocked 'bash -c recursion' 'bash -c "rm -rf ~/x"'
assert_blocked 'bash -lc recursion' 'bash -lc "rm -rf $HOME/x"'
assert_blocked 'sh -lc recursion' 'sh -lc "rm -rf $HOME/x"'
assert_blocked 'bash -xc recursion' 'bash -xc "rm -rf $HOME/x"'
assert_blocked 'bash -ec recursion' 'bash -ec "rm -rf $HOME/x"'
assert_blocked 'bash -lxc recursion' 'bash -lxc "rm -rf $HOME/x"'
assert_blocked 'bash shopt option before combined command flags' \
    'bash -O extglob -lc "rm -rf $HOME/x"'
assert_blocked 'bash long login option before command' \
    'bash --login -c "rm -rf $HOME/x"'
assert_blocked 'bash attached long command option' \
    'bash --command="rm -rf $HOME/x"'
assert_blocked 'eval quoted command' 'eval "rm -rf ~/x"'
assert_blocked 'eval operand concatenation' 'eval rm -rf ~/x'
assert_blocked 'backtick substitution' 'echo `rm -rf ~/x`'
assert_blocked 'timeout wrapper' 'timeout 5 rm -rf ~/x'
assert_blocked 'xargs unknown operands' 'xargs rm < list.txt'
assert_blocked 'nohup wrapper' 'nohup rm -rf ~/x'
assert_blocked 'env wrapper' 'env rm -rf ~/x'

printf '%s\n' '== destructive verbs =='
assert_blocked 'shred protected target' 'shred "$HOME/important"'
assert_blocked 'truncate protected target' 'truncate -s 0 "$HOME/important"'
assert_blocked 'unlink protected target' 'unlink "$HOME/important"'
assert_blocked 'rmdir protected target' 'rmdir "$HOME/important"'
assert_blocked 'find -delete protected root' 'find "$HOME/important" -delete'

printf '%s\n' '== required positive controls =='
assert_allowed 'docker run --rm remains an option' 'docker run --rm image'
assert_blocked 'bare rm against a protected target' 'rm -rf "$HOME/project/important"'
assert_blocked 'mixed safe and protected operands' 'rm -rf /tmp/scratch "$HOME/project/important"'

printf '%s\n' '== safe target vocabulary =='
assert_blocked 'temporary root with a trailing slash is protected' 'rm -rf /tmp/'
assert_blocked 'var temporary root with a trailing slash is protected' 'rm -rf /var/tmp/'
assert_blocked 'wrapped var temporary root is protected' 'sudo rm -rf /var/tmp/'
assert_blocked 'normalized temporary root is protected' 'rm -rf /tmp/.'
assert_allowed 'temporary file' 'rm -rf /tmp/scratch'
assert_allowed 'var temporary file' 'rm -rf /var/tmp/scratch'
assert_allowed 'normalized temporary child remains safe' 'rm -rf /tmp//scratch/'
assert_allowed 'null device' 'rm -f /dev/null'
assert_allowed 'bytecode suffix' 'rm module.pyc'
assert_allowed 'object suffix' 'rm module.o'
assert_allowed 'class suffix' 'rm Module.class'
assert_allowed 'relative bytecode directory' 'rm -rf __pycache__'
assert_allowed 'relative dependency directory' 'rm -rf node_modules'
assert_allowed 'relative build directory' 'rm -rf build'
assert_allowed 'relative distribution directory' 'rm -rf dist'
assert_allowed 'relative target directory' 'rm -rf target'
assert_allowed 'cache component' 'rm -rf project/.cache/tool'
assert_blocked 'safe suffix cannot mask protected neighbor' 'rm module.pyc "$HOME/important"'
assert_blocked 'safe directory cannot mask protected neighbor' 'rm -rf build "$HOME/important"'
assert_blocked 'path traversal escapes a safe prefix' 'rm -rf /tmp/work/../../workspace/project'

printf '%s\n' '== wrappers and command position =='
assert_allowed 'sudo wrapper with safe target' 'sudo rm -rf /tmp/scratch'
assert_allowed 'timeout wrapper with safe target' 'timeout 5 rm -rf /tmp/scratch'
assert_allowed 'nohup wrapper with safe target' 'nohup rm -rf /tmp/scratch'
assert_allowed 'env wrapper with safe target' 'env rm -rf /tmp/scratch'
assert_allowed 'env assignment before safe rm' 'env MODE=test rm -rf /tmp/scratch'
assert_blocked 'sudo option value cannot hide rm' 'sudo -u root rm -rf "$HOME/important"'
assert_blocked 'doas option value cannot hide rm' 'doas -u root rm -rf "$HOME/important"'
assert_blocked 'env option value cannot hide rm' 'env -u MODE rm -rf "$HOME/important"'
assert_blocked 'stdbuf option value cannot hide rm' 'stdbuf -o L rm -rf "$HOME/important"'
assert_blocked 'time option value cannot hide rm' 'time -f format rm -rf "$HOME/important"'
assert_blocked 'timeout option value cannot hide rm' \
    'timeout --signal KILL 5 rm -rf "$HOME/important"'
assert_blocked 'xargs replacement option cannot hide rm' 'xargs -I {} rm {} < list.txt'
assert_blocked 'xargs explicit safe operand cannot hide stdin target' \
    'printf "%s\n" "$HOME/important" | xargs rm /tmp/harmless'
assert_allowed 'xargs literal temporary stdin target remains safe' \
    'echo /tmp/scratch | xargs rm -rf'
assert_allowed 'xargs printf temporary stdin target remains safe' \
    'printf "%s\n" /tmp/scratch | xargs rm -rf'
assert_allowed 'xargs safe replacement target remains safe' \
    'echo /tmp/scratch | xargs -I {} rm -rf {}'
assert_blocked 'env split-string cannot hide rm' 'env -S "rm -rf $HOME/important"'
assert_blocked 'attached env split-string cannot hide rm' \
    'env --split-string="rm -rf $HOME/important"'
assert_blocked 'escaped rm is still recognized' '\rm -rf "$HOME/important"'
assert_blocked 'command wrapper is still recognized' 'command rm -rf "$HOME/important"'
assert_allowed 'command inspection does not execute rm' 'command -v rm'
assert_allowed 'wrapper help does not execute rm' 'timeout --help rm'
assert_allowed 'rm in prose is inert' 'echo rm "$HOME/important"'
assert_allowed 'find syntax in prose is inert' 'echo -exec rm {}'
assert_allowed 'package manager remove is inert' 'apt-get remove package'
assert_allowed 'package manager uninstall is inert' 'npm uninstall package'

printf '%s\n' '== git and find target analysis =='
assert_allowed 'git rm with a known temp target' 'git rm /tmp/scratch'
assert_blocked 'git global option cannot hide rm' 'git -C repo rm important.py'
assert_allowed 'find -delete with a temp root' 'find /tmp/work -type f -delete'
assert_allowed 'find -exec rm with a temp root' 'find /tmp/work -type f -exec rm {} \;'
assert_allowed 'find -exec wrapped rm with a temp root' \
    'find /tmp/work -type f -exec sudo rm {} \;'
assert_blocked 'find symlink traversal remains ambiguous' 'find -L /tmp/link -delete'
assert_blocked 'find -exec wrapper cannot hide rm' \
    'find "$HOME/project" -exec sudo rm {} \;'
assert_blocked 'find -exec shell cannot hide rm' \
    'find "$HOME/project" -exec sh -c "rm -rf $HOME/important" \;'
assert_blocked 'every find -exec action contributes to the verdict' \
    'find /tmp/work -exec rm {} \; -exec rm "$HOME/important" \;'
assert_blocked 'find name text cannot sanctify protected root' \
    'find "$HOME/project" -name /tmp/scratch -exec rm {} \;'
assert_blocked 'find default cwd is ambiguous' 'find -type f -delete'

printf '%s\n' '== literal assignment resolution =='
assert_allowed 'plain literal assignment resolves' 'T=/tmp/safe; rm -rf "$T"'
assert_allowed 'braced literal reference resolves' 'T=/tmp/safe; rm -rf "${T}"'
assert_allowed 'sequenced literal assignment resolves' 'T=/tmp/safe && rm -rf "$T"'
assert_blocked 'literal protected assignment blocks' 'T="$HOME/project"; rm -rf "$T"'
assert_blocked 'reference before assignment stays unknown' 'rm -rf "$T"; T=/tmp/safe'
assert_blocked 'command substitution assignment stays unknown' 'T=$(mktemp -d); rm -rf "$T"'
assert_blocked 'parameter default assignment stays unknown' 'T=${SCRATCH:-/tmp/safe}; rm -rf "$T"'
assert_blocked 'arithmetic assignment stays unknown' 'T=/tmp/safe$((1+1)); rm -rf "$T"'
assert_blocked 'glob assignment stays unknown' 'T=/tmp/safe/*; rm -rf "$T"'
assert_blocked 'empty assignment stays unknown' 'T=; rm -rf "$T/"'
assert_blocked 'conflicting assignments poison the name' \
    'T=/tmp/safe; T="$HOME/project"; rm -rf "$T"'
assert_blocked 'word splitting in a value stays unknown' \
    'T="/tmp/safe $HOME/project"; rm -rf $T'
assert_blocked 'custom IFS disables literal resolution' \
    'IFS=:; T=/tmp/safe:$HOME/project; rm -rf $T'
assert_blocked 'traversal inside a value blocks' \
    'T=../workspace/project; rm -rf /tmp/$T'
assert_blocked 'quoted tilde assignment stays literal and protected' \
    'T="~/.cache/tool"; rm -rf "$T"'
assert_blocked 'unknown variable cannot borrow a safe suffix' 'rm -rf "$UNKNOWN/.cache/tool"'

printf '%s\n' '== assignment mutation and control flow =='
assert_blocked 'command-prefix assignment has no later scope' \
    'T=/tmp/safe env; rm -rf "$T/workspace"'
assert_blocked 'subshell assignment has no later scope' \
    '(T=/tmp/safe); rm -rf "$T/workspace"'
assert_blocked 'assignment-looking prose is ignored' \
    'echo "T=/tmp/safe"; rm -rf "$T/workspace"'
assert_blocked 'backgrounded assignment has no parent scope' \
    'T=/tmp/safe & rm -rf "$T/workspace"'
assert_blocked 'conditional assignment stays unknown' \
    'false && T=/tmp/safe; rm -rf "$T/workspace"'
assert_blocked 'unset poisons a tracked name' \
    'T=/tmp/safe; unset T; rm -rf "$T/workspace"'
assert_blocked 'read poisons a tracked name' \
    'T=/tmp/safe; read T; rm -rf "$T/workspace"'
assert_blocked 'export assignment is not a bare assignment segment' \
    'export T=/tmp/safe; rm -rf "$T/workspace"'
assert_blocked 'source wipes tracked assignments' \
    'T=/tmp/safe; source settings.sh; rm -rf "$T/workspace"'
assert_blocked 'printf -v poisons a tracked name' \
    'T=/tmp/safe; printf -v T "%s" "$HOME/project"; rm -rf "$T"'
assert_blocked 'read subscript writes through to the scalar base' \
    'T=/tmp/safe; read "T[0]" <<< "$HOME/important"; rm -rf "$T"'
assert_blocked 'printf subscript writes through to the scalar base' \
    'T=/tmp/safe; printf -v "T[0]" %s "$HOME/important"; rm -rf "$T"'
assert_allowed 'literal-safe read subscript updates the scalar base' \
    'T=/tmp/safe; read "T[0]" <<< "/tmp/other"; rm -rf "$T"'
assert_blocked 'read options keep a subscripted target unresolved' \
    'T=/tmp/safe; read -n 1 "T[0]" <<< "/tmp/other"; rm -rf "$T"'
assert_blocked 'mapfile subscript leaves the scalar base unresolved' \
    'T=/tmp/safe; mapfile "T[0]" < values; rm -rf "$T"'
assert_blocked 'readarray subscript leaves the scalar base unresolved' \
    'T=/tmp/safe; readarray "T[0]" < values; rm -rf "$T"'
assert_allowed 'mapfile callback text is not an assignment target' \
    'T=/tmp/safe; mapfile -C "T[0]" -c 1 ITEMS < values; rm -rf "$T"'
assert_blocked 'trap wipes tracked assignments' \
    'trap "unset T" DEBUG; T=/tmp/safe; rm -rf "$T/workspace"'
assert_blocked 'nameref wipes tracked assignments' \
    'T=/tmp/safe; declare -n R=T; R="$HOME/project"; rm -rf "$T"'
assert_blocked 'subscript mutation poisons base name' \
    'T=/tmp/safe; T[0]="$HOME/project"; rm -rf "$T"'
assert_allowed 'literal-safe subscript assignment updates the scalar base' \
    'T=/workspace/project; T[0]=/tmp/safe; rm -rf "$T"'
assert_allowed 'subscripted read consults the scalar base state' \
    'T=/tmp/safe; rm -rf "${T[0]}"'
assert_blocked 'subscripted protected read consults the scalar base state' \
    'T=/workspace/project; rm -rf "${T[0]}"'
assert_blocked 'dynamic subscript read stays unresolved' \
    'T=/tmp/safe; rm -rf "${T[$INDEX]}"'
assert_blocked 'append mutation poisons base name' \
    'T=/tmp/safe; T+=/../workspace/project; rm -rf "$T"'
assert_blocked 'attached printf target wipes resolution' \
    'T=/tmp/safe; printf -vT "$HOME/project"; rm -rf "$T"'
assert_blocked 'alias wipes tracked assignments' \
    'T=/tmp/safe; alias x="T=$HOME/project"; rm -rf "$T/workspace"'
assert_blocked 'shopt alias mode wipes tracked assignments' \
    'T=/tmp/safe; shopt -s expand_aliases; rm -rf "$T/workspace"'
assert_allowed 'ordinary printf preserves resolution' \
    'T=/tmp/safe; printf "%s\n" working; rm -rf "$T"'
assert_allowed 'ordinary echo preserves resolution' \
    'T=/tmp/safe; echo working; rm -rf "$T"'

printf '%s\n' '== recursive parsing and ambiguity =='
assert_allowed 'eval of a safe command remains safe' 'eval "rm -rf /tmp/scratch"'
assert_allowed 'shell -c of a safe command remains safe' 'sh -c "rm -rf /tmp/scratch"'
assert_blocked 'eval unwraps ANSI-C quoted protected command' \
    "eval \$'rm -rf \"\$HOME/important\"'"
assert_allowed 'eval unwraps ANSI-C quoted safe command' \
    "eval \$'rm -rf /tmp/scratch'"
assert_blocked 'sh -c unwraps ANSI-C quoted protected command' \
    "sh -c \$'rm -rf \"\$HOME/important\"'"
assert_allowed 'sh -c unwraps ANSI-C quoted safe command' \
    "sh -c \$'rm -rf /tmp/scratch'"
assert_blocked 'bash -c unwraps ANSI-C quoted protected command' \
    "bash -c \$'rm -rf \"\$HOME/important\"'"
assert_allowed 'bash -c unwraps ANSI-C quoted safe command' \
    "bash -c \$'rm -rf /tmp/scratch'"
assert_blocked 'ANSI-C escapes in recursive text stay unresolved' \
    "eval \$'\\x72m -rf \"\$HOME/important\"'"
assert_allowed 'ANSI-C escapes outside recursion remain inert' \
    "printf %s \$'\\n'"
assert_blocked 'command substitution is analyzed' 'echo $(rm -rf "$HOME/important")'
assert_blocked 'every backtick substitution contributes to the verdict' \
    'echo `rm -rf /tmp/safe` `rm -rf "$HOME/important"`'
assert_blocked 'unbalanced quote fails toward block' 'rm -rf "/tmp/scratch'

assert_allowed 'shred options preserve a safe target' 'shred -n 1 /tmp/safe'

RECURSION_LIMIT=3
NESTED_COMMAND='rm -rf /tmp/scratch'
for ((level = 0; level < RECURSION_LIMIT; level++)); do
    printf -v QUOTED_COMMAND '%q' "$NESTED_COMMAND"
    NESTED_COMMAND="eval $QUOTED_COMMAND"
done
assert_allowed 'recursion at the required limit remains analyzable' "$NESTED_COMMAND"
printf -v QUOTED_COMMAND '%q' "$NESTED_COMMAND"
NESTED_COMMAND="eval $QUOTED_COMMAND"
assert_blocked 'recursion beyond the required limit fails toward block' "$NESTED_COMMAND"

HEREDOC_COMMAND="$(printf '%s\n' \
    "cat > /tmp/notes <<'EOF'" \
    'rm -rf "$HOME/important"' \
    'EOF')"
assert_allowed 'heredoc body is inert data' "$HEREDOC_COMMAND"

UNTERMINATED_HEREDOC="$(printf '%s\n' \
    "cat > /tmp/notes <<'EOF'" \
    'rm -rf "$HOME/important"')"
assert_blocked 'unterminated heredoc fails toward block' "$UNTERMINATED_HEREDOC"

printf '%s\n' '== threat-model boundaries =='
assert_allowed 'Python-hosted deletion is outside the Bash parser' \
    'python3 -c "import os; os.remove(\"file\")"'
assert_allowed 'Perl-hosted deletion is outside the Bash parser' \
    'perl -e "unlink q(file)"'
assert_allowed 'script-file contents are outside the Bash parser' 'bash cleanup.sh'
assert_allowed 'Makefile target contents are outside the Bash parser' 'make clean'

printf '%s\n' '== three-state input and dependency behavior =='
run_raw_payload ''
if [[ $LAST_RC -eq 0 && -z $LAST_OUTPUT ]]; then
    pass 'state 1: empty input passes silently'
else
    fail 'state 1: empty input must pass silently'
fi

run_raw_payload 'not json'
if [[ $LAST_RC -eq 0 && -z $LAST_OUTPUT ]]; then
    pass 'state 1: malformed JSON passes silently'
else
    fail 'state 1: malformed JSON must pass silently'
fi

run_raw_payload '{"tool_input":{}}'
if [[ $LAST_RC -eq 0 && -z $LAST_OUTPUT ]]; then
    pass 'state 1: JSON without a command passes silently'
else
    fail 'state 1: JSON without a command must pass silently'
fi

assert_allowed 'state 2: parsed harmless command passes' 'printf "%s\n" hello'
assert_blocked 'state 2: parsed destructive command blocks' 'rm -rf "$HOME/important"'

run_with_restricted_path() {
    local payload="$1"

    set +e
    LAST_OUTPUT="$(
        printf '%s' "$payload" \
            | PATH="$EMPTY_PATH" HOME="$TEMP_ROOT/home" /bin/bash "$HOOK" 2>&1
    )"
    LAST_RC=$?
    set -e
}

HARMLESS_PAYLOAD="$($JQ_BIN -n --arg command 'printf "%s\n" hello' '{tool_input:{command:$command}}')"
run_with_restricted_path "$HARMLESS_PAYLOAD"
if [[ $LAST_RC -eq 0 && -z $LAST_OUTPUT ]]; then
    pass 'state 3: harmless command passes silently when jq is missing'
else
    fail 'state 3: harmless command must pass silently when jq is missing'
fi

run_with_restricted_path ''
if [[ $LAST_RC -eq 0 && -z $LAST_OUTPUT ]]; then
    pass 'state 1: empty input passes silently when dependencies are missing'
else
    fail 'state 1: empty input must not depend on analyzer availability'
fi

run_with_restricted_path 'not json'
if [[ $LAST_RC -eq 0 && -z $LAST_OUTPUT ]]; then
    pass 'state 1: harmless malformed input passes without jq'
else
    fail 'state 1: harmless malformed input must pass without jq'
fi

FALLBACK_BLOCK_COMMANDS=(
    'rm -rf "$HOME/important"'
    'shred "$HOME/important"'
    'truncate -s 0 "$HOME/important"'
    'unlink "$HOME/important"'
    'rmdir "$HOME/important"'
    'find "$HOME/important" -delete'
    'find . -exec rm {} \;'
    'git rm important.py'
)
for fallback_command in "${FALLBACK_BLOCK_COMMANDS[@]}"; do
    FALLBACK_PAYLOAD="$($JQ_BIN -n --arg command "$fallback_command" '{tool_input:{command:$command}}')"
    run_with_restricted_path "$FALLBACK_PAYLOAD"
    if [[ $LAST_RC -eq 2 && $LAST_OUTPUT == *"jq"* && $LAST_OUTPUT == *"BLOCKED"* ]]; then
        pass "state 3: missing-jq fallback blocks $fallback_command"
    else
        fail "state 3: missing-jq fallback must block $fallback_command"
    fi
done

AMBIGUOUS_PROSE_PAYLOAD="$($JQ_BIN -n --arg command 'echo "rm -rf"' '{tool_input:{command:$command}}')"
run_with_restricted_path "$AMBIGUOUS_PROSE_PAYLOAD"
if [[ $LAST_RC -eq 2 && $LAST_OUTPUT == *"jq"* && $LAST_OUTPUT == *"BLOCKED"* ]]; then
    pass 'state 3: missing-jq fallback documents its conservative prose block'
else
    fail 'state 3: missing-jq fallback must block ambiguous destructive text'
fi

jq() { "$JQ_BIN" "$@"; }
export JQ_BIN
export -f jq
run_with_restricted_path "$HARMLESS_PAYLOAD"
if [[ $LAST_RC -eq 0 && -z $LAST_OUTPUT ]]; then
    pass 'state 3: harmless command passes silently when python3 is missing'
else
    fail 'state 3: harmless command must pass silently when python3 is missing'
fi

DESTRUCTIVE_PAYLOAD="$($JQ_BIN -n --arg command 'rm -rf "$HOME/important"' '{tool_input:{command:$command}}')"
run_with_restricted_path "$DESTRUCTIVE_PAYLOAD"
if [[ $LAST_RC -eq 2 && $LAST_OUTPUT == *"python3"* && $LAST_OUTPUT == *"BLOCKED"* ]]; then
    pass 'state 3: destructive command blocks and names missing python3'
else
    fail 'state 3: destructive command must block and name missing python3'
fi
unset -f jq

run_hook 'rm -rf "$HOME/important"'
if [[ $LAST_RC -eq 2 && $LAST_OUTPUT == *"$TEMP_ROOT/trash"* ]]; then
    pass 'deny message uses configured trash directory'
else
    fail 'deny message must use STRATA_TRASH_DIR'
fi

DEFAULT_TRASH_PAYLOAD="$($JQ_BIN -n --arg command 'rm -rf "$HOME/important"' '{tool_input:{command:$command}}')"
set +e
DEFAULT_TRASH_OUTPUT="$(
    unset STRATA_TRASH_DIR
    printf '%s' "$DEFAULT_TRASH_PAYLOAD" | HOME="$TEMP_ROOT/home" bash "$HOOK" 2>&1
)"
DEFAULT_TRASH_RC=$?
set -e
LAST_RC=$DEFAULT_TRASH_RC
LAST_OUTPUT=$DEFAULT_TRASH_OUTPUT
if [[ $DEFAULT_TRASH_RC -eq 2 && $DEFAULT_TRASH_OUTPUT == *"$TEMP_ROOT/home/.trash-agent"* ]]; then
    pass 'deny message defaults to the home trash directory'
else
    fail 'deny message must default to $HOME/.trash-agent'
fi

if ((FAIL_COUNT != 0)); then
    printf '\n%s test(s) failed; %s passed\n' "$FAIL_COUNT" "$PASS_COUNT" >&2
    exit 1
fi

printf '\ngate-rm-guard: %s assertions passed\n' "$PASS_COUNT"
