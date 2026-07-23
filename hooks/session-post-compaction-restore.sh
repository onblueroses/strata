#!/usr/bin/env bash
# Post-compaction context restore (v3 — pointer-first edition)
# Fires on SessionStart after compaction. Injects the recovery map: points at the
# session saves (which themselves point at canonical docs, specs, and the entity KB
# on disk) and arms the read-gate so the save is actually read before work resumes.
# Pipeline overview: $STRATA_HOME/reference/context-continuity.md

STRATA_HOME="${STRATA_HOME:-$HOME/.strata}"
KB_DIR="${KB_DIR:-$STRATA_HOME/workspace}"
STATE_DIR="${STATE_DIR:-$KB_DIR/state}"
SPECS_DIR="${SPECS_DIR:-$STATE_DIR/specs}"

hookData=""
if [ ! -t 0 ]; then
    hookData=$(cat)
fi

sessionId=""
cwd="$HOME"
triggerVal=""

if [ -n "$hookData" ]; then
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

# Fire only on compaction
if [ "$triggerVal" != "compact" ]; then
    exit 0
fi

stateDir="$STATE_DIR"
specDir="$SPECS_DIR"
output=""

# ============================================================
# Section 1: Header — session, window, repo identity
# ============================================================

windowNum="?"
if [ -n "$sessionId" ]; then
    windowFile="/tmp/claude-compact-window-$sessionId.txt"
    if [ -f "$windowFile" ]; then
        windowNum=$(cat "$windowFile" 2>/dev/null | tr -d '[:space:]')
    fi
fi

# Repo identity
repoRoot=""
if [ -d "$cwd" ]; then
    repoRoot=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null)
fi
[ -z "$repoRoot" ] && repoRoot="$cwd"
repoName=$(basename "$repoRoot")

gitBranch=""
if [ -d "$repoRoot/.git" ] || [ -f "$repoRoot/.git" ]; then
    gitBranch=$(git -C "$repoRoot" branch --show-current 2>/dev/null)
fi
[ -z "$gitBranch" ] && gitBranch="(not a git repo)"

# Entity mapping
entityPath=""
for kind in projects areas; do
    candidate="$KB_DIR/$kind/$repoName"
    if [ -d "$candidate" ]; then
        entityPath="$candidate"
        break
    fi
done

# Save file paths
skillSaveFile=""
hookSaveFile=""
if [ -n "$sessionId" ]; then
    skillSaveFile="$stateDir/auto-context-save-$sessionId.md"
    hookSaveFile="$stateDir/auto-context-save-$sessionId-hook.md"
fi
[ -f "$skillSaveFile" ] || skillSaveFile=""
[ -f "$hookSaveFile" ] || hookSaveFile=""

# Emergency fallback when session_id is missing: pre-compaction hook still writes
# the generic auto-context-save-hook.md path. Use it ONLY when sessionId is empty
# (never as a cross-session leak when sessionId is set).
if [ -z "$sessionId" ] && [ -z "$hookSaveFile" ] && [ -f "$stateDir/auto-context-save-hook.md" ]; then
    hookSaveFile="$stateDir/auto-context-save-hook.md"
fi

# Arm the read-gate: drop a sentinel naming the save file(s) so the PreToolUse
# hook gate-resume-read.sh blocks consequential tools until one is Read this
# turn. Reading the save clears it; a 30-min TTL in the gate is the anti-deadlock
# backstop. Only armed when a save actually exists.
# - Keyed on the FULL session id ($sid, not the 8-char $sessionId) so sessions
#   sharing a prefix can't collide on one gate; gate-resume-read.sh uses the same id.
# - Written atomically (temp + mv) so a tool call can never observe an empty
#   half-written sentinel and slip through unenforced.
if [ -n "$sid" ] && { [ -n "$skillSaveFile" ] || [ -n "$hookSaveFile" ]; }; then
    sentinelFile="/tmp/claude-needs-resume-read-$sid"
    tmpSentinel="${sentinelFile}.$$.tmp"
    : >"$tmpSentinel" 2>/dev/null || true
    [ -n "$skillSaveFile" ] && echo "$skillSaveFile" >>"$tmpSentinel" 2>/dev/null
    [ -n "$hookSaveFile" ] && echo "$hookSaveFile" >>"$tmpSentinel" 2>/dev/null
    mv -f "$tmpSentinel" "$sentinelFile" 2>/dev/null || rm -f "$tmpSentinel" 2>/dev/null
fi

output="## Post-Compaction Recovery
Session: $sessionId | Window: $windowNum
Repo: \`$repoName\` (\`$repoRoot\`) | Branch: $gitBranch
Entity: ${entityPath:-(no entity mapping)}
"

# ============================================================
# Section 2: MANDATORY READS — point at the save files
# ============================================================

readSection=""
if [ -n "$skillSaveFile" ] || [ -n "$hookSaveFile" ]; then
    readSection="
### >> READ EVERY FILE LISTED HERE BEFORE ANY TEXT RESPONSE OR NON-READ TOOL CALL

**This is enforced this turn.** A read-gate blocks Edit / Write / Bash / dispatch tools until you Read the save below; read-only tools (Read / Grep / Glob) stay open, and reading the save clears the gate automatically. Read it first.

The saves below hold the live session state plus the map: paths to canonical docs, specs, and the entity KB, which all live on disk untouched by compaction. Open the saves, then open what their map names. This recovery block deliberately contains no previews; open the files yourself.
"
    idx=1
    if [ -n "$skillSaveFile" ]; then
        readSection+="
${idx}. \`$skillSaveFile\` — skill-written rich save (Goal, Decisions, In-Flight, Last Outputs, Session-Specific State)"
        idx=$((idx + 1))
    fi
    if [ -n "$hookSaveFile" ]; then
        readSection+="
${idx}. \`$hookSaveFile\` — hook-written mechanical snapshot + Frame map (canonical doc paths, git, specs, daily-note summaries)"
    fi
    readSection+="

After reading, also open any file listed in the save's \`## Read On Resume\` block at the specified line ranges. Do not skip this — it's the previous instance telling you exactly where to look first.
"
    output+="$readSection"
fi

# ============================================================
# Section 3: Active specs (READ THESE FIRST after Repo Frame)
# ============================================================

# Filter specs to OWN session only. The owner runs multiple parallel sessions on
# different specs; reading another session's spec contaminates this recovery.
# Match criteria (ANY of these passes a spec for inclusion):
#   1. Spec's `Session:` frontmatter field matches THIS sessionId
#   2. Spec has no `Session:` field at all (genuinely shared / unowned)
#   3. Spec was edited in THIS session per .session-edits-{sid}
# Skip every other in-progress spec — those belong to sibling sessions.

sessionEditsFile="$stateDir/.session-edits-$sessionId"
specOutput=""
specOverflow=""
ownedCount=0
otherSessionCount=0
if [ -d "$specDir" ]; then
    while IFS= read -r spec; do
        [ -f "$spec" ] || continue
        raw=$(cat "$spec" 2>/dev/null)
        [ -z "$raw" ] && continue
        # Header-only Status check: body prose can quote historical "Status: planning"
        if ! echo "$raw" | head -10 | grep -qE 'Status:\s*(in-progress|planning)'; then
            continue
        fi

        # Ownership check — Session field can be at line start OR after `| ` separator
        specSession=$(echo "$raw" | head -20 | grep -oE 'Session:[[:space:]]*[a-f0-9]{8}' | head -1 | grep -oE '[a-f0-9]{8}$')
        editedHere=0
        if [ -n "$sessionEditsFile" ] && [ -f "$sessionEditsFile" ]; then
            if grep -qF "$spec" "$sessionEditsFile" 2>/dev/null; then
                editedHere=1
            fi
        fi

        if [ -n "$specSession" ] && [ "$specSession" != "$sessionId" ] && [ "$editedHere" = "0" ]; then
            otherSessionCount=$((otherSessionCount + 1))
            continue
        fi

        ownedCount=$((ownedCount + 1))
        specName=$(basename "$spec")
        # No preview — listing the file is the cue to open it. Recently touched specs
        # surface in the main list; older specs ride in the overflow.
        if find "$spec" -mtime -7 -print -quit 2>/dev/null | grep -q .; then
            specOutput+="- \`$specName\` (recently touched)
"
        else
            specOverflow+="$specName "
        fi
    done < <(ls -1t "$specDir/"*.md 2>/dev/null)
fi

if [ -n "$specOutput" ] || [ -n "$specOverflow" ]; then
    output+="
### Active Specs — THIS session only (authoritative; don't re-debate Decisions)
$specOutput"
    if [ -n "$specOverflow" ]; then
        # List owned-but-stale spec names so the model can read them on resume —
        # they're THIS session's specs even if untouched recently; dropping them
        # to a count loses the path the model needs.
        overflowList=""
        for name in $specOverflow; do
            overflowList+="- \`$name\` (owned by this session; not touched in 7d)
"
        done
        output+="
$overflowList"
    fi
    if [ "$otherSessionCount" -gt 0 ]; then
        output+="
($otherSessionCount in-progress spec(s) belong to OTHER active sessions — deliberately hidden to prevent contamination)
"
    fi
elif [ "$otherSessionCount" -gt 0 ]; then
    output+="
### Active Specs
(none for this session; $otherSessionCount in-progress spec(s) belong to sibling sessions and are hidden)
"
fi

# ============================================================
# Section 4: Active dmux orchestration
# ============================================================

# Only look at the CURRENT cwd's orchestration log — scanning ~/Work/* leaks
# other sessions' parallel dispatches into this recovery.
orchOutput=""
orchPath="$repoRoot/.dmux/orchestration.md"
if [ -f "$orchPath" ]; then
    lastWave=$(grep '^## Wave' "$orchPath" 2>/dev/null | tail -1 | sed 's/## //')
    [ -n "$lastWave" ] && orchOutput+="- \`$repoName\`: $lastWave
"
fi

if [ -n "$orchOutput" ]; then
    output+="
### Active Orchestrations (dmux dispatch)
$orchOutput
Read the orchestration log (\`.dmux/orchestration.md\`) for full wave history.
"
fi

# ============================================================
# Section 5: Recent JSONL events
# ============================================================

# Cap the tail at 10 events. Mechanical events only (edit/commit/compaction); semantic events
# (decision/milestone/goal/hypothesis) carry verbose what/why payloads that preview the save's
# Decisions table — drop them so the model opens the save to learn what was decided and why.
# For commit events keep ONLY the first clean line of the message: the raw capture otherwise
# leaks `$(cat <<'MARKER'` heredoc scaffolding (verbose, truncated mid-string, low signal).
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

# ============================================================
# Section 6: Uncommitted changes
# ============================================================

gitStatus=""
if [ -d "$repoRoot" ]; then
    gitStatus=$(git -C "$repoRoot" status --short 2>/dev/null | head -15)
fi
if [ -n "$gitStatus" ]; then
    uncommittedCount=$(echo "$gitStatus" | wc -l | tr -d '[:space:]')
    output+="
### Uncommitted ($uncommittedCount files)
\`\`\`
$gitStatus
\`\`\`
"
fi

# ============================================================
# Section 7: Tail — what to do after reading
# ============================================================

output+="
### After reading
Resume from \`>> Current Step\` in the spec / \`Next Actions\` in the save. If anything is still unclear, run \`/context-resume\`.
"

# Output stays small by construction: pointers, 10 one-line events, 15 status lines.
# (The v2 char-budget trim was a no-op — it replaced the 10-event tail with the same
# 10 events — and was removed with the embedding it guarded against.)

[ -n "$output" ] && printf '%s' "$output" | bash "$STRATA_HOME/hooks/lib-ledger.sh" session-post-compaction-restore "$sessionId" >/dev/null 2>&1 || true
printf '%s' "$output"
exit 0
