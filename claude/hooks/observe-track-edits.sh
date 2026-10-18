#!/usr/bin/env bash
# PostToolUse hook: tracks which files were edited this session.
# Appends file paths to life/areas/claude-code-setup/state/.session-edits-{sessionId} (deduped).
# Supplies the ownership guard and deliberate session reconciliation; it starts no review.

stdinContent=""
if [ ! -t 0 ]; then
    stdinContent=$(cat)
fi
[ -z "$stdinContent" ] && exit 0

data=$(echo "$stdinContent" | jq '.' 2>/dev/null) || exit 0

filePath=$(echo "$data" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$filePath" ] && exit 0

# Skip files that are session bookkeeping, not implementation work.
# These should never trigger re-verification.
if echo "$filePath" | grep -qE '\.session-edits-|\.verify-passed-|dream-state\.json|skill-runs\.jsonl|session-events-.*\.jsonl|/life/daily/.*\.json'; then
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

stateDir="${CLAUDE_SESSION_STATE_DIR:-$HOME/.local/state/claude-sessions}"
editsFile="$stateDir/.session-edits-$sessionId"
jsonlFile="$stateDir/.session-edits-$sessionId.jsonl"

# Extract tool name for JSONL
toolName=$(echo "$data" | jq -r '.tool_name // "unknown"' 2>/dev/null)

# Plain-text: keep one entry per path for session ownership lookup.
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
