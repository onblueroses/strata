#!/usr/bin/env bash
# observe-track-mcp-tools.sh — PostToolUse(mcp__.*) MCP tool-use logger.
#
# Q it answers: which MCP servers' tools actually get called (and how often)?
# Fills the one telemetry gap the observe-* family missed — edits, skills, and session
# events are already covered; MCP usage was not.
#
# MCP tool names are mcp__<server>__<tool>. Records {ts, sid, server, tool} for any tool
# whose name starts with mcp__. Invisible by design: no stdout, no stderr, always exit 0
# (fail-open). Sink lives at $STATE_DIR/mcp-tool-calls.jsonl, size-capped at 512 KB with
# one .1 rollover generation.
#
# Query with:
#   jq -s 'group_by(.server)|map({server:.[0].server,calls:length})|sort_by(-.calls)' \
#     "$STATE_DIR/mcp-tool-calls.jsonl"

stdinContent=""
if [ ! -t 0 ]; then
    stdinContent=$(cat)
fi
[ -z "$stdinContent" ] && exit 0

toolName=$(printf '%s' "$stdinContent" | jq -r '.tool_name // empty' 2>/dev/null)
case "$toolName" in
    mcp__*) : ;;
    *) exit 0 ;;
esac

# mcp__<server>__<tool> -> server is the segment between the first two "__".
rest="${toolName#mcp__}"
server="${rest%%__*}"

sid=$(printf '%s' "$stdinContent" | jq -r '.session_id // empty' 2>/dev/null)
sid="${sid:0:8}"
ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)

stateDir="${STATE_DIR:-}"
[ -z "$stateDir" ] && exit 0
f="$stateDir/mcp-tool-calls.jsonl"
maxBytes=524288
mkdir -p "$stateDir" 2>/dev/null || exit 0

# size-capped rotation: one .1 generation, ~1 MB ceiling.
if [ -f "$f" ]; then
    sz=$(stat -c%s "$f" 2>/dev/null || echo 0)
    [ "$sz" -gt "$maxBytes" ] && mv -f "$f" "$f.1" 2>/dev/null || true
fi

jq -nc --arg ts "$ts" --arg sid "$sid" --arg server "$server" --arg tool "$toolName" \
    '{ts:$ts, sid:$sid, server:$server, tool:$tool}' >> "$f" 2>/dev/null || true

exit 0
