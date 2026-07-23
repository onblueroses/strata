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

# Expand declared paths without eval. Relative repo-doc paths resolve from repoRoot;
# environment variables and ~ use this hook's environment and resolved local roots.
expandPath() {
    local raw="$1"
    RAW_PATH="$raw" REPO_ROOT="$repoRoot" STRATA_HOME="$STRATA_HOME" \
        KB_DIR="$KB_DIR" STATE_DIR="$STATE_DIR" SPECS_DIR="$SPECS_DIR" \
        python3 -c 'import os
p = os.path.expanduser(os.path.expandvars(os.environ["RAW_PATH"]))
if not os.path.isabs(p):
    p = os.path.join(os.environ["REPO_ROOT"], p)
print(os.path.realpath(p))' 2>/dev/null
}

isVolatilePath() {
    case "$1" in
        /tmp|/tmp/*|*/scratchpad|*/scratchpad/*) return 0 ;;
        *) return 1 ;;
    esac
}

gatePaths=()
gateRanges=()
gateWhys=()
gateBudgets=()
droppedNotes=()

addGateEntry() {
    local path="$1"
    local rangeStart="${2:-}"
    local rangeEnd="${3:-}"
    local why="$4"
    local existing lineCount budget

    for existing in "${gatePaths[@]}"; do
        [ "$existing" = "$path" ] && return
    done

    lineCount=$(wc -l < "$path" 2>/dev/null | tr -d '[:space:]')
    [[ "$lineCount" =~ ^[0-9]+$ ]] || lineCount=1
    [ "$lineCount" -gt 0 ] || lineCount=1
    if [[ "$rangeStart" =~ ^[0-9]+$ ]] && [[ "$rangeEnd" =~ ^[0-9]+$ ]] \
        && [ "$rangeStart" -gt 0 ] && [ "$rangeEnd" -ge "$rangeStart" ]; then
        budget=$((rangeEnd - rangeStart + 1))
    else
        rangeStart=1
        rangeEnd="$lineCount"
        budget="$lineCount"
    fi

    gatePaths+=("$path")
    gateRanges+=("$rangeStart-$rangeEnd")
    gateWhys+=("$why")
    gateBudgets+=("$budget")
}

findSessionOwnedSpec() {
    local spec raw specSession
    [ -n "$sessionId" ] && [ -d "$specDir" ] || return
    while IFS= read -r spec; do
        [ -f "$spec" ] || continue
        raw=$(cat "$spec" 2>/dev/null)
        [ -n "$raw" ] || continue
        echo "$raw" | head -10 | grep -qE 'Status:\s*(in-progress|planning)' || continue
        specSession=$(echo "$raw" | head -20 | grep -oE 'Session:[[:space:]]*[a-f0-9]{8}' | head -1 | grep -oE '[a-f0-9]{8}$')
        if [ "$specSession" = "$sessionId" ]; then
            printf '%s\n' "$spec"
            return
        fi
    done < <(ls -1t "$specDir/"*.md 2>/dev/null)
}

continuityFile="$STRATA_HOME/reference/context-continuity.md"
hasNorthStarBlock=0
if [ -n "$skillSaveFile" ] && grep -q '^## North Star$' "$skillSaveFile" 2>/dev/null; then
    hasNorthStarBlock=1
fi

gateMode="declared North Star"
if [ "$hasNorthStarBlock" = "1" ]; then
    addGateEntry "$skillSaveFile" "" "" "skill-written session frame, decisions, and declared strategic anchors"

    northStarPattern='^[[:space:]]*[0-9]+\.[[:space:]]+`([^`]+)`([[:space:]]+\(lines[[:space:]]+([0-9]+)-([0-9]+)\))?[[:space:]]+—[[:space:]]+(.+)$'
    declaredCount=0
    while IFS= read -r line; do
        if [[ "$line" =~ $northStarPattern ]]; then
            declaredCount=$((declaredCount + 1))
            rawPath="${BASH_REMATCH[1]}"
            rangeStart="${BASH_REMATCH[3]}"
            rangeEnd="${BASH_REMATCH[4]}"
            why="${BASH_REMATCH[5]}"
            expandedPath=$(expandPath "$rawPath")
            if [ -z "$expandedPath" ] || [ ! -f "$expandedPath" ] || isVolatilePath "$expandedPath"; then
                droppedNotes+=("dropped: $rawPath (volatile or missing)")
            else
                addGateEntry "$expandedPath" "$rangeStart" "$rangeEnd" "$why"
            fi
            [ "$declaredCount" -ge 3 ] && break
        fi
    done < <(sed -n '/^## North Star$/,/^## /{ /^## North Star$/d; /^## /d; p; }' "$skillSaveFile")

    if [ -f "$continuityFile" ]; then
        addGateEntry "$continuityFile" "" "" "context-continuity contract for the gate and recovery pipeline"
    fi
else
    gateMode="deterministic fallback"
    if [ -n "$hookSaveFile" ]; then
        addGateEntry "$hookSaveFile" "" "" "fallback mechanical map because no declared North Star is available"
    fi

    ownedSpecFallback=$(findSessionOwnedSpec)
    if [ -n "$ownedSpecFallback" ] && [ -f "$ownedSpecFallback" ]; then
        addGateEntry "$ownedSpecFallback" "" "" "session-owned active spec"
    fi

    entityDir=""
    if [ -n "$hookSaveFile" ]; then
        entityDir=$(grep -m1 -E '^\*{0,2}Entity:\*{0,2}[[:space:]]*' "$hookSaveFile" 2>/dev/null \
            | sed -E 's/^\*{0,2}Entity:\*{0,2}[[:space:]]*//; s/^`//; s/`$//')
    fi
    if [ -n "$entityDir" ] && [ "$entityDir" != "(no entity mapping)" ]; then
        entityDir=$(expandPath "$entityDir")
        entitySummary="$entityDir/summary.md"
        if [ -f "$entitySummary" ] && ! isVolatilePath "$entitySummary"; then
            addGateEntry "$entitySummary" "" "" "entity summary recovered from the hook map"
        fi
    fi
fi

# Absolute backstop: a compaction gate must never publish an empty sentinel.
if [ "${#gatePaths[@]}" -eq 0 ]; then
    if [ -f "$continuityFile" ]; then
        addGateEntry "$continuityFile" "" "" "continuity contract used as the last-resort orientation anchor"
    else
        restoreSelf="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/$(basename "${BASH_SOURCE[0]}")"
        addGateEntry "$restoreSelf" "" "" "restore hook used as the last-resort non-empty gate target"
    fi
fi

# Arm the read-gate: the declared mode gates orientation, not the mechanical map.
# The deterministic fallback is used only when the semantic save or North Star block
# is absent. A 30-min TTL in the gate remains the anti-deadlock backstop.
# - Keyed on the FULL session id ($sid, not the 8-char $sessionId) so sessions
#   sharing a prefix can't collide on one gate; gate-resume-read.sh uses the same id.
# - Written atomically (temp + mv) so a tool call can never observe an empty
#   half-written sentinel and slip through unenforced.
if [ -n "$sid" ]; then
    sentinelFile="/tmp/claude-needs-resume-read-$sid"
    tmpSentinel="${sentinelFile}.$$.tmp"
    printf '%s\n' "${gatePaths[@]}" >"$tmpSentinel" 2>/dev/null
    mv -f "$tmpSentinel" "$sentinelFile" 2>/dev/null || rm -f "$tmpSentinel" 2>/dev/null
fi

output="## Post-Compaction Recovery
Session: $sessionId | Window: $windowNum
Repo: \`$repoName\` (\`$repoRoot\`) | Branch: $gitBranch
Entity: ${entityPath:-(no entity mapping)}
"

# ============================================================
# Section 2: MANDATORY ORIENTATION READS + ADVISORY MAP
# ============================================================

readSection="
### >> READ EVERY FILE LISTED HERE BEFORE ANY TEXT RESPONSE OR NON-READ TOOL CALL

**This is enforced this turn.** A read-gate blocks Edit / Write / Bash / dispatch tools until you Read every gated orientation entry below; read-only tools (Read / Grep / Glob) stay open, and reading every entry clears the gate automatically. Read them first.

Compaction summaries preserve tactical state well; repeated summarization erodes strategic framing. Gate mode: **$gateMode**.

### Gated Orientation
"
for idx in "${!gatePaths[@]}"; do
    displayIdx=$((idx + 1))
    readSection+="
${displayIdx}. \`${gatePaths[$idx]}\` (lines ${gateRanges[$idx]}; budget: ${gateBudgets[$idx]} lines) — ${gateWhys[$idx]}"
done

if [ "${#droppedNotes[@]}" -gt 0 ]; then
    for note in "${droppedNotes[@]}"; do
        readSection+="
$note"
    done
fi

hookAdvisoryPath="${hookSaveFile:-$stateDir/auto-context-save-$sessionId-hook.md}"
readSection+="

### Advisory Map (not part of the declared North Star gate)

- \`$hookAdvisoryPath\` — hook-written mechanical snapshot + Frame map. In fallback mode it is gated only because the semantic North Star was unavailable.
- After orientation, use the skill save's \`## Read On Resume\` block for ungated tactical pointers. Point at conclusions, not logs.
"
output+="$readSection"

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
