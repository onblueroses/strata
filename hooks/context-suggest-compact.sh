#!/usr/bin/env bash
# Count tool calls per session, suggest compaction at thresholds.
# Event: PostToolUse (Edit, Write, Bash, Agent, Skill)
# Config: {"hooks":{"PostToolUse":[{"hooks":[{"type":"command","command":"hooks/context-suggest-compact.sh"}]}]}}

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
