#!/usr/bin/env bash
# Stop hook: rescues empty daily notes with a minimal auto-summary when /end wasn't run.
# Fires after verify-gate, before sync-life-repo.

sessionId="default"
jsonInput=""
if [ ! -t 0 ]; then
    jsonInput=$(cat)
fi
if [ -n "$jsonInput" ]; then
    sid=$(echo "$jsonInput" | jq -r '.session_id // empty' 2>/dev/null)
    if [ -n "$sid" ]; then
        sessionId="${sid:0:8}"
    fi
fi

[ "$sessionId" = "default" ] && exit 0

STRATA_HOME="${STRATA_HOME:-$HOME/.strata}"
KB_DIR="${KB_DIR:-$STRATA_HOME/workspace}"
STATE_DIR="${STATE_DIR:-$KB_DIR/state}"

dailyDir="$KB_DIR/daily"
today=$(date +%Y-%m-%d)

# Find today's daily note for this session
noteFile=$(find "$dailyDir" -maxdepth 1 -name "$today-*-$sessionId.json" 2>/dev/null | head -1)
[ -z "$noteFile" ] && exit 0

# Parse and check if summary is null
noteContent=$(cat "$noteFile" 2>/dev/null) || exit 0
summary=$(echo "$noteContent" | jq -r '.summary // empty' 2>/dev/null)
[ -n "$summary" ] && exit 0

# Build minimal summary from session artifacts
parts=()

# Check session edits file
editsFile="$STATE_DIR/.session-edits-$sessionId"
if [ -f "$editsFile" ]; then
    mapfile -t edits < <(grep -v '^\s*$' "$editsFile" 2>/dev/null)
    editCount=${#edits[@]}
    if [ "$editCount" -gt 0 ]; then
        # Get basenames
        fileNames=()
        for e in "${edits[@]}"; do
            fileNames+=("$(basename "$e")")
        done
        # Preview first 5
        preview=""
        for i in "${!fileNames[@]}"; do
            [ "$i" -ge 5 ] && break
            [ "$i" -gt 0 ] && preview+=", "
            preview+="${fileNames[$i]}"
        done
        if [ "$editCount" -gt 5 ]; then
            preview+=" (+$((editCount - 5)) more)"
        fi
        parts+=("Edited $editCount files: $preview")
    fi
fi

# Check session events file for commits
eventsFile="$STATE_DIR/session-events-$sessionId.jsonl"
if [ -f "$eventsFile" ]; then
    firstCommit=""
    while IFS= read -r line; do
        evtType=$(echo "$line" | jq -r '.type // empty' 2>/dev/null)
        if [ "$evtType" = "commit" ]; then
            msg=$(echo "$line" | jq -r '.msg // empty' 2>/dev/null)
            if [ -n "$msg" ]; then
                if [ ${#msg} -gt 60 ]; then
                    msg="${msg:0:60}..."
                fi
                firstCommit="$msg"
                break
            fi
        fi
    done < "$eventsFile"
    if [ -n "$firstCommit" ]; then
        parts+=("Committed: $firstCommit")
    fi
fi

if [ ${#parts[@]} -eq 0 ]; then
    parts+=("Short session, no tracked edits")
fi

# Join parts with ". "
summaryText="[auto] "
for i in "${!parts[@]}"; do
    [ "$i" -gt 0 ] && summaryText+=". "
    summaryText+="${parts[$i]}"
done
summaryText+=". No /end run."

# Update the daily note
updatedNote=$(echo "$noteContent" | jq \
    --arg summary "$summaryText" \
    '.summary = $summary | .session_name = "auto-summarized"')

echo "$updatedNote" > "$noteFile"

# Rename the file from *-unnamed-* to *-auto-summarized-*
noteBasename=$(basename "$noteFile")
newName=$(echo "$noteBasename" | sed 's/-unnamed-/-auto-summarized-/')
if [ "$newName" != "$noteBasename" ]; then
    newPath="$dailyDir/$newName"
    mv -f "$noteFile" "$newPath" 2>/dev/null
fi

exit 0
