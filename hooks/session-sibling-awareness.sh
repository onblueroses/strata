#!/usr/bin/env bash
# SessionStart hook: injects sibling session awareness.
# Summarizes what other active sessions are working on (project + intent),
# not raw file lists. Helps agents coordinate at task level.

stateDir="$STATE_DIR"

# Get own session ID
stdinContent=""
if [ ! -t 0 ]; then
    stdinContent=$(cat)
fi

ownSessionId=""
if [ -n "$stdinContent" ]; then
    sid=$(echo "$stdinContent" | jq -r '.session_id // empty' 2>/dev/null)
    [ -n "$sid" ] && ownSessionId="${sid:0:8}"
fi

now=$(date +%s)
siblingOutput=""
siblingCount=0

while IFS= read -r editFile; do
    [ -f "$editFile" ] || continue

    fname=$(basename "$editFile")
    sessionId="${fname#.session-edits-}"
    [ "$sessionId" = "$ownSessionId" ] && continue

    fileList=$(cat "$editFile" 2>/dev/null) || continue
    [ -z "$fileList" ] && continue

    fileCount=$(echo "$fileList" | wc -l)
    mtime=$(stat -c %Y "$editFile" 2>/dev/null) || continue
    ageMin=$(( (now - mtime) / 60 ))

    # Extract the dominant git root from the edited paths.
    declare -A gitRootCounts=()
    dominantGitRoot=""
    dominantGitCount=0
    while IFS= read -r editedPath; do
        [ -n "$editedPath" ] || continue
        editedDir="$editedPath"
        [ -d "$editedDir" ] || editedDir=$(dirname -- "$editedPath" 2>/dev/null) || continue
        gitRoot=$(git -C "$editedDir" rev-parse --show-toplevel 2>/dev/null) || continue
        rootCount=${gitRootCounts["$gitRoot"]:-0}
        rootCount=$((rootCount + 1))
        gitRootCounts["$gitRoot"]=$rootCount
        if [ "$rootCount" -gt "$dominantGitCount" ]; then
            dominantGitRoot="$gitRoot"
            dominantGitCount=$rootCount
        fi
    done <<< "$fileList"
    project=""
    [ -n "$dominantGitRoot" ] && project=$(basename -- "$dominantGitRoot" 2>/dev/null)
    [ -z "$project" ] && project="(config/misc)"

    line="  $sessionId"
    line+=" - $project, $fileCount files, ${ageMin}m ago"

    siblingOutput+="$line"$'\n'
    siblingCount=$((siblingCount + 1))
done < <(find "$stateDir" -maxdepth 1 -name '.session-edits-*' -not -name '*.jsonl' -mmin -60 2>/dev/null)

if [ "$siblingCount" -gt 0 ]; then
    echo "SIBLING SESSIONS ($siblingCount active):"
    echo "$siblingOutput"
fi

exit 0
