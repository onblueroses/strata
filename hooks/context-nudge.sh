#!/usr/bin/env bash
# Context nudge - fires on UserPromptSubmit
# Counts messages per session, nudges to /context-save before compaction hits

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

# First nudge at 40, then every 25 after
if [ "$count" -eq 40 ] || { [ "$count" -gt 40 ] && [ $(( (count - 40) % 25 )) -eq 0 ]; }; then
    msg="[$count messages] You have rich context right now. Consider running /context-save before compaction hits."
    printf '%s\n' "$msg" | bash "$STRATA_HOME/hooks/lib-ledger.sh" context-nudge "$sessionId" >/dev/null 2>&1 || true
    echo "$msg"
fi

exit 0
