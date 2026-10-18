#!/usr/bin/env bash
# Timing support for the independently configured PreToolUse gate processes.
# This is intentionally separate from ../gates/run-gates.sh, which runs the offline
# verify-* policy suite. Gate scripts source this file; executing it directly is a no-op.

_gate_elapsed_ms() {
    local start="${_GATE_TELEMETRY_STARTED_AT:-}" end="${EPOCHREALTIME:-}"
    local start_fraction end_fraction elapsed_us
    [[ "$start" =~ ^[0-9]+\.[0-9]+$ && "$end" =~ ^[0-9]+\.[0-9]+$ ]] || return 1
    start_fraction="${start#*.}000000"
    end_fraction="${end#*.}000000"
    elapsed_us=$((
        10#${end%.*} * 1000000 + 10#${end_fraction:0:6}
        - 10#${start%.*} * 1000000 - 10#${start_fraction:0:6}
    ))
    (( elapsed_us > 0 )) || return 1
    printf '%d.%03d' "$((elapsed_us / 1000))" "$((elapsed_us % 1000))"
}

_gate_timing_json_field() {
    local field="$1" fallback="$2" value=""
    if command -v jq >/dev/null 2>&1; then
        value="$(printf '%s' "${_GATE_TELEMETRY_INPUT:-}" \
            | jq -r --arg field "$field" '.[$field] // empty' 2>/dev/null || true)"
    fi
    case "$value" in
        ""|*[!A-Za-z0-9_.:-]*) printf '%s' "$fallback" ;;
        *) printf '%s' "$value" ;;
    esac
}

_gate_emit_allow_timing() {
    local gate_rc="${1:-1}" duration gate default_tool input emitter
    trap - EXIT
    [ "$gate_rc" -eq 0 ] || return 0
    [ "${_GATE_TELEMETRY_EMIT_ALLOW:-0}" -eq 1 ] || return 0
    duration="$(_gate_elapsed_ms 2>/dev/null || true)"
    [ -n "$duration" ] || return 0
    gate="${_GATE_TELEMETRY_NAME:-unknown}"
    default_tool="${_GATE_TELEMETRY_DEFAULT_TOOL:-unknown}"
    input="${_GATE_TELEMETRY_INPUT:-}"
    emitter="${HOME:-$HOME}/.claude/telemetry/telemetry-emit.sh"

    # Parsing and sink I/O happen after the measured interval in a detached child. A broken,
    # absent, or slow telemetry path therefore cannot change the gate's verdict or latency.
    (
        local sid tool payload
        _GATE_TELEMETRY_INPUT="$input"
        sid="$(_gate_timing_json_field session_id unknown)"
        tool="$(_gate_timing_json_field tool_name "$default_tool")"
        payload="$(printf '{"tool":"%s","total_ms":%s,"per_gate_ms":{"%s":%s}}' \
            "$tool" "$duration" "$gate" "$duration")"
        bash "$emitter" gate_timing "$sid" "$payload"
    ) </dev/null >/dev/null 2>&1 &
    return 0
}

# --- fail closed on internal error (a ticket) ---------------------------------------------
# The default-guarding above is a discipline, enforced by a comment. Eleven gates source this
# file, so one unguarded expansion disarms all eleven at once — which is what happened at
# 2026-08-16 11:19. This is the mechanism behind the discipline: whatever goes wrong, a gate
# that dies without declaring a verdict refuses instead of permitting.
#
# PreToolUse reads exit 0 as allow and exit 2 as block. Every other status means "the hook
# errored" and is treated as non-blocking, so the command runs while the gate's BLOCKED text
# still reaches stderr. Every real exit statement in the ten blocking gates is 0 or 2 (audited
# 2026-08-16), so any other status is unintended by construction and converts to a block.
#
# Coverage, measured 2026-08-16 against this helper rather than assumed. Ordinary shell
# termination is not the only way a gate dies without a verdict, so the EXIT trap alone left
# four paths still permitting: SIGTERM 143, SIGPIPE 141, `exec` failure 127, and an outer
# `timeout` 124. The signal traps below close the ones a shell can catch. SIGKILL is
# irreducible by construction — nothing runs after it — so a gate killed with -9 still
# permits, and no claim here should suggest otherwise.
#
# The `timeout` case matters most because it is reachable in normal operation: settings.json
# bounds each hook, and `timeout` signals TERM first, so trapping TERM converts a hook that
# overran its budget into a refusal instead of a silent allow. Gates doing unbounded work
# should still carry their own measured self-deadline (a ticket); this is the backstop, not a
# substitute for one.
#
# Read before sourcing, not assigned: a hook that must fail OPEN sets _GATE_FAIL_CLOSED=0
# BEFORE it sources this file. Selecting the mode afterwards leaves a window in which a
# top-level abort during the source itself is converted to a block against the hook's own
# contract (codex review, 2026-08-16).
_GATE_FAIL_CLOSED="${_GATE_FAIL_CLOSED:-1}"

# Kept for hooks that select their mode after sourcing. Prefer the pre-source assignment: this
# cannot retroactively cover an abort that already happened while the file was being read.
gate_fail_open_on_error() { _GATE_FAIL_CLOSED=0; }

_gate_exit_trap() {
    local rc="${1:-1}" why="${2:-exited $1 without declaring a verdict}"
    trap - EXIT HUP INT QUIT TERM PIPE
    case "$rc" in
        0|2) _gate_emit_allow_timing "$rc"; exit "$rc" ;;
    esac
    [ "${_GATE_FAIL_CLOSED:-1}" -eq 1 ] || exit "$rc"
    printf '%s: BLOCKED (gate error): the hook %s. PreToolUse reads that as non-blocking, so this gate failed closed rather than let the command through. Fix the gate, then re-run.\n' \
        "${_GATE_TELEMETRY_NAME:-gate}" "$why" >&2
    exit 2
}

# Armed at source time, not inside gate_timing_begin: a gate that sources this file and then
# aborts before calling it is exactly the case worth covering.
trap '_gate_exit_trap "$?"' EXIT
# A signal kills the shell without running the EXIT trap, and the resulting 128+n status reads
# as non-blocking. TERM is the one that matters: `timeout` and process supervisors send it
# first, so an overrunning hook lands here rather than in a silent allow.
trap '_gate_exit_trap 143 "was terminated (SIGTERM) before reaching a verdict"' TERM
trap '_gate_exit_trap 141 "lost its output pipe (SIGPIPE) before reaching a verdict"' PIPE
trap '_gate_exit_trap 130 "was interrupted (SIGINT) before reaching a verdict"' INT
trap '_gate_exit_trap 129 "lost its terminal (SIGHUP) before reaching a verdict"' HUP
trap '_gate_exit_trap 131 "was quit (SIGQUIT) before reaching a verdict"' QUIT

gate_timing_begin() {
    # Every expansion in this file is default-guarded: gates source it under `set -u`, and an
    # unbound-variable abort here exits the gate 1, which PreToolUse treats as non-blocking —
    # a thrown wrapper silently disarms every gate that wraps it (observed 2026-08-16 11:19).
    _GATE_TELEMETRY_NAME="${1:-unknown}"
    _GATE_TELEMETRY_DEFAULT_TOOL="${2:-unknown}"
    _GATE_TELEMETRY_INPUT="${3:-}"
    _GATE_TELEMETRY_STARTED_AT="${4:-}"
    # Routine allow-path profiling is off after a ticket; pass 1 explicitly for a probe.
    _GATE_TELEMETRY_EMIT_ALLOW="${5:-0}"
    # The EXIT trap is already installed and routes to _gate_emit_allow_timing on a clean
    # allow; re-installing a timing-only trap here would drop the fail-closed conversion.
}

gate_payload_add_duration() {
    local variable="${1:-}" current="" duration
    [[ "$variable" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || return 0
    current="${!variable-}"
    _GATE_TELEMETRY_EMIT_ALLOW=0
    duration="$(_gate_elapsed_ms 2>/dev/null || true)"
    [ -n "$duration" ] || return 0
    case "$current" in
        "") printf -v "$variable" '{"duration_ms":%s}' "$duration" ;;
        \{\}) printf -v "$variable" '{"duration_ms":%s}' "$duration" ;;
        \{*\}) printf -v "$variable" '%s,"duration_ms":%s}' "${current%\}}" "$duration" ;;
    esac
}
