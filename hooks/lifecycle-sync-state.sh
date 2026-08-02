#!/usr/bin/env bash
# Stop hook: auto-commit + push a configured state directory when both of these
# are true:
#   1. $STRATA_SYNC_DIR is set (explicit opt-in)
#   2. $STRATA_SYNC_DIR is a git repo with a configured remote
#
# Default behavior is no-op so the hook can ship enabled without forcing every
# user into a git-based sync workflow. Set STRATA_SYNC_DIR in your shell rc to
# turn it on:
#
#   export STRATA_SYNC_DIR="$STATE_DIR"        # sync runtime state
#
# Uses a per-target lockfile to serialize concurrent sync attempts.

set -uo pipefail

SYNC_DIR="${STRATA_SYNC_DIR:-}"
[[ -z "$SYNC_DIR" ]] && exit 0
[[ -d "$SYNC_DIR/.git" ]] || exit 0

LOCK="$SYNC_DIR/.git/sync.lock"
LOCK_ACQUIRED=false

cleanup_lock() {
  if $LOCK_ACQUIRED && [[ -f "$LOCK" ]]; then
    rm -f "$LOCK" 2>/dev/null
  fi
}
trap cleanup_lock EXIT

# Use the session id as a stable, backend-independent commit label.
SESSION_NAME="unknown-session"
if [[ ! -t 0 ]]; then
  JSON=$(cat)
  if [[ -n "$JSON" ]]; then
    SID=$(echo "$JSON" | jq -r '.session_id // empty' 2>/dev/null)
    if [[ -n "$SID" ]]; then
      SESSION_NAME="session-${SID:0:8}"
    fi
  fi
fi

# Acquire lock (15s timeout).
DEADLINE=$((SECONDS + 15))
while ! $LOCK_ACQUIRED && [[ $SECONDS -lt $DEADLINE ]]; do
  if (set -C; echo $$ > "$LOCK") 2>/dev/null; then
    LOCK_ACQUIRED=true
  else
    sleep 0.5
  fi
done
$LOCK_ACQUIRED || exit 0

cd "$SYNC_DIR" || exit 0
STATUS=$(git status --porcelain 2>/dev/null)
if [[ -n "$STATUS" ]]; then
  TIMESTAMP=$(date +"%Y-%m-%d %H:%M")
  git add -A >/dev/null 2>&1
  git commit -m "Auto-sync: $SESSION_NAME ($TIMESTAMP)" >/dev/null 2>&1
  git push &>/dev/null & disown
fi
