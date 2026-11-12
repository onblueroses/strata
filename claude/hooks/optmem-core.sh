#!/usr/bin/env bash
# SessionStart: inject the durable @k/core/ notes, newest version of each key.
# Every path exits 0 with a payload; a failure says what failed and the command to run by hand.

set -u
case ${BASH_SOURCE[0]} in */*) here=${BASH_SOURCE[0]%/*} ;; *) here=. ;; esac
# shellcheck source=lib/optmem-session.sh
. "$here/lib/optmem-session.sh" 2>/dev/null || {
    printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"OPTMEM CORE FAILURE: hooks/lib/optmem-session.sh could not be loaded, so the core notes were not read. Run by hand: memo recall @k/core/"}}'
    exit 0
}

core_regex='^#[0-9]+ [0-9]{4}-[0-9]{2}-[0-9]{2} F @e/[a-z0-9-]+ @g @k/core/'

# Sample split of a 5,000 ms hook timeout: a small reserve stays for cleanup and the JSON.
# Keep it below the timeout you register.
internal_timeout=4.867s

# Newest wins per (entity, scope, key), as the note contract says: recall returns every
# version, so without this a superseded core note keeps loading beside its correction. A
# newest payload starting RETIRED drops the key.
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

# The regex is single-quoted in the by-hand command, not %q-escaped: it holds no single quote,
# and a failure message is read under time pressure, where backslash soup is harder to scan.
optmem_preflight CORE "recall '$core_regex'" || exit 0

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
    emit_payload "$(printf '%s\n' "$command_output" | dedupe_core)" "OPTMEM CORE OVERSIZE: this payload exceeds OPTMEM_INJECTION_BUDGET, so the harness may have persisted it to a file and injected only a preview. Read that file, then narrow the @k/core/ set or split it across two hooks."
fi

exit 0
