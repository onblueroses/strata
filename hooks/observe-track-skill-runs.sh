#!/usr/bin/env bash
# PostToolUse hook: logs skill invocations to JSONL for load tracking.#
# Records which skills were invoked and whether they loaded successfully.
# Does NOT track downstream success (whether the skill's instructions
# produced good results) - that happens over the conversation, not in the
# tool result. This tracks invocation frequency and load failures only.
#
# Query with:
#   jq -s 'group_by(.skill) | map({skill: .[0].skill, invocations: length})' \
#     ~/$STATE_DIR/skill-runs.jsonl

stdinContent=""
if [ ! -t 0 ]; then
    stdinContent=$(cat)
fi
[ -z "$stdinContent" ] && exit 0

data=$(echo "$stdinContent" | jq '.' 2>/dev/null) || exit 0

toolName=$(echo "$data" | jq -r '.tool_name // empty' 2>/dev/null)
[ "$toolName" != "Skill" ] && exit 0

skillName=$(echo "$data" | jq -r '.tool_input.skill // empty' 2>/dev/null)
[ -z "$skillName" ] && exit 0

# Check if the tool call itself errored (skill file not found, parse error, etc.)
# This does NOT reflect whether the skill's instructions led to good output.
isError=$(echo "$data" | jq -r '.tool_result.is_error // empty' 2>/dev/null)
loaded=true
if [ "$isError" = "true" ]; then
    loaded=false
fi

sessionId="default"
sid=$(echo "$data" | jq -r '.session_id // empty' 2>/dev/null)
if [ -n "$sid" ]; then
    sessionId="${sid:0:8}"
fi

stateDir="$STATE_DIR"

ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

event=$(jq -nc \
    --arg skill "$skillName" \
    --argjson loaded "$loaded" \
    --arg sid "$sessionId" \
    --arg ts "$ts" \
    '{skill: $skill, loaded: $loaded, sid: $sid, ts: $ts}')

echo "$event" >> "$stateDir/skill-runs.jsonl"

exit 0
