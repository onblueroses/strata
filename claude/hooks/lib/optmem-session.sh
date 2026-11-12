# Shared by optmem-wake.sh and optmem-core.sh, the two SessionStart hooks that read OptMem.
# Sourced, never run. Everything here prints a hook payload or sets a variable; nothing exits,
# so each hook keeps its own exit-0-on-every-path ending.

# OPTMEM_MEMO_PATH exists for the tests (and matches the Codex start hook's override);
# OPTMEM_MEMO is the install setting (config/hooks-runtime.env.example).
memo=${OPTMEM_MEMO_PATH:-${OPTMEM_MEMO:-${HOME:-}/.local/bin/memo}}

# Text the caller wants in front of every payload (the wake hook's session-scope header).
context_prefix=""

emit_context() {
    /usr/bin/jq -cn --arg context "$context_prefix$1" \
        '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$context}}'
}

# A harness may cap what one SessionStart hook injects and save a longer payload to a file
# behind a preview. Set OPTMEM_INJECTION_BUDGET (config/hooks-runtime.env.example) to your
# harness's documented limit to get a warning in front of an oversize payload; unset, no check.
# Withholding memory would be worse, so an oversize payload still goes out whole.
INJECTION_BUDGET=${OPTMEM_INJECTION_BUDGET:-}

emit_payload() {  # emit_payload <payload> <oversize warning>
    if [[ -n $INJECTION_BUDGET ]] && (( ${#1} + ${#context_prefix} > INJECTION_BUDGET )); then
        emit_context "$2
$1"
    else
        emit_context "$1"
    fi
}

# optmem_preflight <LABEL> <memo arguments as a person would type them>
# Resolves the store and checks that memo and the store are usable. On success sets
# memory_store, memory_store_shell and manual_command and returns 0. On failure prints the
# failure payload, sets preflight_reason, and returns 1.
optmem_preflight() {
    local label=$1 by_hand=$2
    preflight_reason=""
    if [[ -n "${MEMORY_DIR:-}" ]]; then
        memory_store=$MEMORY_DIR
    elif [[ -n "${HOME:-}" ]]; then
        memory_store=$HOME/.optmem/memory
    else
        preflight_reason=no-store-path
        emit_context "OPTMEM $label FAILURE: neither MEMORY_DIR nor HOME is set, so the memory store cannot be resolved. Run by hand after setting one: $memo $by_hand"
        return 1
    fi
    printf -v memory_store_shell '%q' "$memory_store"
    manual_command="env MEMORY_DIR=$memory_store_shell $memo $by_hand"
    if [[ ! -x "$memo" ]]; then
        preflight_reason=no-memo
        emit_context "OPTMEM $label FAILURE: the memo CLI is missing or not executable at $memo. Run by hand: $manual_command"
        return 1
    fi
    if [[ ! -d "$memory_store" || ! -f "$memory_store/LOG.txt" || ! -d "$memory_store/TREE" ]]; then
        preflight_reason=no-store
        emit_context "OPTMEM $label FAILURE: the memory store is missing or incomplete at $memory_store; expected LOG.txt and TREE/. Run by hand: $manual_command"
        return 1
    fi
    return 0
}
