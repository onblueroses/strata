#!/usr/bin/env bash
# dispatch_wave.sh — encodes the sentinel-file dispatch pattern for /recon waves.
#
# Goal: dispatch N codex wrapper calls in parallel against N prompt files,
#       capture exit codes via .status sentinel files, enforce deadline + stall
#       detection, and exit with the worst child code so the orchestrator can
#       branch on it.
#
# Usage:
#   bash dispatch_wave.sh \
#     --run-dir DIR --wave WAVE_LABEL --wrapper fast|strong \
#     [--deadline N_SECS] [--no-progress N_SECS] [--cache MODE] \
#     PROMPT_FILE [PROMPT_FILE ...]
#
# --cache is forwarded only because lane wrappers accept it as a compatibility
# no-op; this helper does not provide response caching.
#
# For each PROMPT_FILE foo.prompt.md the script writes:
#   foo.out      — stdout+stderr from the wrapper
#   foo.status   — exit code of the wrapper (or 124 on timeout)
#   foo.pid      — pid of the wrapped subshell (so the orchestrator can debug hangs)
#
# Exit codes (worst child wins):
#   0   — all children clean
#   3   — at least one child returned 3 (quota / throttle)
#   124 — at least one child timed out (deadline or stall)
#   other — at least one child returned a non-zero non-3 code

set -u

RUN_DIR=""
WAVE=""
WRAPPER=""
DEADLINE_SECS=1800     # overall wave wall-clock cap
STALL_SECS=300         # no-progress window
CACHE_FLAG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --run-dir)     RUN_DIR="$2";       shift 2;;
    --wave)        WAVE="$2";          shift 2;;
    --wrapper)     WRAPPER="$2";       shift 2;;
    --deadline)    DEADLINE_SECS="$2"; shift 2;;
    --no-progress) STALL_SECS="$2";    shift 2;;
    --cache)       CACHE_FLAG="--cache $2"; shift 2;;
    --) shift; break;;
    -*) echo "unknown flag: $1" >&2; exit 2;;
    *)  break;;
  esac
done

if [[ -z "$RUN_DIR" || -z "$WAVE" || -z "$WRAPPER" || $# -eq 0 ]]; then
  echo "usage: dispatch_wave.sh --run-dir DIR --wave LABEL --wrapper W [--deadline N] [--no-progress N] [--cache MODE] PROMPT [PROMPT ...]" >&2
  exit 2
fi

if [[ ! -d "$RUN_DIR" ]]; then
  echo "run-dir does not exist: $RUN_DIR" >&2
  exit 2
fi

PROMPTS=("$@")
TOTAL=${#PROMPTS[@]}

echo "dispatching $TOTAL prompts to $WRAPPER (wave=$WAVE, deadline=${DEADLINE_SECS}s, stall=${STALL_SECS}s)"

# Launch each prompt in a subshell that captures the exit code into a .status sentinel.
for PROMPT in "${PROMPTS[@]}"; do
  if [[ ! -f "$PROMPT" ]]; then
    echo "prompt file missing: $PROMPT" >&2
    BASE="${PROMPT%.prompt.md}"
    echo "127" > "${BASE}.status"
    continue
  fi
  BASE="${PROMPT%.prompt.md}"
  (
    "$WRAPPER" $CACHE_FLAG --file "$PROMPT" > "${BASE}.out" 2>&1
    echo $? > "${BASE}.status"
  ) &
  echo $! > "${BASE}.pid"
done

# Wait loop with deadline + no-progress detection. Watch for .status files appearing.
START=$(date +%s)
LAST_PROGRESS=$START
LAST_DONE=0

while true; do
  sleep 5
  NOW=$(date +%s)
  DONE=$(ls "$RUN_DIR"/${WAVE}-*.status 2>/dev/null | wc -l)
  if [[ "$DONE" -gt "$LAST_DONE" ]]; then
    LAST_DONE=$DONE
    LAST_PROGRESS=$NOW
  fi
  if [[ "$DONE" -ge "$TOTAL" ]]; then break; fi
  ELAPSED=$((NOW - START))
  STALLED=$((NOW - LAST_PROGRESS))
  if [[ "$ELAPSED" -gt "$DEADLINE_SECS" ]]; then
    echo "DEADLINE_EXCEEDED after ${ELAPSED}s ($DONE/$TOTAL complete)" >&2
    break
  fi
  if [[ "$STALLED" -gt "$STALL_SECS" ]]; then
    echo "NO_PROGRESS for ${STALLED}s ($DONE/$TOTAL complete)" >&2
    break
  fi
done

# Write synthetic 124 for any prompt that never produced a .status file.
for PROMPT in "${PROMPTS[@]}"; do
  BASE="${PROMPT%.prompt.md}"
  if [[ ! -f "${BASE}.status" ]]; then
    PID=$(cat "${BASE}.pid" 2>/dev/null || true)
    if [[ -n "$PID" ]] && kill -0 "$PID" 2>/dev/null; then
      kill "$PID" 2>/dev/null || true
    fi
    echo "124" > "${BASE}.status"
  fi
done

# Compute the worst exit code: 124 > 3 > other-nonzero > 0.
WORST=0
for PROMPT in "${PROMPTS[@]}"; do
  BASE="${PROMPT%.prompt.md}"
  CODE=$(cat "${BASE}.status" 2>/dev/null || echo 1)
  case "$CODE" in
    0)   ;;
    3)   if [[ "$WORST" != 124 ]]; then WORST=3; fi ;;
    124) WORST=124 ;;
    *)   if [[ "$WORST" == 0 ]]; then WORST="$CODE"; fi ;;
  esac
done

echo "wave $WAVE complete: $DONE/$TOTAL done, worst_status=$WORST"
exit "$WORST"
