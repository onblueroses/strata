#!/usr/bin/env bash
# PreToolUse hook: auto-approve inert .claude/ documentation edits only.
set -uo pipefail

jsonInput=$(cat)
toolName=$(echo "$jsonInput" | jq -r '.tool_name // empty' 2>/dev/null)

case "$toolName" in
    Write|Edit)
        filePath=$(echo "$jsonInput" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
        case "$filePath" in
            .claude/*|*/.claude/*) ;;
            *) exit 0 ;;
        esac

        case "$filePath" in
            .claude/hooks/*|*/.claude/hooks/*|\
            .claude/agents/*|*/.claude/agents/*|\
            .claude/commands/*|*/.claude/commands/*|\
            *.json|*.jsonc|*.sh|*.bash|*.zsh|*.fish|*.py|*.js|*.ts|*.mjs|*.cjs|*.yaml|*.yml|*.toml)
                echo "BLOCKED: .claude configuration and executable edits require explicit approval." >&2
                exit 2
                ;;
            *.md|*.markdown|*.txt)
                echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"Auto-approved inert .claude documentation edit"}}'
                ;;
            *)
                echo "BLOCKED: only inert .claude documentation edits can be auto-approved." >&2
                exit 2
                ;;
        esac
        ;;
esac
