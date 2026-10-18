#!/usr/bin/env bash
set -euo pipefail
export LC_ALL=C

script_dir="$(cd "$(dirname "$0")" && pwd)"
helper="$script_dir/run-gates.sh"
scratch_root="${GATE_TEST_SCRATCH:-${TMPDIR:-/tmp}}"
scratch="$(mktemp -d "$scratch_root/run-gates-timing-XXXXXX")"
test_home="$scratch/home"
emitter="$test_home/.claude/telemetry/telemetry-emit.sh"
default_sink="$scratch/default.log"
opt_in_sink="$scratch/opt-in.log"
denial_sink="$scratch/denial.log"
mkdir -p "$(dirname "$emitter")"
: > "$default_sink"
: > "$opt_in_sink"
: > "$denial_sink"

cat > "$emitter" <<'EMITTER'
#!/usr/bin/env bash
printf '%s\t%s\t%s\n' "${1:-}" "${2:-}" "${3:-}" >> "$GATE_TIMING_TEST_SINK"
EMITTER
chmod +x "$emitter"

run_allow_probe() {
    local sink="$1" mode="${2:-default}"
    if [ "$mode" = "default" ]; then
        HOME="$test_home" GATE_TIMING_TEST_SINK="$sink" bash -c '
            set -uo pipefail
            . "$1"
            gate_timing_begin timing-test Bash '\''{"session_id":"timing-test","tool_name":"Bash"}'\'' "$EPOCHREALTIME"
            while [ "$EPOCHREALTIME" = "$_GATE_TELEMETRY_STARTED_AT" ]; do :; done
            exit 0
        ' bash "$helper"
    else
        HOME="$test_home" GATE_TIMING_TEST_SINK="$sink" bash -c '
            set -uo pipefail
            . "$1"
            gate_timing_begin timing-test Bash '\''{"session_id":"timing-test","tool_name":"Bash"}'\'' "$EPOCHREALTIME" 1
            while [ "$EPOCHREALTIME" = "$_GATE_TELEMETRY_STARTED_AT" ]; do :; done
            exit 0
        ' bash "$helper"
    fi
}

# One second is more than 59 times the measured 16.935 ms maximum for this local emitter.
wait_for_row() {
    local sink="$1"
    local attempt
    for ((attempt = 0; attempt < 100; attempt++)); do
        [ "$(wc -l < "$sink")" -ge 1 ] && return 0
        sleep 0.01
    done
    [ "$(wc -l < "$sink")" -ge 1 ]
}

failures=0
run_allow_probe "$default_sink"
if wait_for_row "$default_sink"; then
    echo "FAIL: ordinary allow emitted gate_timing without an explicit opt-in"
    failures=$((failures + 1))
else
    echo "PASS: ordinary allow stayed silent"
fi

run_allow_probe "$opt_in_sink" opt-in
if wait_for_row "$opt_in_sink" \
    && grep -Fq $'gate_timing\ttiming-test\t' "$opt_in_sink"; then
    echo "PASS: fifth-argument opt-in emitted gate_timing"
else
    echo "FAIL: explicit opt-in did not emit gate_timing inside the detection window"
    failures=$((failures + 1))
fi

denial_payload="$(HOME="$test_home" GATE_TIMING_TEST_SINK="$denial_sink" bash -c '
    set -uo pipefail
    . "$1"
    gate_timing_begin timing-test Bash '\''{"session_id":"timing-test","tool_name":"Bash"}'\'' "$EPOCHREALTIME"
    while [ "$EPOCHREALTIME" = "$_GATE_TELEMETRY_STARTED_AT" ]; do :; done
    payload='\''{"reason":"test-denial"}'\''
    gate_payload_add_duration payload
    printf "%s\n" "$payload"
' bash "$helper")"
if jq -e '.reason == "test-denial" and (.duration_ms | type == "number") and .duration_ms > 0' \
    >/dev/null <<< "$denial_payload"; then
    echo "PASS: denial payload retained duration_ms"
else
    echo "FAIL: denial payload lost a positive numeric duration_ms"
    failures=$((failures + 1))
fi
if wait_for_row "$denial_sink"; then
    echo "FAIL: denial duration also emitted an allow-path timing row"
    failures=$((failures + 1))
else
    echo "PASS: denial duration suppressed allow-path timing"
fi

printf 'run-gates timing scratch: %s\n' "$scratch"
exit "$failures"
