#!/usr/bin/env bash
# PostToolUse hook (advisory): enriches Grep/Glob results with entity context.
# When a search targets a known project/area directory, appends a brief
# architectural context block from the entity's summary.md.
# Also surfaces matching memory file names.
# Max output: ~20 lines. Silent when no entity matches.

KB_BASE="${KB_DIR:-$HOME/workspace}"
STATE_BASE="${STATE_DIR:-$KB_BASE/state}"
MEMORY_DIR="${STATE_BASE}/memory/cards"

stdinContent=""
if [ ! -t 0 ]; then
    stdinContent=$(cat)
fi
[ -z "$stdinContent" ] && exit 0

data=$(echo "$stdinContent" | jq '.' 2>/dev/null) || exit 0

# Extract search path; fall back to cwd if empty
searchPath=$(echo "$data" | jq -r '.tool_input.path // empty' 2>/dev/null)
if [ -z "$searchPath" ]; then
    searchPath=$(echo "$data" | jq -r '.cwd // empty' 2>/dev/null)
fi
[ -z "$searchPath" ] && exit 0

# Normalize: resolve symlinks, strip trailing slash
searchPath=$(realpath "$searchPath" 2>/dev/null || echo "$searchPath")
searchPath="${searchPath%/}"

# Early exit for paths that are never project directories
case "$searchPath" in
    /tmp*|$HOME/.claude*|$HOME/.config*|$HOME/.local*|$HOME/.cache*)
        exit 0 ;;
esac

# Session dedup: don't re-inject context for the same entity within a session.
sessionId="default"
sid=$(echo "$data" | jq -r '.session_id // empty' 2>/dev/null)
[ -n "$sid" ] && sessionId="${sid:0:8}"
flagFile="/tmp/claude-enrich-search-$sessionId.txt"
touch "$flagFile" 2>/dev/null

# Session-level cache for summary path mentions.
# Maps entity names to paths mentioned in their summaries.
cacheFile="/tmp/claude-enrich-search-$sessionId.cache"

# Build cache if missing or older than 5 minutes
rebuild_cache=0
if [ ! -f "$cacheFile" ]; then
    rebuild_cache=1
else
    cacheAge=$(( $(date +%s) - $(stat -c %Y "$cacheFile" 2>/dev/null || echo 0) ))
    [ "$cacheAge" -gt 300 ] && rebuild_cache=1
fi

if [ "$rebuild_cache" -eq 1 ]; then
    : > "$cacheFile"
    for summaryFile in "$KB_BASE"/projects/*/summary.md "$KB_BASE"/areas/*/summary.md; do
        [ -f "$summaryFile" ] || continue
        entity="${summaryFile%/summary.md}"
        entity="${entity##*/}"
        # Extract all parenthesized paths from the summary (backtick-wrapped paths like `/home/...`)
        paths=$(grep -oP '`('"$HOME"'/[^`]+)`' "$summaryFile" | tr -d '`' | sort -u)
        if [ -n "$paths" ]; then
            while IFS= read -r p; do
                printf '%s\t%s\n' "$entity" "$p" >> "$cacheFile"
            done <<< "$paths"
        fi
    done
fi

# Map search path to an entity.
# Strategy: direct $KB_DIR/ match, then basename walk with validation, then cached path lookup.
find_entity() {
    local path="$1"

    # Direct match: path is under $KB_DIR/projects/ or $KB_DIR/areas/
    if [[ "$path" == "$KB_BASE/projects/"* ]]; then
        local rel="${path#$KB_BASE/projects/}"
        echo "${rel%%/*}"
        return 0
    fi
    if [[ "$path" == "$KB_BASE/areas/"* ]]; then
        local rel="${path#$KB_BASE/areas/}"
        echo "${rel%%/*}"
        return 0
    fi

    # Basename walk: check if any ancestor dirname matches an entity.
    # First ancestor match wins - if the directory basename is an entity name,
    # the search is almost certainly about that entity. Cache validation is
    # only needed for the fallback path-mention scan (ambiguous cases).
    local check="$path"
    for _ in 1 2 3 4; do
        local dirName=$(basename "$check")
        for base in "$KB_BASE/projects" "$KB_BASE/areas"; do
            if [ -f "$base/$dirName/summary.md" ]; then
                echo "$dirName"
                return 0
            fi
        done
        check=$(dirname "$check")
        [[ "$check" == "/" || "$check" == "." ]] && break
    done

    # Cached path lookup: find the entity whose mentioned path is the longest prefix.
    local bestEntity=""
    local bestLen=0
    while IFS=$'\t' read -r entity cachedPath; do
        if [[ "$path" == "$cachedPath"* ]]; then
            local len=${#cachedPath}
            if [ "$len" -gt "$bestLen" ]; then
                bestLen=$len
                bestEntity=$entity
            fi
        fi
    done < "$cacheFile"

    if [ -n "$bestEntity" ]; then
        echo "$bestEntity"
        return 0
    fi

    return 1
}

entityName=$(find_entity "$searchPath") || exit 0

# Session dedup check
if grep -qxF "$entityName" "$flagFile" 2>/dev/null; then
    exit 0
fi

# Find the summary.md
summaryFile=""
if [ -f "$KB_BASE/projects/$entityName/summary.md" ]; then
    summaryFile="$KB_BASE/projects/$entityName/summary.md"
elif [ -f "$KB_BASE/areas/$entityName/summary.md" ]; then
    summaryFile="$KB_BASE/areas/$entityName/summary.md"
fi
[ -z "$summaryFile" ] && exit 0

# Extract Architecture, Details, or Key Details section.
# Truncate each line to 120 chars and cap at 12 lines for brevity.
archSection=$(awk '
    /^## (Architecture|Details|Key Details)/ { found=1; next }
    found && /^## / { exit }
    found { print }
' "$summaryFile" | sed '/^[[:space:]]*$/d' | while IFS= read -r line; do
    if [ ${#line} -gt 120 ]; then
        echo "  ${line:0:117}..."
    else
        echo "  $line"
    fi
done | head -12)

# Extract Status line (first line after ## Status)
statusLine=$(awk '
    /^## Status/ { found=1; next }
    found && /^## / { exit }
    found && NF { print; exit }
' "$summaryFile")

# Find matching memory files (by entity name in filename or description).
# Uses cached frontmatter from context-memory-hint if available; else direct scan.
memMatches=()
if [ -d "$MEMORY_DIR" ]; then
    entityLower="${entityName,,}"
    entityPattern="${entityLower//-/[-_]}"
    for memFile in "$MEMORY_DIR"/*.md; do
        [ -f "$memFile" ] || continue
        memName=$(basename "$memFile")
        [[ "$memName" == "MEMORY.md" ]] && continue
        memLower="${memName,,}"
        if [[ "$memLower" =~ $entityPattern ]]; then
            memMatches+=("$memName")
            continue
        fi
        # Check description field (first 10 lines only)
        if head -10 "$memFile" | grep -qiF "$entityName" 2>/dev/null; then
            memMatches+=("$memName")
        fi
    done
fi

# Build output only if we have something useful
[ -z "$archSection" ] && [ -z "$statusLine" ] && [ ${#memMatches[@]} -eq 0 ] && exit 0

# Record entity as injected for this session
echo "$entityName" >> "$flagFile"

output="ENTITY CONTEXT [$entityName]:"
if [ -n "$statusLine" ]; then
    output+="\n  Status: $statusLine"
fi
if [ -n "$archSection" ]; then
    output+="\n  Architecture (from summary.md):\n$archSection"
fi
if [ ${#memMatches[@]} -gt 0 ]; then
    output+="\n  Related memories: ${memMatches[*]}"
fi

printf '%b' "$output"
exit 0
