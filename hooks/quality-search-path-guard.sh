#!/usr/bin/env bash
# Warn when Glob or Grep targets the entire home directory (often times out).
# Event: PreToolUse (Glob, Grep)
# Config: {"hooks":{"PreToolUse":[{"matcher":{"tool_name":"Glob|Grep"},"hooks":[{"type":"command","command":"hooks/quality-search-path-guard.sh"}]}]}}

stdinContent=""
if [ ! -t 0 ]; then
    stdinContent=$(cat)
fi
[ -z "$stdinContent" ] && exit 0

data=$(echo "$stdinContent" | jq '.' 2>/dev/null) || exit 0

searchPath=$(echo "$data" | jq -r '.tool_input.path // empty' 2>/dev/null)
# Null/empty path means current working directory - check if that's home
if [ -z "$searchPath" ]; then
    searchPath=$(echo "$data" | jq -r '.cwd // empty' 2>/dev/null)
fi
[ -z "$searchPath" ] && exit 0

# Normalize: lowercase, trim trailing slash
normalized=$(echo "$searchPath" | tr '[:upper:]' '[:lower:]' | sed 's:/*$::')

# Match home directory exactly (not subdirectories)
homeNormalized=$(echo "$HOME" | tr '[:upper:]' '[:lower:]' | sed 's:/*$::')
case "$normalized" in
    "$homeNormalized")
        echo "BROAD SEARCH: Searching the entire home directory often times out. Consider a more specific path (e.g., a project directory)."
        ;;
esac

exit 0
