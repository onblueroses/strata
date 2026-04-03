#!/usr/bin/env bash
# Save context before compaction for post-compaction recovery.
# Event: PreCompact
# Config: {"hooks":{"PreCompact":[{"hooks":[{"type":"command","command":"hooks/context-pre-compaction-save.sh"}]}]}}

STRATA_STATE_DIR="${STRATA_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/strata}"

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

# Session-specific save file to avoid collisions between concurrent instances
mkdir -p "$STRATA_STATE_DIR"
saveFile="$STRATA_STATE_DIR/auto-context-save.md"
windowFile=""
if [ -n "$sessionId" ]; then
    saveFile="$STRATA_STATE_DIR/auto-context-save-$sessionId.md"
    windowFile="$STRATA_STATE_DIR/auto-context-save-$sessionId-w$windowNum.md"
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

# Find active spec files
specDir="$STRATA_STATE_DIR/specs"
specContent="(no active specs)"
if [ -d "$specDir" ]; then
    specEntries=()
    for spec in "$specDir/"*.md; do
        [ -f "$spec" ] || continue
        raw=$(cat "$spec" 2>/dev/null)
        [ -z "$raw" ] && continue
        if echo "$raw" | grep -qE 'Status:\s*(in-progress|planning)'; then
            specName=$(basename "$spec")
            # Extract Current Step section
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
jsonlFile="$STRATA_STATE_DIR/session-events-$sessionId.jsonl"
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

## Recovery
Run \`/context-resume\` or read this file to restore context.
Transcript backup: $transcriptPath
SAVEEOF

if [ -n "$windowFile" ]; then
    cp "$saveFile" "$windowFile"
fi

# Backup transcript if path provided
if [ -n "$transcriptPath" ] && [ -f "$transcriptPath" ]; then
    backupDir="$STRATA_STATE_DIR/transcript-backups"
    mkdir -p "$backupDir"
    backupName="pre-compaction-$(echo "$timestamp" | tr ' :' '--').jsonl"
    cp "$transcriptPath" "$backupDir/$backupName"

    # Keep only last 5 backups
    ls -1t "$backupDir"/pre-compaction-*.jsonl 2>/dev/null | tail -n +6 | while read -r f; do
        rm -f "$f"
    done
fi

# Resume directive - stdout becomes system-reminder post-compaction
uncommittedCount=0
if [ -n "$gitStatus" ]; then
    uncommittedCount=$(echo "$gitStatus" | wc -l | tr -d '[:space:]')
fi
jsonlInfo="No event log"
if [ "$jsonlEventCount" -gt 0 ]; then
    jsonlInfo="Event log: $STRATA_STATE_DIR/session-events-$sessionId.jsonl ($jsonlEventCount events)"
fi

cat << RESUMEEOF
## Session Resume
Session: $sessionId | Window: $windowNum | CWD: $cwd
Branch: $gitBranch | Uncommitted: $uncommittedCount files
Active specs: $specContent
$jsonlInfo
Auto-save: $STRATA_STATE_DIR/auto-context-save-$sessionId.md

RESUME: Read $STRATA_STATE_DIR/session-events-$sessionId.jsonl and any active specs to restore context. Continue from where you left off.
RESUMEEOF

exit 0
