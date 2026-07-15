#!/usr/bin/env bash
# SessionStart hook: injects sibling session awareness.
# Summarizes what other active sessions are working on (project + intent),
# not raw file lists. Helps agents coordinate at task level.

stateDir="$STATE_DIR"
dailyDir="${KB_DIR:-$HOME/workspace}/daily"
today=$(date +%Y-%m-%d)

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

# Pre-build daily note lookup: map session IDs to note filenames (one find, not N)
declare -A dailyNotes
while IFS= read -r note; do
    [ -f "$note" ] || continue
    dailyNotes["$note"]=1
done < <(find "$dailyDir" -maxdepth 1 -name "${today}-*.json" 2>/dev/null)

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

    # Extract primary project from most common path prefix
    project=$(echo "$fileList" | grep -oP "(?<=${KB_DIR}/projects/)[^/]+|(?<=${KB_DIR}/areas/)[^/]+" | sort | uniq -c | sort -rn | head -1 | awk '{print $2}')
    if [ -z "$project" ]; then
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
        [ -n "$dominantGitRoot" ] && project=$(basename -- "$dominantGitRoot" 2>/dev/null)
    fi
    [ -z "$project" ] && project="(config/misc)"

    # Look up session name from pre-fetched daily notes
    sessionName=""
    for note in "${!dailyNotes[@]}"; do
        if [[ "$note" == *"-${sessionId}.json" ]]; then
            base=$(basename "$note" .json)
            sessionName=$(echo "$base" | sed "s/^${today}-//;s/-${sessionId}$//")
            [ "$sessionName" = "unnamed" ] && sessionName=""
            [ "$sessionName" = "auto-summarized" ] && sessionName=""
            break
        fi
    done

    line="  $sessionId"
    [ -n "$sessionName" ] && line+=" ($sessionName)"
    line+=" - $project, $fileCount files, ${ageMin}m ago"

    siblingOutput+="$line"$'\n'
    siblingCount=$((siblingCount + 1))
done < <(find "$stateDir" -maxdepth 1 -name '.session-edits-*' -not -name '*.jsonl' -mmin -60 2>/dev/null)

if [ "$siblingCount" -gt 0 ]; then
    echo "SIBLING SESSIONS ($siblingCount active):"
    echo "$siblingOutput"
fi

exit 0
