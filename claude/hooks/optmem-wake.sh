#!/usr/bin/env bash
# SessionStart: inject the OptMem wake document under a validated session-scope header.
# Every path exits 0 with a payload; a failure says what failed and the command to run by
# hand. One telemetry row per run records which path ended it.

set -u
case ${BASH_SOURCE[0]} in */*) here=${BASH_SOURCE[0]%/*} ;; *) here=. ;; esac
# shellcheck source=lib/optmem-session.sh
. "$here/lib/optmem-session.sh" 2>/dev/null || {
    printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"SessionStart","additionalContext":"OPTMEM WAKE FAILURE: hooks/lib/optmem-session.sh could not be loaded, so memory was not read. Run by hand: memo wake"}}'
    exit 0
}

# ------------------------------------------------------------- telemetry
#
# The row is written by the EXIT trap, so it lands after the injection is on stdout, on every
# path including the early ones. A failed emission is swallowed: telemetry may never be the
# reason a session loses its memory.

wake_status=error       # ok | refused | error
wake_reason=unreached   # which branch ended the hook
wake_sid=unknown
wake_unsettled=""       # blocks awaiting a nap, when the output states it
wake_ms=""              # the memo wake call itself
wake_chars=""           # size of the injected payload
NOW_US=0

clock_us() {
    # EPOCHREALTIME is bash 5 and costs no fork; a shell without it emits no
    # timing rather than paying a subprocess per hook run.
    NOW_US=0
    local t=${EPOCHREALTIME:-}
    t=${t/[.,]/}
    [[ "$t" =~ ^[0-9]{10,}$ ]] && NOW_US=$t
    return 0
}

clock_us
wake_start_us=$NOW_US

emit_wake() {
    local exit_status=$?
    [[ -n "${HOME:-}" ]] || return 0
    local emitter="$HOME/.claude/telemetry/telemetry-emit.sh"
    [[ -f "$emitter" ]] || return 0
    local extra=""
    clock_us
    if (( wake_start_us > 0 && NOW_US > 0 )); then
        extra=",\"ms\":$(( (NOW_US - wake_start_us) / 1000 ))"
    fi
    [[ -n "$wake_ms" ]] && extra="$extra,\"wake_ms\":$wake_ms"
    [[ -n "$wake_unsettled" ]] && extra="$extra,\"unsettled\":$wake_unsettled"
    [[ -n "$wake_chars" ]] && extra="$extra,\"chars\":$wake_chars"
    # Every value is one of this script's own literals or an integer, so the JSON needs no jq.
    # Bounded: a wedged emitter must not get the hook killed before the harness reads it.
    /usr/bin/timeout 1s bash "$emitter" optmem_wake "$wake_sid" \
        "{\"status\":\"$wake_status\",\"reason\":\"$wake_reason\"$extra}" \
        >/dev/null 2>&1 || true
    return "$exit_status"
}

trap emit_wake EXIT

# Sample split of a 5,000 ms hook timeout: 1,000 ms go to the bounded stdin read below and
# a small reserve to cleanup and the JSON, which leaves this for the wake call. Keep the sum
# below the timeout you register.
internal_timeout=3.867s

# The note grammar scopes every session-local record with @s/<8 chars>, and the harness
# passes the authoritative session_id on JSON stdin; this prints the token so the model never
# has to derive one.
#
# Resolution failure prints the failure rather than a substitute id. A wrong
# @s/ token writes notes under another session's identity, which last-write-wins
# then treats as supersession; an absent token costs one question.
resolve_session_scope() {
    # Bash character ranges follow locale collation, and these hooks run under
    # LANG=en_US.UTF-8, where [a-z0-9] matches accented letters: a session_id of
    # "abcdefgh" with an accent passes an unguarded check and emits a token the
    # note grammar forbids. Verified both ways on this machine. C collation is
    # what makes [a-z0-9] mean ASCII.
    local LC_ALL=C
    local raw="" sid="" jq_status=0
    if [[ ! -t 0 ]]; then
        # The harness closes stdin, so plain `cat` returns; a pipe left open would
        # otherwise block until the enclosing 5,000 ms hook timeout kills the hook
        # and costs the session its whole memory injection. Bound the read instead:
        # partial input fails the parse below and resolves to unresolved.
        raw=$(/usr/bin/timeout 1s cat)
    fi
    if [[ -n "$raw" ]]; then
        # Require a string: `jq -r` stringifies a numeric session_id, so
        # {"session_id":12345678} would otherwise become a valid-looking token.
        sid=$(/usr/bin/jq -r 'if (.session_id|type)=="string" then .session_id else empty end' <<<"$raw" 2>/dev/null)
        jq_status=$?
    fi
    # jq prints a parsed value BEFORE failing on trailing garbage and exits 5, so
    # ignoring the status would let {"session_id":"..."} junk become canonical.
    if (( jq_status != 0 )); then
        sid=""
    fi
    sid=${sid:0:8}
    if [[ "$sid" =~ ^[a-z0-9]{8}$ ]]; then
        printf 'SESSION SCOPE: @s/%s\nUse this exact token for session-scoped OptMem notes.' "$sid"
    else
        printf 'SESSION SCOPE: unresolved\nThe SessionStart payload carried no usable session_id, so no @s/ token is available. Ask before writing any session-scoped note; a guessed id writes into another session.'
    fi
}

# Command substitution strips trailing newlines, so the blank line that separates
# the header from the payload is joined here rather than printed above.
context_prefix="$(resolve_session_scope)"$'\n\n'

# The header carries the only validated copy of the session id; read it back
# rather than plumbing a second one out of the subshell above.
if [[ "$context_prefix" =~ @s/([a-z0-9]{8}) ]]; then
    wake_sid="${BASH_REMATCH[1]}"
fi

if ! optmem_preflight WAKE wake; then
    wake_reason=$preflight_reason
    exit 0
fi

clock_us
wake_call_start_us=$NOW_US
if command_output="$(MEMORY_DIR="$memory_store" /usr/bin/timeout "$internal_timeout" "$memo" wake 2>&1)"; then
    command_status=0
else
    command_status=$?
fi
clock_us
if (( wake_call_start_us > 0 && NOW_US > 0 )); then
    wake_ms=$(( (NOW_US - wake_call_start_us) / 1000 ))
fi
wake_chars=${#command_output}

# What the memory still owes, as memo itself renders it: the refusal names the
# whole backlog, a nap prompt names what remains after the one it offers.
if [[ "$command_output" =~ Do\ the\ ([0-9]+)\ compression ]]; then
    wake_unsettled="${BASH_REMATCH[1]}"
elif [[ "$command_output" =~ ([0-9]+)\ compressions\ remain ]]; then
    wake_unsettled=$(( BASH_REMATCH[1] + 1 ))
elif [[ "$command_output" == *"1 compression remains"* ]]; then
    wake_unsettled=2
elif [[ "$command_output" == *"Compress memories #"* ]]; then
    wake_unsettled=1
elif (( command_status == 0 )); then
    wake_unsettled=0
fi

if [[ $command_status -eq 124 ]]; then
    wake_reason=timeout
    emit_context "OPTMEM WAKE FAILURE: memo wake timed out after $internal_timeout. Run by hand: $manual_command"
elif [[ $command_status -ne 0 && "$command_output" == *"Cannot wake:"* ]]; then
    # Not a failure: this is OptMem's consolidation cycle asking to be paid.
    # `memo wake` renders its document from compressed blocks, so once a block
    # the document needs is still raw it refuses until that block is summarized.
    # The store refuses past a fixed number of unsettled notes, which a busy afternoon
    # reaches. One nap restores wake; the whole backlog need not be cleared.
    # The session pays this at start, which is OptMem's own design
    # (wake prints the prompt in-band) and keeps the debt from outliving one
    # session start. So hand the model the prompt and the command, not an error.
    wake_status=refused
    wake_reason=nap-required
    emit_context "OPTMEM MEMORY NEEDS A NAP BEFORE IT CAN BE READ.

Do this NOW, before any other work, or this session has no memory:
1. Write one line, within the store's note limit, compressing the memories shown below. Keep what has lasting effect, drop what does not, invent nothing. Open with the date range, then plain sentences (what happened, what was decided, what is still alive); no @ tokens, no keyword lists.
2. Run: env MEMORY_DIR=$memory_store_shell $memo nap <lo>-<hi> \"<your line>\" using the exact block ids below.
3. Run: $manual_command
4. Repeat until wake returns the memory and ends with 'You are awake.'; clear any remaining compressions the same way once you have your memory.

$command_output"
elif [[ $command_status -ne 0 ]]; then
    wake_reason="exit-$command_status"
    emit_context "OPTMEM WAKE FAILURE: memo wake exited with status $command_status. Run by hand: $manual_command

Original memo output:
$command_output"
elif [[ -z "$command_output" ]]; then
    wake_reason=empty-output
    emit_context "OPTMEM WAKE FAILURE: memo wake exited successfully but returned empty output. Run by hand: $manual_command"
elif [[ "$command_output" == *"Not awake yet. Run:"* ]]; then
    # memo pages its output above PART_CHARS or PART_LINES, and part 1 alone is
    # not the whole memory. A hook cannot follow the paging without an agent
    # round trip, which is exactly what this hook exists to avoid.
    wake_reason=paged
    emit_context "OPTMEM WAKE FAILURE: WAKE_LINES is large enough that memo paged its output, so this is only part 1 of the memory. Lower WAKE_LINES in $memory_store/config until wake returns one part. Run by hand: $manual_command

Original memo output:
$command_output"
elif ! /usr/bin/grep -Fqx 'You are awake.' <<<"$command_output"; then
    wake_reason=unconfirmed
    emit_context "OPTMEM WAKE FAILURE: memo wake returned output without the required 'You are awake.' confirmation. Run by hand: $manual_command

Original memo output:
$command_output"
else
    wake_status=ok
    wake_reason=awake
    # Wake succeeded. When compressions are pending, memo appends the next nap
    # prompt after "You are awake."; paying it here is what keeps the backlog
    # away from the refusal threshold above. Cheap now, or the whole
    # memory injection later.
    if [[ "$command_output" == *"Compress memories #"* ]]; then
        command_output="$command_output

OPTMEM: compressions are pending, shown above. Clear them this session: env MEMORY_DIR=$memory_store_shell $memo nap <lo>-<hi> \"<line>\". Stay within the store's note limit. Start with the date range. Write plain sentences about events, decisions and open work. Use no @ tokens or keyword lists. Past the store's unsettled-note threshold, wake refuses until one nap is paid."
    fi
    emit_payload "$command_output" "OPTMEM WAKE OVERSIZE: this payload exceeds OPTMEM_INJECTION_BUDGET, so the harness may have persisted it to a file and injected only a preview. Read that file, then lower WAKE_LINES in the store's config."
fi

exit 0
