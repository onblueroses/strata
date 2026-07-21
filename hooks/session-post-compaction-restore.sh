#!/usr/bin/env bash
# Post-compaction context restore
# Fires on SessionStart after compaction. Reads save files from disk and outputs
# structured recovery context to stdout, which gets injected as system-reminder.
# MUST be sync (not async) - stdout injection requires synchronous execution.

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

stateDir="$STATE_DIR"
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

# --- Section 2b: Active dmux orchestration ---
orchOutput=""
# Check cwd and common project locations for orchestration logs
for orchPath in "$cwd/.dmux/orchestration.md" $HOME/Work/*/.dmux/orchestration.md; do
    if [ -f "$orchPath" ]; then
        projName=$(basename "$(dirname "$(dirname "$orchPath")")")
        if grep -q '^## Wave' "$orchPath"; then
            orchOutput+="- \`$projName\`: $(grep '^## Wave' "$orchPath" | tail -1 | sed 's/## //')
"
        fi
    fi
done

if [ -n "$orchOutput" ]; then
    output+="
### Active Orchestrations (dmux dispatch)
$orchOutput
Read the orchestration log (\`.dmux/orchestration.md\`) for full wave history and decisions.
"
fi

# --- Section 3: JSONL event log tail ---
# Cap the tail at 10 mechanical events (edit/commit/compaction). For commit events keep ONLY
# the first clean line of the message: a raw multi-line `-m` capture otherwise leaks
# `$(cat <<'MARKER'` heredoc scaffolding (verbose, truncated mid-string, low signal). The
# empty-msg guard renders a missing message as a blank line rather than "null".
jsonlLines=10
jsonlFile="$stateDir/session-events-$sessionId.jsonl"
eventsFilter='
  select(.type=="edit" or .type=="commit" or .type=="compaction")
  | if .type=="commit" then
      .msg |= ( (. // "") | split("\n")
                | ( (.[0] // "") as $first
                    | if ($first | test("^\\$\\(cat <<")) then (.[1] // $first) else $first end )
                | gsub("^\\s+|\\s+$"; "") )
    else . end
'
jsonlOutput=""
if [ -n "$sessionId" ] && [ -f "$jsonlFile" ]; then
    jsonlOutput=$(jq -c "$eventsFilter" "$jsonlFile" 2>/dev/null | tail -n "$jsonlLines")
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
# Two save files may exist per session:
#   - auto-context-save-{sid}.md       <- written by /context-save skill (rich semantic content)
#   - auto-context-save-{sid}-hook.md  <- written by PreCompact hook (fresh mechanical state)
# Read both. Skill file gives Goal/Critical Context/Decisions; hook file gives
# fresh Git State / Active Specs / Daily Notes captured at compaction moment.
skillSaveFile=""
hookSaveFile=""
if [ -n "$sessionId" ]; then
    skillSaveFile="$stateDir/auto-context-save-$sessionId.md"
    hookSaveFile="$stateDir/auto-context-save-$sessionId-hook.md"
fi
# Skill-file fallback: ONLY if no session_id (emergency recovery). Never grab another
# session's manual save when we have a session_id - it would inject the wrong intent.
if [ -z "$sessionId" ] && [ ! -f "$skillSaveFile" ]; then
    skillSaveFile=$(ls -1t "$stateDir"/auto-context-save-*.md 2>/dev/null | grep -v -- '-hook' | grep -v -- '-w[0-9]' | head -1)
fi
# Hook-file fallback: prefer the no-session generic path the hook still writes when
# session_id is missing. Don't pull other sessions' hook files for the same reason.
if [ ! -f "$hookSaveFile" ]; then
    if [ -f "$stateDir/auto-context-save-hook.md" ]; then
        hookSaveFile="$stateDir/auto-context-save-hook.md"
    elif [ -z "$sessionId" ]; then
        hookSaveFile=$(ls -1t "$stateDir"/auto-context-save-*-hook.md 2>/dev/null | grep -v -- '-w[0-9]' | head -1)
    fi
fi

# --- Arm the post-compaction read-gate ---
# Drop a sentinel naming the save file(s) so the PreToolUse hook gate-resume-read.sh
# blocks consequential tools until one is Read since this compaction. Keyed on the FULL
# session id ($sid, not the 8-char $sessionId) so sessions sharing a prefix can't collide
# on one gate (gate-resume-read.sh keys on the same full id). Written atomically (temp + mv)
# so a tool call can never observe a half-written sentinel and slip through unenforced.
# Armed only when a save actually exists to read.
if [ -n "$sid" ] && { [ -f "$skillSaveFile" ] || [ -f "$hookSaveFile" ]; }; then
    sentinelFile="/tmp/claude-needs-resume-read-$sid"
    tmpSentinel="${sentinelFile}.$$.tmp"
    : >"$tmpSentinel" 2>/dev/null || true
    [ -f "$skillSaveFile" ] && echo "$skillSaveFile" >>"$tmpSentinel" 2>/dev/null
    [ -f "$hookSaveFile" ] && echo "$hookSaveFile" >>"$tmpSentinel" 2>/dev/null
    mv -f "$tmpSentinel" "$sentinelFile" 2>/dev/null || rm -f "$tmpSentinel" 2>/dev/null
fi

saveOutput=""
# Pull rich semantic blocks from skill file (Goal, Critical Context, Decisions)
if [ -f "$skillSaveFile" ]; then
    for section in "Goal" "Critical Context" "Decisions"; do
        block=$(sed -n "/^## $section/,/^## /{/^## $section/d; /^## /d; p;}" "$skillSaveFile" 2>/dev/null | head -20)
        if [ -n "$block" ]; then
            saveOutput+="
$section:
$block
"
        fi
    done
fi
# Pull fresh mechanical state from hook file (Active Specs, Git State)
if [ -f "$hookSaveFile" ]; then
    specsSection=$(sed -n '/^## Active Specs/,/^## /{/^## Active Specs/d; /^## /d; p;}' "$hookSaveFile" 2>/dev/null | head -10)
    if [ -n "$specsSection" ]; then
        saveOutput+="
Active Specs:
$specsSection
"
    fi
    gitSection=$(sed -n '/^## Git State/,/^## /{/^## Git State/d; /^## /d; p;}' "$hookSaveFile" 2>/dev/null | head -15)
    if [ -n "$gitSection" ]; then
        saveOutput+="
Git State:
$gitSection"
    fi
fi

if [ -n "$saveOutput" ]; then
    output+="
### From Save Files
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
        jsonlOutput=$(jq -c "$eventsFilter" "$jsonlFile" 2>/dev/null | tail -n 10)
        # Rebuild output (simpler than surgical replacement)
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
If this context seems incomplete, run /context-resume for full manual recovery.
Save files: skill=${skillSaveFile:-none} hook=${hookSaveFile:-none} (read manually if needed)
"
fi

# --- Read-gate enforcement notice (added AFTER truncation so it is never dropped) ---
# Recovery context lands only when it is compelling and enforced. The block above is
# compelling; this gate makes the first consequential action wait until the save is opened.
if [ -n "$sid" ] && { [ -f "$skillSaveFile" ] || [ -f "$hookSaveFile" ]; }; then
    output+="
### >> READ YOUR SESSION SAVE BEFORE ANY NON-READ TOOL (enforced this turn)
A PreToolUse read-gate blocks Edit / Write / Bash / dispatch tools until you Read the save below since this compaction; read-only tools (Read / Grep / Glob) stay open, reading the save clears the gate, and it self-expires after 30 min. Open it now:"
    [ -f "$skillSaveFile" ] && output+="
  Read $skillSaveFile"
    [ -f "$hookSaveFile" ] && output+="
  Read $hookSaveFile"
    output+="
"
fi

[ -n "$output" ] && printf '%s' "$output" | bash "$STRATA_HOME/hooks/lib-ledger.sh" session-post-compaction-restore "$sessionId" >/dev/null 2>&1 || true
printf '%s' "$output"
exit 0
