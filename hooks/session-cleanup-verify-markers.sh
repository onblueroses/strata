#!/usr/bin/env bash
# SessionStart hook: clears verify marker files for THIS session only.
# Other sessions' files are untouched (concurrency safe).
# Runs only on genuinely new sessions: a compact/resume restart keeps its markers —
# .session-edits-{sid} feeds the spec-ownership filters in the compaction hooks.

sessionId="default"
jsonInput=""
if [ ! -t 0 ]; then
    jsonInput=$(cat)
fi
if [ -n "$jsonInput" ]; then
    src=$(echo "$jsonInput" | jq -r '.source // .trigger // empty' 2>/dev/null)
    case "$src" in
        compact|resume) exit 0 ;;
    esac
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
