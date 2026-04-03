#!/usr/bin/env bash
# Count messages per session, nudge to save context before compaction.
# Event: UserPromptSubmit
# Config: {"hooks":{"UserPromptSubmit":[{"hooks":[{"type":"command","command":"hooks/context-nudge.sh"}]}]}}

hookData=""
if [ ! -t 0 ]; then
    hookData=$(cat)
fi

sessionId="default"
if [ -n "$hookData" ]; then
    sid=$(echo "$hookData" | jq -r '.session_id // empty' 2>/dev/null)
    if [ -n "$sid" ]; then
        sessionId="${sid:0:8}"
    fi
fi

counterFile="/tmp/claude-msg-counter-$sessionId.txt"

count=0
if [ -f "$counterFile" ]; then
    count=$(cat "$counterFile" 2>/dev/null | tr -d '[:space:]')
    # Ensure it's a number
    if ! [[ "$count" =~ ^[0-9]+$ ]]; then
        count=0
    fi
fi
count=$((count + 1))
printf '%d' "$count" > "$counterFile"

# First nudge at 20, then every 15 after
if [ "$count" -eq 20 ] || { [ "$count" -gt 20 ] && [ $(( (count - 20) % 15 )) -eq 0 ]; }; then
    echo "[$count messages] You have rich context right now. Consider running /context-save before compaction hits."
fi

exit 0
