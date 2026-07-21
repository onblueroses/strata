#!/usr/bin/env bash
# Pre-compaction auto-save
# Runs async before context compaction - captures state so nothing is lost
# Output goes to $STATE_DIR/auto-context-save.md for post-compaction recovery

timestamp=$(date +"%Y-%m-%d %H:%M")

# Read hook JSON from stdin
hookData=""
if [ ! -t 0 ]; then
    hookData=$(cat)
fi

trigger="unknown"
transcriptPath=""
cwd="$HOME"
sessionId=""

if [ -n "$hookData" ]; then
    trigger=$(echo "$hookData" | jq -r '.trigger // "unknown"' 2>/dev/null)
    transcriptPath=$(echo "$hookData" | jq -r '.transcript_path // empty' 2>/dev/null)
    cwdVal=$(echo "$hookData" | jq -r '.cwd // empty' 2>/dev/null)
    [ -n "$cwdVal" ] && cwd="$cwdVal"
    sid=$(echo "$hookData" | jq -r '.session_id // empty' 2>/dev/null)
    if [ -n "$sid" ]; then
        sessionId="${sid:0:8}"
    fi
fi

# Track compaction window number per session
windowNum=1
if [ -n "$sessionId" ]; then
    windowCounterFile="/tmp/claude-compact-window-$sessionId.txt"
    if [ -f "$windowCounterFile" ]; then
        prev=$(cat "$windowCounterFile" 2>/dev/null | tr -d '[:space:]')
        [[ "$prev" =~ ^[0-9]+$ ]] && windowNum=$((prev + 1))
    fi
    printf '%d' "$windowNum" > "$windowCounterFile"
fi

# Session-specific save file to avoid collisions between concurrent instances.
# IMPORTANT: hook writes to a -hook.md path, NOT the same file the /context-save
# skill writes to (auto-context-save-{sid}.md). The skill-written file holds rich
# semantic content (Goal, Critical Context, Decisions) the model composed; the hook
# would otherwise clobber it. Both files coexist; /context-resume reads both.
stateDir="$STATE_DIR"
saveFile="$stateDir/auto-context-save-hook.md"
windowFile=""
if [ -n "$sessionId" ]; then
    saveFile="$stateDir/auto-context-save-$sessionId-hook.md"
    windowFile="$stateDir/auto-context-save-$sessionId-hook-w$windowNum.md"
fi

# Gather git state
gitBranch=""
gitStatus=""
gitLog=""
gitDiffStat=""
if [ -d "$cwd" ]; then
    gitBranch=$(git -C "$cwd" branch --show-current 2>/dev/null)
    gitStatus=$(git -C "$cwd" status --short 2>/dev/null | head -15)
    gitLog=$(git -C "$cwd" log --oneline -5 2>/dev/null)
    gitDiffStat=$(git -C "$cwd" diff --stat 2>/dev/null | head -15)
    [ -z "$gitBranch" ] && gitBranch="(not a git repo)"
fi

# Find today's daily notes (JSON format) - only include notes with summaries
today=$(date +%Y-%m-%d)
dailyContent=""
dailyDir="${KB_DIR:-$HOME/workspace}/daily"
if [ -d "$dailyDir" ]; then
    entries=()
    for note in "$dailyDir/$today-"*.json; do
        [ -f "$note" ] || continue
        raw=$(cat "$note" 2>/dev/null)
        if [ -n "$raw" ]; then
            summary=$(echo "$raw" | jq -r '.summary // empty' 2>/dev/null)
            if [ -n "$summary" ]; then
                entries+=("$raw")
            fi
        fi
    done
    if [ ${#entries[@]} -eq 0 ]; then
        dailyContent="(no completed sessions today)"
    else
        dailyContent=""
        for i in "${!entries[@]}"; do
            [ "$i" -gt 0 ] && dailyContent+=$'\n---\n'
            dailyContent+="${entries[$i]}"
        done
    fi
fi

# Find active spec files
specDir="$STATE_DIR/specs"
specContent="(no active specs)"
if [ -d "$specDir" ]; then
    specEntries=()
    for spec in "$specDir/"*.md; do
        [ -f "$spec" ] || continue
        raw=$(cat "$spec" 2>/dev/null)
        [ -z "$raw" ] && continue
        if echo "$raw" | grep -qE 'Status:\s*(in-progress|planning)'; then
            specName=$(basename "$spec")
            # Extract Current Step section - get first line after ## >> Current Step
            step=$(echo "$raw" | sed -n '/^## >> Current Step/,/^## /{ /^## >> Current Step/d; /^## /d; p; }' | head -1 | sed 's/^[[:space:]]*//')
            if [ -n "$step" ]; then
                specEntries+=("- \`$specName\`: $step")
            else
                specEntries+=("- \`$specName\`: (no current step)")
            fi
        fi
    done
    if [ ${#specEntries[@]} -gt 0 ]; then
        specContent=$(printf '%s\n' "${specEntries[@]}")
    fi
fi

# Append compaction event to JSONL event log
jsonlFile="$stateDir/session-events-$sessionId.jsonl"
jsonlEventCount=0
if [ -n "$sessionId" ]; then
    ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    compactEvent=$(jq -nc \
        --arg type "compaction" \
        --arg ts "$ts" \
        --arg sid "$sessionId" \
        --argjson window "$windowNum" \
        --arg cwd "$cwd" \
        '{type: $type, ts: $ts, sid: $sid, window: $window, cwd: $cwd}')
    echo "$compactEvent" >> "$jsonlFile"
    if [ -f "$jsonlFile" ]; then
        jsonlEventCount=$(wc -l < "$jsonlFile" | tr -d '[:space:]')
    fi
fi

# Build save file
cat > "$saveFile" << SAVEEOF
# Auto-Context Save
Saved: $timestamp
Trigger: $trigger (compaction)
Session ID: $sessionId
Working directory: $cwd

IMPORTANT: This save was created before /end ran. The current session's daily note may be incomplete or missing summary/decisions. Use /context-resume to restore full state.

## Active Specs
$specContent
READ THESE FIRST after compaction. The >> Current Step section tells you where you are.

## Git State
Branch: $gitBranch
$gitStatus

### Recent Commits
$gitLog

### Uncommitted Changes
$gitDiffStat

## Today's Daily Notes
$dailyContent

## Recovery
Run \`/context-resume\` or read this file to restore context.
Transcript backup: $transcriptPath
SAVEEOF

if [ -n "$windowFile" ]; then
    cp "$saveFile" "$windowFile"
fi

# Backup transcript if path provided
if [ -n "$transcriptPath" ] && [ -f "$transcriptPath" ]; then
    backupDir="$STRATA_HOME/transcript-backups"
    mkdir -p "$backupDir"
    backupName="pre-compaction-$(echo "$timestamp" | tr ' :' '--').jsonl"
    cp "$transcriptPath" "$backupDir/$backupName"

    # Keep only last 5 backups
    ls -1t "$backupDir"/pre-compaction-*.jsonl 2>/dev/null | tail -n +6 | while read -r f; do
        rm -f "$f"
    done
fi

# Cleanup 1: keep only the 3 most recent per-window hook copies for THIS session.
# Window copies (-hook-wN.md) stay <24h in a long live session, so the age-out below never
# fires on them and they accumulate. Keep-3 bounds growth regardless of session length; the
# ageless main copy (-hook.md, no -wN) uses a different glob and is untouched.
if [ -n "$sessionId" ]; then
    ls -1t "$stateDir/auto-context-save-$sessionId-hook-w"*.md 2>/dev/null \
        | tail -n +4 \
        | while IFS= read -r f; do rm -f "$f"; done
fi

# Cleanup 2: age out saves left by OTHER / dead sessions (>24h). Skip this session's main save
# and its window copies — Cleanup 1 owns those.
find "$stateDir" -maxdepth 1 -name "auto-context-save*.md" -mmin +1440 \
    ! -path "$saveFile" ! -name "auto-context-save-$sessionId-hook-w*.md" -delete 2>/dev/null

# Clean up JSONL event logs older than 24 hours (from other sessions)
find "$stateDir" -maxdepth 1 -name "session-events-*.jsonl" -mmin +1440 ! -name "session-events-$sessionId.jsonl" -delete 2>/dev/null

# Stdout removed - was dead code. PreCompact is async, stdout either gets compacted
# away or isn't processed. Recovery now handled by session-post-compaction-restore.sh
# (SessionStart hook, sync). Removed code preserved at ~/to-delete/pre-compaction-stdout-block.sh

exit 0
