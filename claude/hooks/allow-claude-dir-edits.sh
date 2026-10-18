#!/usr/bin/env bash
# PreToolUse hook: auto-approve Write/Edit operations targeting .claude/ directory.
# Bypasses the protected directory prompt for .claude/ files.

jsonInput=$(cat)
toolName=$(echo "$jsonInput" | jq -r '.tool_name // empty' 2>/dev/null)

case "$toolName" in
    Write|Edit)
        filePath=$(echo "$jsonInput" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
        # Edit/Write paths are relative to the Claude session cwd.  Resolve that input
        # path before classifying it; the hook must not require an absolute spelling.
        if [[ "$filePath" != /* ]]; then
            filePath="$PWD/$filePath"
        fi
        if [[ "$filePath" == */.claude || "$filePath" == */.claude/* ]]; then
            echo '{"hookSpecificOutput":{"permissionDecision":"allow","permissionDecisionReason":"Auto-approved .claude/ edit"}}'
        fi
        ;;
esac
