#!/usr/bin/env bash
# Run linters on Python and JS/TS files after edits.
# Event: PostToolUse (Edit, Write)
# Config: {"hooks":{"PostToolUse":[{"matcher":{"tool_name":"Edit|Write"},"hooks":[{"type":"command","command":"hooks/quality-lint-on-write.sh"}]}]}}

stdinContent=""
if [ ! -t 0 ]; then
    stdinContent=$(cat)
fi
[ -z "$stdinContent" ] && exit 0

data=$(echo "$stdinContent" | jq '.' 2>/dev/null) || exit 0

filePath=$(echo "$data" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$filePath" ] && exit 0

# Resolve to absolute if relative
if [[ "$filePath" != /* ]]; then
    filePath="$(pwd)/$filePath"
fi

[ -f "$filePath" ] || exit 0

ext="${filePath##*.}"
ext=$(echo ".$ext" | tr '[:upper:]' '[:lower:]')

issues=()

# -- Python ----------------------------------------------------------------
if [ "$ext" = ".py" ]; then
    # sloppylint: AI-specific code slop detector
    if command -v sloppylint &>/dev/null; then
        result=$(sloppylint "$filePath" 2>&1)
        if [ -n "$result" ]; then
            issues+=("sloppylint:"$'\n'"$result")
        fi
    fi

    # ruff: fast linter with auto-fix
    if command -v ruff &>/dev/null; then
        result=$(ruff check --fix "$filePath" 2>&1)
        if [ $? -ne 0 ]; then
            issues+=("ruff:"$'\n'"$result")
        fi
    fi

# -- TypeScript / JavaScript -----------------------------------------------
elif [[ "$ext" =~ ^\.(ts|tsx|js|jsx|mjs|cjs)$ ]]; then
    # Walk up to find project root (where package.json lives)
    dir=$(dirname "$filePath")
    searchDir="$dir"
    projectRoot="$dir"
    while [ -n "$searchDir" ] && [ "$searchDir" != "/" ]; do
        if [ -f "$searchDir/package.json" ]; then
            projectRoot="$searchDir"
            break
        fi
        searchDir=$(dirname "$searchDir")
    done

    # Prefer local eslint, fall back to global
    eslintCmd=""
    localEslint="$projectRoot/node_modules/.bin/eslint"
    if [ -x "$localEslint" ]; then
        eslintCmd="$localEslint"
    elif command -v eslint &>/dev/null; then
        eslintCmd="eslint"
    fi

    if [ -n "$eslintCmd" ]; then
        result=$("$eslintCmd" --fix "$filePath" 2>&1)
        if [ $? -ne 0 ]; then
            issues+=("eslint:"$'\n'"$result")
        fi
    fi
fi

# -- Output -----------------------------------------------------------------
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
