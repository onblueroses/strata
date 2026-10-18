#!/usr/bin/env bash
# Failure-classifier regression tests for the codex wrappers.
#
# The wrappers decide success or quota-wall by grepping the captured event stream, so any
# run whose transcript quotes the quota wording used to be reported as a wall. These cases
# drive each wrapper end-to-end against a scripted `codex` stub and assert the exit code.
#
# Run: bash ~/.claude/delegate/test-classifier.sh
set -uo pipefail

WRAPPER_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
WRAPPERS=(codex-strong codex-fast ds-codex)

die() { echo "test-classifier: $1" >&2; exit 1; }

tmpdir=$(mktemp -d) || die "cannot create a temp directory"
trap 'rm -rf "$tmpdir"' EXIT

STUB_DIR="$tmpdir/stub"
SCENARIO="$tmpdir/scenario"
mkdir -p "$STUB_DIR" "$SCENARIO" || die "cannot create the fixture directories"

cat >"$STUB_DIR/codex" <<'STUB' || die "cannot write the codex stub"
#!/usr/bin/env bash
# Replays a scripted run: stdout stream, stderr text, last message, exit code.
cat >/dev/null   # drain the piped prompt so the writer never takes SIGPIPE
last="" prev=""
for a in "$@"; do
  [[ "$prev" == "--output-last-message" ]] && last="$a"
  prev="$a"
done
[[ -n "$last" ]] && cat "$CODEX_STUB_SCENARIO/last" >"$last"
cat "$CODEX_STUB_SCENARIO/stdout"
cat "$CODEX_STUB_SCENARIO/stderr" >&2
exit "$(cat "$CODEX_STUB_SCENARIO/exit")"
STUB

# ds-codex probes its LiteLLM bridge with curl and refuses to dispatch when it is down.
# Stubbing the probe keeps ds-codex covered whether or not the service happens to be running.
cat >"$STUB_DIR/curl" <<'STUB' || die "cannot write the curl stub"
#!/usr/bin/env bash
exit 0
STUB

# A jq that exits non-zero without writing output: the wrapper's completion probe must fall
# back to the last-message file instead of reading an unreadable stream as "no turn".
BROKEN_JQ="$tmpdir/brokenjq"
mkdir -p "$BROKEN_JQ" || die "cannot create the broken-jq directory"
printf '#!/usr/bin/env bash\nexit 1\n' >"$BROKEN_JQ/jq" || die "cannot write the broken jq stub"

chmod +x "$STUB_DIR/codex" "$STUB_DIR/curl" "$BROKEN_JQ/jq" || die "cannot make the stubs executable"
# Without an executable stub first on PATH the wrappers resolve the real codex and launch
# agentic full-access runs, so refuse to continue rather than dispatch for real.
[[ -x "$STUB_DIR/codex" && -x "$STUB_DIR/curl" ]] || die "stubs are not executable; refusing to run"
for w in "${WRAPPERS[@]}"; do
  [[ -r "$WRAPPER_DIR/$w" ]] || die "wrapper not found: $WRAPPER_DIR/$w"
done

PASS=0
FAIL=0
CASE=0
EXTRA_PATH=""   # prepended to PATH for the next expect() call, then cleared

# scenario <stdout> <stderr> <exit> <last-message>
scenario() {
  printf '%s' "$1" >"$SCENARIO/stdout"
  printf '%s' "$2" >"$SCENARIO/stderr"
  printf '%s' "$3" >"$SCENARIO/exit"
  printf '%s' "$4" >"$SCENARIO/last"
}

# expect <case-name> <expected-rc> [expected-stdout-substring]
expect() {
  local name=$1 want=$2 want_out=${3:-} wrapper out rc
  CASE=$((CASE + 1))
  for wrapper in "${WRAPPERS[@]}"; do
    # Fresh cache per case: a wrapper that records a rate limit opens its circuit breaker,
    # which would short-circuit every later case in the run.
    out=$(PATH="${EXTRA_PATH:+$EXTRA_PATH:}$STUB_DIR:$PATH" \
          HOME="$tmpdir/home" \
          DELEGATE_CACHE_DIR="$tmpdir/cache-$wrapper-$CASE" \
          DEEPSEEK_API_KEY="stub-key-unused-by-the-codex-stub" \
          CODEX_STUB_SCENARIO="$SCENARIO" \
          bash "$WRAPPER_DIR/$wrapper" "regression probe" 2>/dev/null)
    rc=$?
    if [[ "$rc" -ne "$want" ]]; then
      echo "FAIL $wrapper/$name: exit $rc, want $want" >&2
      FAIL=$((FAIL + 1))
    elif [[ -n "$want_out" && "$out" != *"$want_out"* ]]; then
      echo "FAIL $wrapper/$name: stdout missing '$want_out' (got: ${out:0:80})" >&2
      FAIL=$((FAIL + 1))
    else
      PASS=$((PASS + 1))
    fi
  done
  EXTRA_PATH=""
}

STARTED='{"type":"thread.started","thread_id":"019f0000-0000-7000-8000-000000000000"}
{"type":"turn.started"}
'
COMPLETED='{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":10}}
'

# The reported bug: a 30-minute run that finished, whose transcript quotes the very wording
# the classifier greps for, because the model was reading these wrappers.
scenario "$STARTED"'{"type":"item.completed","item":{"type":"agent_message","text":"the branch greps for \"hit your usage limit for GPT-\" and exits 3"}}
'"$COMPLETED" "" 0 "PORT COMPLETE"
expect "completed-run-quoting-quota-wording" 0 "PORT COMPLETE"

# Same shape for the API-error branch. Its regex is line-anchored on `^ERROR: `, which no
# JSON-escaped message string can match, so codex's own stderr is the only surface that can
# carry error-looking text into a run that nonetheless completed its turn.
scenario "$STARTED$COMPLETED" 'ERROR: {"status":500,"message":"error-looking stderr on a completed run"}
' 0 "PORT COMPLETE"
expect "completed-run-with-error-looking-stderr" 0 "PORT COMPLETE"

# A real subscription wall: model-specific wording, no turn completes, codex exits clean.
scenario "$STARTED" "ERROR: You've hit your usage limit for GPT-5.6-sol. Try again later.
" 0 ""
expect "real-usage-limit-wall" 3

# A real 429 wall: retry limit exhausted, codex exits non-zero.
scenario "$STARTED" "stream error: exceeded retry limit, last status: 429; request id: req_00000000
" 1 ""
expect "real-429-wall" 3

# A real API error event with no completed turn.
scenario "$STARTED"'{"type":"error","message":"model_not_found"}
' "" 0 ""
expect "real-api-error-event" 2

# A turn that completed but whose process still failed stays an error: the guard requires
# both a completed turn and a clean exit before it suppresses classification.
scenario "$STARTED$COMPLETED" "" 124 "partial"
expect "completed-turn-with-failed-exit" 2

# No wall wording anywhere and a completed turn: the ordinary success path.
scenario "$STARTED$COMPLETED" "" 0 "ordinary result"
expect "ordinary-success" 0 "ordinary result"

# jq present but failing takes the completion signal from the last-message file; an
# unreadable stream must not read as "no turn completed" and revive the text-matching bug.
scenario "$STARTED"'{"type":"item.completed","item":{"type":"agent_message","text":"quotes \"hit your usage limit for GPT-\" verbatim"}}
'"$COMPLETED" "" 0 "PORT COMPLETE"
EXTRA_PATH="$BROKEN_JQ"
expect "broken-jq-falls-back-to-last-message" 0 "PORT COMPLETE"

echo "classifier: $PASS passed, $FAIL failed"
# A silently shortened run reads as a green suite, so assert the full matrix actually ran.
want=$((CASE * ${#WRAPPERS[@]}))
if [[ $((PASS + FAIL)) -ne "$want" ]]; then
  echo "FAIL: ran $((PASS + FAIL)) checks, expected $want ($CASE cases x ${#WRAPPERS[@]} wrappers)" >&2
  exit 1
fi
[[ "$FAIL" -eq 0 ]]
