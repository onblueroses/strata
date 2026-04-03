#!/usr/bin/env bash
# Track edited files per session for verification gate.
# Event: PostToolUse (Edit, Write)
# Config: {"hooks":{"PostToolUse":[{"matcher":{"tool_name":"Edit|Write"},"hooks":[{"type":"command","command":"hooks/observe-track-edits.sh"}]}]}}

STRATA_STATE_DIR="${STRATA_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/strata}"

stdinContent=""
if [ ! -t 0 ]; then
    stdinContent=$(cat)
fi
[ -z "$stdinContent" ] && exit 0

data=$(echo "$stdinContent" | jq '.' 2>/dev/null) || exit 0

filePath=$(echo "$data" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$filePath" ] && exit 0

# Skip files that are session bookkeeping, not implementation work.
if echo "$filePath" | grep -qE '\.session-edits-|\.verify-passed-'; then
    exit 0
fi
# Skip files inside the state dir itself (event logs, save files, etc.)
if [[ "$filePath" == "$STRATA_STATE_DIR"/* ]]; then
    exit 0
fi

# Resolve to absolute if relative
if [[ "$filePath" != /* ]]; then
    filePath="$(pwd)/$filePath"
fi

# Session ID
sessionId="default"
sid=$(echo "$data" | jq -r '.session_id // empty' 2>/dev/null)
if [ -n "$sid" ]; then
    sessionId="${sid:0:8}"
fi

mkdir -p "$STRATA_STATE_DIR"
editsFile="$STRATA_STATE_DIR/.session-edits-$sessionId"
jsonlFile="$STRATA_STATE_DIR/.session-edits-$sessionId.jsonl"

# Extract tool name for JSONL
toolName=$(echo "$data" | jq -r '.tool_name // "unknown"' 2>/dev/null)

# Plain-text: append if not already listed (verify gate reads this)
alreadyListed=false
if [ -f "$editsFile" ]; then
    if grep -qxF "$filePath" "$editsFile" 2>/dev/null; then
        alreadyListed=true
    fi
fi

if [ "$alreadyListed" = false ]; then
    echo "$filePath" >> "$editsFile"
fi

# JSONL: always append (captures every edit event, not just unique paths)
timestamp=$(date -u +%Y-%m-%dT%H:%M:%S)
jq -nc --arg ts "$timestamp" --arg fp "$filePath" --arg tool "$toolName" --arg sid "$sessionId" \
    '{timestamp:$ts, file:$fp, tool:$tool, session:$sid}' >> "$jsonlFile" 2>/dev/null

exit 0
