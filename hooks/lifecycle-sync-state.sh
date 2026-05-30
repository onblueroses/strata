#!/usr/bin/env bash
# Stop hook: auto-commit + push the state directory (typically $KB_DIR or
# $STATE_DIR) when both of these are true:
#   1. $STRATA_SYNC_DIR is set (opt-in; see CLAUDE.md Decisions on lifecycle-sync)
#   2. $STRATA_SYNC_DIR is a git repo with a configured remote
#
# Default behavior is no-op so the hook can ship enabled without forcing every
# user into a git-based sync workflow. Set STRATA_SYNC_DIR in your shell rc to
# turn it on:
#
#   export STRATA_SYNC_DIR="$KB_DIR"           # sync the whole workspace
#   export STRATA_SYNC_DIR="$STATE_DIR/specs"  # or just the specs subtree
#
# Uses a per-target lockfile so parallel sessions never collide.

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

# Read session-name hint from JSON stdin (matches the daily-note pattern
# when $KB_DIR/daily/ holds session journals named YYYY-MM-DD-<slug>-<sid>.json).
SESSION_NAME="unknown"
if [[ ! -t 0 ]]; then
  JSON=$(cat)
  if [[ -n "$JSON" ]]; then
    SID=$(echo "$JSON" | jq -r '.session_id // empty' 2>/dev/null)
    if [[ -n "$SID" ]]; then
      SID="${SID:0:8}"
      TODAY=$(date +%Y-%m-%d)
      MATCH=$(find "${KB_DIR:-$SYNC_DIR}/daily" -maxdepth 1 -name "$TODAY-*-$SID.json" 2>/dev/null | head -1)
      if [[ -n "$MATCH" ]]; then
        SNAME=$(jq -r '.session_name // empty' "$MATCH" 2>/dev/null)
        [[ -n "$SNAME" && "$SNAME" != "unnamed" ]] && SESSION_NAME="$SNAME"
      fi
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
