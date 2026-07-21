#!/usr/bin/env bash
# PostToolUse hook: silently auto-fixes formatting/lint after Claude edits Python, TS/JS, and
# Rust files (ruff --fix + format, biome --write, rustfmt). Reads file path from stdin JSON
# (tool_input.file_path). Fixes are applied in place, non-reverting.
# The model NEVER sees this hook's stdout: on a PostToolUse event exit-1 stdout goes to the
# user, not to Claude. So the diagnostic-only checkers (sloppylint, pyright, tsgo --noEmit)
# were removed 2026-07-21 — they paid up to 15s of latency reporting errors the model could
# not read. Only the silent auto-fixers remain; any error a fixer cannot fix is surfaced to
# the USER via exit 1 (never to the model).

stdinContent=""
if [ ! -t 0 ]; then
    stdinContent=$(cat)
fi
[ -z "$stdinContent" ] && exit 0

data=$(echo "$stdinContent" | jq '.' 2>/dev/null) || exit 0

filePath=$(echo "$data" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$filePath" ] && exit 0

if [[ "$filePath" != /* ]]; then
    filePath="$(pwd)/$filePath"
fi

[ -f "$filePath" ] || exit 0

ext="${filePath##*.}"
ext=$(echo ".$ext" | tr '[:upper:]' '[:lower:]')
issues=()

# This hook runs automatically after edits; keep it to tools that do not execute repo-controlled code.

# -- Python ----------------------------------------------------------------
if [ "$ext" = ".py" ]; then
    if command -v ruff &>/dev/null; then
        if ! result=$(ruff check --fix "$filePath" 2>&1); then
            issues+=("ruff check:"$'\n'"$result")
        fi
        if ! result=$(ruff format "$filePath" 2>&1); then
            issues+=("ruff format:"$'\n'"$result")
        fi
    fi

# -- TypeScript / JavaScript -----------------------------------------------
elif [[ "$ext" =~ ^\.(ts|tsx|js|jsx|mjs|cjs)$ ]]; then
    if command -v biome &>/dev/null; then
        if ! result=$(biome check --write --no-errors-on-unmatched "$filePath" 2>&1); then
            issues+=("biome:"$'\n'"$result")
        fi
    fi

# -- Rust ------------------------------------------------------------------
elif [ "$ext" = ".rs" ]; then
    if command -v rustfmt &>/dev/null; then
        if ! result=$(rustfmt "$filePath" 2>&1); then
            issues+=("rustfmt:"$'\n'"$result")
        fi
    fi
fi

# -- Output ----------------------------------------------------------------
if [ ${#issues[@]} -gt 0 ]; then
    fileName=$(basename "$filePath")
    echo "Lint issues in ${fileName}:"
    for issue in "${issues[@]}"; do
        echo "$issue"
        echo ""
    done
    exit 1
fi

exit 0
