#!/usr/bin/env bash
# PreToolUse hook: auto-approve inert .claude/ documentation edits only.
set -uo pipefail

jsonInput=$(cat)
toolName=$(echo "$jsonInput" | jq -r '.tool_name // empty' 2>/dev/null)

is_protected_claude_surface() {
    local path="$1"

    case "$path" in
        .claude/hooks/*|*/.claude/hooks/*|\
        .claude/agents/*|*/.claude/agents/*|\
        .claude/commands/*|*/.claude/commands/*|\
        .claude/settings*|*/.claude/settings*|\
        *.json|*.jsonc|*.sh|*.bash|*.zsh|*.fish|*.py|*.js|*.ts|*.mjs|*.cjs|*.yaml|*.yml|*.toml)
            return 0
            ;;
    esac

    return 1
}

case "$toolName" in
    Write|Edit)
        filePath=$(echo "$jsonInput" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
        case "$filePath" in
            .claude/*|*/.claude/*) ;;
            *) exit 0 ;;
        esac

        if is_protected_claude_surface "$filePath"; then
            echo "BLOCKED: .claude configuration and executable edits require explicit approval." >&2
            exit 2
        fi

        case "$filePath" in
            *.md|*.markdown|*.txt)
                canonicalPath=$(realpath -m -- "$filePath" 2>/dev/null || readlink -f -- "$filePath" 2>/dev/null || printf '%s\n' "$filePath")
                case "$canonicalPath" in
                    .claude/*|*/.claude/*) ;;
                    *)
                        echo "BLOCKED: only inert .claude documentation edits can be auto-approved." >&2
                        exit 2
                        ;;
                esac

                if [ -L "$filePath" ] || is_protected_claude_surface "$canonicalPath"; then
                    echo "BLOCKED: .claude configuration and executable edits require explicit approval." >&2
                    exit 2
                fi

                echo '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"Auto-approved inert .claude documentation edit"}}'
                ;;
            *)
                echo "BLOCKED: only inert .claude documentation edits can be auto-approved." >&2
                exit 2
                ;;
        esac
        ;;
esac
