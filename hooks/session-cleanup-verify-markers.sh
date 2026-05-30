#!/usr/bin/env bash
# SessionStart hook: clears verify marker files for THIS session only.
# Other sessions' files are untouched (concurrency safe).

sessionId="default"
jsonInput=""
if [ ! -t 0 ]; then
    jsonInput=$(cat)
fi
if [ -n "$jsonInput" ]; then
    sid=$(echo "$jsonInput" | jq -r '.session_id // empty' 2>/dev/null)
    if [ -n "$sid" ]; then
        sessionId="${sid:0:8}"
    fi
fi

stateDir="$STATE_DIR"
editsFile="$stateDir/.session-edits-$sessionId"
verifyFile="$stateDir/.verify-passed-$sessionId"

rm -f "$editsFile" 2>/dev/null
rm -f "$verifyFile" 2>/dev/null

exit 0
