#!/usr/bin/env bash
# Post-compaction context restore.
# Fires on SessionStart after compaction. Reads save files from disk and outputs
# structured recovery context to stdout, which gets injected as system-reminder.
# MUST be sync (not async) - stdout injection requires synchronous execution.
# Event: SessionStart
# Config: {"hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"hooks/session-post-compaction-restore.sh","timeout":10000}]}]}}

STRATA_STATE_DIR="${STRATA_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/strata}"

# Read hook JSON from stdin
hookData=""
if [ ! -t 0 ]; then
    hookData=$(cat)
fi

# Parse session info
sessionId=""
cwd="$HOME"
triggerVal=""

if [ -n "$hookData" ]; then
    # Check both 'trigger' and 'source' - docs are ambiguous on field name
    triggerVal=$(echo "$hookData" | jq -r '.trigger // empty' 2>/dev/null)
    if [ -z "$triggerVal" ]; then
        triggerVal=$(echo "$hookData" | jq -r '.source // empty' 2>/dev/null)
    fi
    cwdVal=$(echo "$hookData" | jq -r '.cwd // empty' 2>/dev/null)
    [ -n "$cwdVal" ] && cwd="$cwdVal"
    sid=$(echo "$hookData" | jq -r '.session_id // empty' 2>/dev/null)
    if [ -n "$sid" ]; then
        sessionId="${sid:0:8}"
    fi
fi

# Only fire on compaction, exit silently for startup/resume/clear
if [ "$triggerVal" != "compact" ]; then
    exit 0
fi

# --- From here: compaction recovery only ---

stateDir="$STRATA_STATE_DIR"
specDir="$stateDir/specs"
output=""

# --- Section 1: Header/metadata ---
windowNum="?"
if [ -n "$sessionId" ]; then
    windowFile="/tmp/claude-compact-window-$sessionId.txt"
    if [ -f "$windowFile" ]; then
        windowNum=$(cat "$windowFile" 2>/dev/null | tr -d '[:space:]')
    fi
fi

gitBranch=""
if [ -d "$cwd" ]; then
    gitBranch=$(git -C "$cwd" branch --show-current 2>/dev/null)
fi
[ -z "$gitBranch" ] && gitBranch="(not a git repo)"

output="## Post-Compaction Recovery
Session: $sessionId | Window: $windowNum | CWD: $cwd
Branch: $gitBranch
"

# --- Section 2: Active specs (HIGHEST PRIORITY) ---
specOutput=""
specCount=0
if [ -d "$specDir" ]; then
    for spec in "$specDir/"*.md; do
        [ -f "$spec" ] || continue
        raw=$(cat "$spec" 2>/dev/null)
        [ -z "$raw" ] && continue
        if echo "$raw" | grep -qE 'Status:\s*(in-progress|planning)'; then
            specName=$(basename "$spec")
            specCount=$((specCount + 1))
            if [ "$specCount" -le 3 ]; then
                # Extract >> Current Step section (lines after heading until next ##)
                step=$(echo "$raw" | sed -n '/^## >> Current Step/,/^## /{ /^## >> Current Step/d; /^## /d; p; }' | head -3 | sed '/^$/d')
                if [ -n "$step" ]; then
                    specOutput+="- \`$specName\`: $step
"
                else
                    specOutput+="- \`$specName\`: (no current step)
"
                fi
            else
                specOutput+="- \`$specName\`: (name only, over limit)
"
            fi
        fi
    done
fi

if [ -n "$specOutput" ]; then
    output+="
### Active Specs (READ THESE FIRST)
$specOutput"
else
    output+="
### Active Specs
(none)
"
fi

# --- Section 3: JSONL event log tail ---
jsonlLines=25
jsonlFile="$stateDir/session-events-$sessionId.jsonl"
jsonlOutput=""
if [ -n "$sessionId" ] && [ -f "$jsonlFile" ]; then
    jsonlOutput=$(tail -n "$jsonlLines" "$jsonlFile" 2>/dev/null)
fi

if [ -n "$jsonlOutput" ]; then
    output+="
### Recent Events (last ${jsonlLines})
\`\`\`
$jsonlOutput
\`\`\`
"
fi

# --- Section 4: Save file extract ---
saveFile=""
if [ -n "$sessionId" ]; then
    saveFile="$stateDir/auto-context-save-$sessionId.md"
fi
# Fall back to most recent save file if session-specific not found
if [ ! -f "$saveFile" ]; then
    saveFile=$(ls -1t "$stateDir"/auto-context-save*.md 2>/dev/null | head -1)
fi

saveOutput=""
if [ -f "$saveFile" ]; then
    # Extract key sections: Active Specs, Git State
    saveOutput=$(sed -n '/^## Active Specs/,/^## /{/^## Active Specs/d; /^## /d; p;}' "$saveFile" 2>/dev/null | head -10)
    gitSection=$(sed -n '/^## Git State/,/^## /{/^## Git State/d; /^## /d; p;}' "$saveFile" 2>/dev/null | head -15)
    if [ -n "$gitSection" ]; then
        saveOutput+="
Git State:
$gitSection"
    fi
fi

if [ -n "$saveOutput" ]; then
    output+="
### From Save File
$saveOutput
"
fi

# --- Section 5: Uncommitted changes ---
gitStatus=""
if [ -d "$cwd" ]; then
    gitStatus=$(git -C "$cwd" status --short 2>/dev/null | head -10)
fi
if [ -n "$gitStatus" ]; then
    uncommittedCount=$(echo "$gitStatus" | wc -l | tr -d '[:space:]')
    output+="
### Uncommitted ($uncommittedCount files)
$gitStatus
"
fi

# --- Section 6: Directive ---
output+="
### Resume
Continue from where you left off. Active specs are authoritative - read them first.
Decisions in spec tables are settled - do not re-debate.
If this context seems incomplete, run /context-resume for full manual recovery.
"

# --- Character budget enforcement ---
charCount=${#output}
if [ "$charCount" -gt 9500 ]; then
    # Truncation pass 1: reduce JSONL to 10 lines
    if [ -n "$jsonlOutput" ] && [ -n "$sessionId" ] && [ -f "$jsonlFile" ]; then
        jsonlOutput=$(tail -n 10 "$jsonlFile" 2>/dev/null)
        # Rebuild output
        output="## Post-Compaction Recovery
Session: $sessionId | Window: $windowNum | CWD: $cwd
Branch: $gitBranch
"
        if [ -n "$specOutput" ]; then
            output+="
### Active Specs (READ THESE FIRST)
$specOutput"
        fi
        if [ -n "$jsonlOutput" ]; then
            output+="
### Recent Events (last 10, truncated)
\`\`\`
$jsonlOutput
\`\`\`
"
        fi
        if [ -n "$saveOutput" ]; then
            output+="
### From Save File
$saveOutput
"
        fi
        if [ -n "$gitStatus" ]; then
            output+="
### Uncommitted ($uncommittedCount files)
$gitStatus
"
        fi
        output+="
### Resume
Continue from where you left off. Active specs are authoritative - read them first.
Decisions in spec tables are settled - do not re-debate.
If this context seems incomplete, run /context-resume for full manual recovery.
"
    fi
fi

# Truncation pass 2: drop save file section if still over
charCount=${#output}
if [ "$charCount" -gt 9500 ]; then
    saveOutput=""
    # Rebuild without save section
    output="## Post-Compaction Recovery
Session: $sessionId | Window: $windowNum | CWD: $cwd
Branch: $gitBranch
"
    if [ -n "$specOutput" ]; then
        output+="
### Active Specs (READ THESE FIRST)
$specOutput"
    fi
    if [ -n "$jsonlOutput" ]; then
        output+="
### Recent Events (truncated)
\`\`\`
$jsonlOutput
\`\`\`
"
    fi
    if [ -n "$gitStatus" ]; then
        output+="
### Uncommitted ($uncommittedCount files)
$gitStatus
"
    fi
    output+="
### Resume
Continue from where you left off. Active specs are authoritative - read them first.
Decisions in spec tables are settled - do not re-debate.
Save file available at: $saveFile (read manually if needed)
If this context seems incomplete, run /context-resume for full manual recovery.
"
fi

printf '%s' "$output"
exit 0
