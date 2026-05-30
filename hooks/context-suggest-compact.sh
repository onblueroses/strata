#!/usr/bin/env bash
# Counts ALL tool calls per session, suggests /compact at threshold.
# Fires on PostToolUse for all tools (moved from PreToolUse Edit|Write only).
# Pattern from: everything-claude-code (tool-call-compaction-trigger)

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

# Counter file per session (in /tmp to auto-clean on reboot)
counterFile="/tmp/claude-compact-counter-$sessionId.txt"
count=0
if [ -f "$counterFile" ]; then
    count=$(cat "$counterFile" 2>/dev/null | tr -d '[:space:]')
    [[ "$count" =~ ^[0-9]+$ ]] || count=0
fi
count=$((count + 1))
printf '%d' "$count" > "$counterFile"

# Suggest at 50 calls, then every 25 after
if [ "$count" -eq 50 ]; then
    echo "[$count tool calls this session] Consider running /compact if you're between tasks or transitioning phases."
elif [ "$count" -gt 50 ] && [ $(( (count - 50) % 25 )) -eq 0 ]; then
    echo "[$count tool calls this session] Context may be stale - consider /compact if starting new work."
fi

exit 0
