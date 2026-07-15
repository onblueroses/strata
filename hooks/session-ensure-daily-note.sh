#!/usr/bin/env bash
# Create JSON daily note stub for this session

STRATA_HOME="${STRATA_HOME:-$HOME/.strata}"
KB_DIR="${KB_DIR:-$STRATA_HOME/workspace}"
STATE_DIR="${STATE_DIR:-$KB_DIR/state}"

dailyDir="$KB_DIR/daily"
today=$(date +%Y-%m-%d)

mkdir -p "$dailyDir"

# Read session ID from JSON stdin (Claude Code passes hook input as JSON)
sessionId="00000000"
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

# Default name
sessionName="unnamed"

dailyFile="$dailyDir/$today-$sessionName-$sessionId.json"

# Only create if no file with this session ID exists today
existing=$(find "$dailyDir" -maxdepth 1 -name "$today-*-$sessionId.json" 2>/dev/null)
if [ -z "$existing" ]; then
    projectDir="${CLAUDE_WORKING_DIRECTORY:-$HOME}"
    startedTime=$(date +%H:%M)

    jq -n \
        --arg date "$today" \
        --arg session_id "$sessionId" \
        --arg session_name "$sessionName" \
        --arg project_dir "$projectDir" \
        --arg started "$startedTime" \
        '{
            date: $date,
            session_id: $session_id,
            session_name: $session_name,
            project_dir: $project_dir,
            started: $started,
            ended: null,
            summary: null,
            decisions: [],
            outputs: [],
            entities_touched: [],
            tags: [],
            takeaway: null
        }' > "$dailyFile"
fi

# Cleanup: delete stubs with null summaries older than 1 day
find "$dailyDir" -maxdepth 1 -name "*.json" -mtime +1 2>/dev/null | while read -r f; do
    summary=$(jq -r '.summary // empty' "$f" 2>/dev/null)
    if [ -z "$summary" ]; then
        rm -f "$f"
    fi
done

echo "$dailyFile"
