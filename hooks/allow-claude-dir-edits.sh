#!/usr/bin/env bash
# PreToolUse hook: auto-approve Write/Edit operations targeting .claude/ directory.
# Bypasses the protected directory prompt for .claude/ files.

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
