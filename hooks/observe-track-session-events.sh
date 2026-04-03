#!/usr/bin/env bash
# JSONL event log for session state reconstruction. Tracks edits and commits.
# Event: PostToolUse (Edit, Write, Bash)
# Config: {"hooks":{"PostToolUse":[{"matcher":{"tool_name":"Edit|Write|Bash"},"hooks":[{"type":"command","command":"hooks/observe-track-session-events.sh"}]}]}}

STRATA_STATE_DIR="${STRATA_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/strata}"

stdinContent=""
if [ ! -t 0 ]; then
    stdinContent=$(cat)
fi
[ -z "$stdinContent" ] && exit 0

data=$(echo "$stdinContent" | jq '.' 2>/dev/null) || exit 0

toolName=$(echo "$data" | jq -r '.tool_name // empty' 2>/dev/null)
[ -z "$toolName" ] && exit 0

sessionId="default"
sid=$(echo "$data" | jq -r '.session_id // empty' 2>/dev/null)
if [ -n "$sid" ]; then
    sessionId="${sid:0:8}"
fi

mkdir -p "$STRATA_STATE_DIR"
jsonlFile="$STRATA_STATE_DIR/session-events-$sessionId.jsonl"
ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

if [ "$toolName" = "Edit" ] || [ "$toolName" = "Write" ]; then
    filePath=$(echo "$data" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
    [ -z "$filePath" ] && exit 0

    # Skip infrastructure files to avoid feedback loops
    if echo "$filePath" | grep -qE 'session-events-|\.session-edits-|\.verify-passed-|auto-context-save'; then
        exit 0
    fi
    # Skip files inside state dir
    if [[ "$filePath" == "$STRATA_STATE_DIR"/* ]]; then
        exit 0
    fi

    event=$(jq -nc \
        --arg type "edit" \
        --arg ts "$ts" \
        --arg sid "$sessionId" \
        --arg file "$filePath" \
        '{type: $type, ts: $ts, sid: $sid, file: $file}')
    echo "$event" >> "$jsonlFile"

elif [ "$toolName" = "Bash" ]; then
    command=$(echo "$data" | jq -r '.tool_input.command // empty' 2>/dev/null)
    [ -z "$command" ] && exit 0

    # Only track git commits
    if echo "$command" | grep -qE '^git commit\b|&&\s*git commit\b'; then
        # Extract commit message from -m flag
        msg=""
        if [[ "$command" =~ -m[[:space:]]+\"([^\"]+)\" ]]; then
            msg="${BASH_REMATCH[1]}"
        elif [[ "$command" =~ -m[[:space:]]+\'([^\']+)\' ]]; then
            msg="${BASH_REMATCH[1]}"
        elif [[ "$command" =~ -m[[:space:]]+([^[:space:]]+) ]]; then
            msg="${BASH_REMATCH[1]}"
        fi
        # Truncate long messages
        if [ ${#msg} -gt 120 ]; then
            msg="${msg:0:120}"
        fi

        event=$(jq -nc \
            --arg type "commit" \
            --arg ts "$ts" \
            --arg sid "$sessionId" \
            --arg msg "$msg" \
            '{type: $type, ts: $ts, sid: $sid, msg: $msg}')
        echo "$event" >> "$jsonlFile"
    fi
fi

exit 0
