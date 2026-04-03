#!/usr/bin/env bash
# Auto-approve Write/Edit operations targeting .claude/ directory.
# Event: PreToolUse (Write, Edit)
# Config: {"hooks":{"PreToolUse":[{"matcher":{"tool_name":"Write|Edit"},"hooks":[{"type":"command","command":"hooks/allow-claude-dir-edits.sh"}]}]}}

jsonInput=$(cat)
toolName=$(echo "$jsonInput" | jq -r '.tool_name // empty' 2>/dev/null)

case "$toolName" in
    Write|Edit)
        filePath=$(echo "$jsonInput" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
        if echo "$filePath" | grep -q '/\.claude/'; then
            echo '{"hookSpecificOutput":{"permissionDecision":"allow","permissionDecisionReason":"Auto-approved .claude/ edit"}}'
        fi
        ;;
esac
