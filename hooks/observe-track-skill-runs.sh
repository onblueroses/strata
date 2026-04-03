#!/usr/bin/env bash
# Log skill invocations to JSONL for load tracking.
# Event: PostToolUse (Skill)
# Config: {"hooks":{"PostToolUse":[{"matcher":{"tool_name":"Skill"},"hooks":[{"type":"command","command":"hooks/observe-track-skill-runs.sh"}]}]}}
#
# Query with:
#   jq -s 'group_by(.skill) | map({skill: .[0].skill, invocations: length})' \
#     "$STRATA_STATE_DIR/skill-runs.jsonl"

STRATA_STATE_DIR="${STRATA_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/strata}"

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

mkdir -p "$STRATA_STATE_DIR"

ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

event=$(jq -nc \
    --arg skill "$skillName" \
    --argjson loaded "$loaded" \
    --arg sid "$sessionId" \
    --arg ts "$ts" \
    '{skill: $skill, loaded: $loaded, sid: $sid, ts: $ts}')

echo "$event" >> "$STRATA_STATE_DIR/skill-runs.jsonl"

exit 0
