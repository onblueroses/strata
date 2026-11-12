#!/usr/bin/env bash
# Contract test for session-inject-time.sh: the label follows the event's source, a prompt
# gets a line only when this session's last reading is stale, and no input shape breaks it.
set -euo pipefail

hook="$(cd "$(dirname "$0")" && pwd)/session-inject-time.sh"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/test-clock-XXXXXX")"
trap 'rm -rf "$tmp"' EXIT
export CLOCK_STATE_DIR="$tmp/clock"
sid="aaaabbbb-0000-1111-2222-333344445555"

run() {  # run <json>; prints "<event> :: <context>" or nothing
    printf '%s' "$1" | bash "$hook" \
        | jq -r '.hookSpecificOutput | .hookEventName + " :: " + .additionalContext'
}
start() { run "{\"hook_event_name\":\"SessionStart\",\"source\":\"$1\",\"session_id\":\"$sid\"}"; }
prompt() { run "{\"hook_event_name\":\"UserPromptSubmit\",\"prompt\":\"x\",\"session_id\":\"${1:-$sid}\"}"; }
fail() { echo "FAIL: $*"; exit 1; }

# 1. The label names what happened: only a start says "started".
[[ "$(start startup)" == "SessionStart :: TIME: session started "* ]] || fail "startup label"
[[ "$(start clear)" == "SessionStart :: TIME: session started "* ]] || fail "clear label"
[[ "$(start resume)" == "SessionStart :: TIME: session resumed "* ]] || fail "resume label"
out="$(start compact)"
[[ "$out" == "SessionStart :: TIME: context compacted "* ]] || fail "compact label"
[[ "$out" == *"report UTC"* && "$out" == *'run `date`'* ]] || fail "zone lines missing: $out"

# 2. A prompt right after a reading: nothing.
[[ -z "$(prompt)" ]] || fail "prompt printed inside the fresh window"

# 3. A prompt after the window: one line, as a UserPromptSubmit payload; the next is silent again.
echo $(( $(date +%s) - 45 * 60 )) > "$CLOCK_STATE_DIR/${sid:0:8}"
out="$(prompt)"
[[ "$out" =~ ^UserPromptSubmit\ ::\ TIME:\ [0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}\ [A-Z0-9+-]+\ at\ this\ prompt\.$ ]] \
    || fail "stale prompt line wrong: $out"
[[ -z "$(prompt)" ]] || fail "second prompt printed again"

# 4. A session with no reading on record gets its first one at a prompt.
[[ "$(prompt ccccdddd-0000)" == "UserPromptSubmit :: TIME: "* ]] || fail "first reading missing"

# 5. Positive control for the window itself: at CLOCK_STALE_MIN=0 every prompt is stale.
[[ -n "$(CLOCK_STALE_MIN=0 prompt)" ]] || fail "window of zero stayed silent"

# 5b. A damaged stamp reads as stale, not as an error.
echo garbage > "$CLOCK_STATE_DIR/${sid:0:8}"
[[ "$(prompt)" == "UserPromptSubmit :: TIME: "* ]] || fail "damaged stamp stayed silent"

# 6. No session id: nothing to remember against, so a prompt stays silent.
[[ -z "$(run '{"hook_event_name":"UserPromptSubmit","prompt":"x"}')" ]] || fail "prompt without a session printed"

# 7. No stdin (Codex's start hook) and unparseable stdin: the start form, exit 0.
out="$(bash "$hook" < /dev/null | jq -r '.hookSpecificOutput.additionalContext')"
[[ "$out" == "TIME: session started "* ]] || fail "no-stdin run: $out"
out="$(printf 'not json' | bash "$hook" | jq -r '.hookSpecificOutput.additionalContext')"
[[ "$out" == "TIME: session started "* ]] || fail "garbage stdin: $out"

# 8. An unwritable state directory costs a repeat line, never an error.
out="$(CLOCK_STATE_DIR=/proc/nope prompt)" || fail "unwritable state dir exited nonzero"
[[ "$out" == "UserPromptSubmit :: TIME: "* ]] || fail "unwritable state dir lost the line"

printf 'session-inject-time: labels per source, prompt line only when stale, safe on every input shape\n'
