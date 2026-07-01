#!/usr/bin/env bash
# PostToolUse hook: runs fast language checks after Claude edits Python, TS/JS, and Rust files.
# Reads file path from stdin JSON (tool_input.file_path). Outputs issues for Claude to see.

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

dir=$(dirname "$filePath")
ext="${filePath##*.}"
ext=$(echo ".$ext" | tr '[:upper:]' '[:lower:]')
issues=()

# This hook runs automatically after edits; keep it to tools that do not execute repo-controlled code.

find_up() {
    local start="$1"
    local marker="$2"
    local current="$start"

    while [ -n "$current" ] && [ "$current" != "/" ]; do
        if [ -f "$current/$marker" ]; then
            echo "$current"
            return 0
        fi
        current=$(dirname "$current")
    done

    if [ -f "/$marker" ]; then
        echo "/"
        return 0
    fi

    return 1
}

# -- Python ----------------------------------------------------------------
if [ "$ext" = ".py" ]; then
    if command -v sloppylint &>/dev/null; then
        result=$(sloppylint "$filePath" 2>&1)
        if [ -n "$result" ]; then
            issues+=("sloppylint:"$'\n'"$result")
        fi
    fi

    if command -v ruff &>/dev/null; then
        if ! result=$(ruff check --fix "$filePath" 2>&1); then
            issues+=("ruff check:"$'\n'"$result")
        fi
        if ! result=$(ruff format "$filePath" 2>&1); then
            issues+=("ruff format:"$'\n'"$result")
        fi
    fi

    if command -v pyright &>/dev/null; then
        if ! result=$(pyright "$filePath" 2>&1); then
            issues+=("pyright:"$'\n'"$result")
        fi
    fi

# -- TypeScript / JavaScript -----------------------------------------------
elif [[ "$ext" =~ ^\.(ts|tsx|js|jsx|mjs|cjs)$ ]]; then
    tsconfigRoot=$(find_up "$dir" "tsconfig.json" || true)
    projectRoot="$dir"
    if [ -n "$tsconfigRoot" ]; then
        projectRoot="$tsconfigRoot"
    fi

    if [[ "$ext" =~ ^\.(ts|tsx)$ ]] && command -v tsgo &>/dev/null && [ -f "$projectRoot/tsconfig.json" ]; then
        if ! result=$(cd "$projectRoot" && tsgo --noEmit 2>&1); then
            issues+=("tsgo:"$'\n'"$result")
        fi
    fi

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
