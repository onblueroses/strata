#!/usr/bin/env bash

set -u

memo="${OPTMEM_MEMO:-$HOME/.local/bin/memo}"
core_regex='^#[0-9]+ [0-9]{4}-[0-9]{2}-[0-9]{2} F @e/[a-z0-9-]+ @g @k/core/'

# The enclosing SessionStart hook timeout is 5,000 ms, matching the existing
# memory-hook contract and the project-scoped proof registration. On the
# 2,948-record scratch store, 10 simultaneous calls (the named maximum primary
# session count) measured wake at 55.655 ms max; the slower core recall measured
# 64.268 ms max and 67.083 ms batch wall. Reserving ceil(64.268) + ceil(67.083)
# = 133 ms for timeout cleanup and JSON emission leaves 4,867 ms here.
internal_timeout=4.867s

emit_context() {
    /usr/bin/jq -cn --arg context "$1" \
        '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$context}}'
}

# The measured per-hook SessionStart budget is 10,000 characters
# (state/optmem/hook-injection-limit.md). Above it the harness persists the
# payload to a file and injects a 2 KB preview, which is non-destructive but
# costs the model a Read. Withholding memory would be worse than overflowing, so
# the payload still goes out; the warning rides in front of it, inside the
# preview, naming the knob to turn.
INJECTION_BUDGET=10000

emit_payload() {
    local payload=$1 warning=$2
    if (( ${#payload} > INJECTION_BUDGET )); then
        emit_context "$warning
$payload"
    else
        emit_context "$payload"
    fi
}

# Newest wins per (entity, scope, key), as the note contract says: recall
# returns every version, so without this a superseded core note keeps loading
# beside its correction. A newest payload starting RETIRED drops the key.
dedupe_core() {
    /usr/bin/awk '
        /^#[0-9]+ / { n++; line[n] = $0; k = $4 " " $5 " " $6; key[n] = k; last[k] = n; next }
        END {
            c = 0
            for (i = 1; i <= n; i++) {
                if (last[key[i]] != i) continue
                p = line[i]; sub(/^([^ ]+ ){6}/, "", p)
                if (p ~ /^RETIRED/) continue
                print line[i]; c++
            }
            print c " core notes."
        }'
}

if [[ -n "${MEMORY_DIR:-}" ]]; then
    memory_store=$MEMORY_DIR
elif [[ -n "${HOME:-}" ]]; then
    memory_store=$HOME/.optmem/memory
else
    emit_context "OPTMEM CORE FAILURE: neither MEMORY_DIR nor HOME is set, so the memory store cannot be resolved. Run by hand after setting one: $memo recall '$core_regex'"
    exit 0
fi

printf -v memory_store_shell '%q' "$memory_store"
# Single-quote rather than %q: the regex has no single quote of its own, and a
# failure message is read by a human under time pressure, where %q's backslash
# soup is materially harder to scan than the literal pattern.
core_regex_shell="'$core_regex'"
manual_command="env MEMORY_DIR=$memory_store_shell $memo recall $core_regex_shell"

if [[ ! -x "$memo" ]]; then
    emit_context "OPTMEM CORE FAILURE: the memo CLI is missing or not executable at $memo. Run by hand: $manual_command"
    exit 0
fi

if [[ ! -d "$memory_store" || ! -f "$memory_store/LOG.txt" || ! -d "$memory_store/TREE" ]]; then
    emit_context "OPTMEM CORE FAILURE: the memory store is missing or incomplete at $memory_store; expected LOG.txt and TREE/. Run by hand: $manual_command"
    exit 0
fi

if command_output="$(MEMORY_DIR="$memory_store" /usr/bin/timeout "$internal_timeout" "$memo" recall "$core_regex" 2>&1)"; then
    command_status=0
else
    command_status=$?
fi

if [[ $command_status -eq 124 ]]; then
    emit_context "OPTMEM CORE FAILURE: memo recall timed out after $internal_timeout. Run by hand: $manual_command"
elif [[ $command_status -ne 0 ]]; then
    emit_context "OPTMEM CORE FAILURE: memo recall exited with status $command_status. Run by hand: $manual_command

Original memo output:
$command_output"
elif [[ -z "$command_output" ]]; then
    emit_context "OPTMEM CORE FAILURE: memo recall exited successfully but returned empty output. Run by hand: $manual_command"
elif [[ "$command_output" == "No match." ]]; then
    emit_context "OPTMEM CORE FAILURE: memo recall returned 'No match.' for the durable @k/core/ namespace. Run by hand: $manual_command"
elif [[ "$command_output" == *"Narrow the regex." ]]; then
    emit_context "OPTMEM CORE FAILURE: memo recall could not return the whole durable @k/core/ namespace within its output part. Run by hand: $manual_command

Original memo output:
$command_output"
else
    emit_payload "$(printf '%s\n' "$command_output" | dedupe_core)" "OPTMEM CORE OVERSIZE: this payload exceeds the measured 10,000-character SessionStart budget, so the harness has persisted it to a file and injected only a preview. Read that file, then narrow the @k/core/ set or split it across two hooks."
fi

exit 0
