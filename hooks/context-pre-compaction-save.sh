#!/usr/bin/env bash
# Pre-compaction auto-save (v3 — pointer-first edition)
# Captures the advisory mechanical snapshot (git, owned specs, daily-note summaries)
# plus a Frame MAP: paths to canonical docs and entity KB, with line counts. It embeds no
# doc content — disk survives compaction untouched; only context-window state dies.
# The /context-save skill writes the gated orientation companion (North Star) plus
# the semantic state (In-Flight, decisions).
# Pipeline overview: $STRATA_HOME/reference/context-continuity.md
# Output: $STATE_DIR/auto-context-save-{sid}-hook.md

STRATA_HOME="${STRATA_HOME:-$HOME/.strata}"
KB_DIR="${KB_DIR:-$STRATA_HOME/workspace}"
STATE_DIR="${STATE_DIR:-$KB_DIR/state}"
SPECS_DIR="${SPECS_DIR:-$STATE_DIR/specs}"

timestamp=$(date +"%Y-%m-%d %H:%M")

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

# Compaction window counter (restore hook + JSONL event display)
windowNum=1
if [ -n "$sessionId" ]; then
    windowCounterFile="/tmp/claude-compact-window-$sessionId.txt"
    if [ -f "$windowCounterFile" ]; then
        prev=$(cat "$windowCounterFile" 2>/dev/null | tr -d '[:space:]')
        [[ "$prev" =~ ^[0-9]+$ ]] && windowNum=$((prev + 1))
    fi
    printf '%d' "$windowNum" > "$windowCounterFile"
fi

stateDir="$STATE_DIR"
mkdir -p "$stateDir"
saveFile="$stateDir/auto-context-save-hook.md"
if [ -n "$sessionId" ]; then
    saveFile="$stateDir/auto-context-save-$sessionId-hook.md"
fi

# ============================================================
# Frame map: repo identity + canonical doc PATHS (no embedding)
# ============================================================

# Canonical doc filenames — most-load-bearing first. CLAUDE.md and AGENTS.md are
# omitted for the cwd repo: the harness natively reloads the cwd CLAUDE.md chain.
canonicalDocs=(
    "THESIS.md"
    "STRATEGY.md"
    "NORTH_STAR.md"
    "NORTHSTAR.md"
    "VISION.md"
    "GOALS.md"
    "CHARTER.md"
    "ROADMAP.md"
    "PLAN.md"
    "ARCHITECTURE.md"
    "DESIGN.md"
    "SPEC.md"
    "OVERVIEW.md"
    "PRINCIPLES.md"
    "MANIFEST.md"
    "README.md"
)

# Detect repo root via git; fall back to cwd
repoRoot=""
if [ -d "$cwd" ]; then
    repoRoot=$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null)
fi
[ -z "$repoRoot" ] && repoRoot="$cwd"
repoName=$(basename "$repoRoot")

gitRemote=""
if [ -d "$repoRoot/.git" ] || [ -f "$repoRoot/.git" ]; then
    gitRemote=$(git -C "$repoRoot" config --get remote.origin.url 2>/dev/null)
fi
[ -z "$gitRemote" ] && gitRemote="(no remote / local only)"

# Entity mapping ($KB_DIR/projects/{name} or $KB_DIR/areas/{name} matching repoName)
entityPath=""
for kind in projects areas; do
    candidate="$KB_DIR/$kind/$repoName"
    if [ -d "$candidate" ]; then
        entityPath="$candidate"
        break
    fi
done

# List a file as a pointer: "- `path` (N lines)". Args: path, label
pointFile() {
    local path="$1"
    local label="$2"
    [ ! -f "$path" ] || [ ! -r "$path" ] || [ ! -s "$path" ] && return
    local lineCount
    lineCount=$(wc -l < "$path" 2>/dev/null | tr -d '[:space:]')
    echo "- \`$label\` (${lineCount:-?} lines)"
}

buildFrameMap() {
    echo "## Repo Frame: $repoName"
    echo ""
    echo "**Path:** \`$repoRoot\`"
    echo "**Git remote:** $gitRemote"
    echo "**Entity:** ${entityPath:-(no entity mapping)}"
    echo ""
    echo "### Canonical Docs (on disk — open the load-bearing ones)"

    local foundAny=0
    local doc sub
    for doc in "${canonicalDocs[@]}"; do
        if [ -f "$repoRoot/$doc" ]; then
            pointFile "$repoRoot/$doc" "$repoRoot/$doc"
            foundAny=1
        fi
        for sub in docs notes .claude; do
            if [ -f "$repoRoot/$sub/$doc" ]; then
                pointFile "$repoRoot/$sub/$doc" "$repoRoot/$sub/$doc"
                foundAny=1
            fi
        done
    done
    [ "$foundAny" = "0" ] && echo "(no canonical docs found at repo root or docs/ notes/ .claude/)"

    if [ -n "$entityPath" ]; then
        echo ""
        echo "### Entity Knowledge Base (on disk)"
        pointFile "$entityPath/summary.md" "$entityPath/summary.md"
        pointFile "$entityPath/items.json" "$entityPath/items.json"
    fi
}

frameMapBlock=$(buildFrameMap)

# ============================================================
# Mechanical state: git, daily notes, active specs
# ============================================================

gitBranch=""
gitStatus=""
gitLog=""
gitDiffStat=""
if [ -d "$repoRoot/.git" ] || [ -f "$repoRoot/.git" ]; then
    gitBranch=$(git -C "$repoRoot" branch --show-current 2>/dev/null)
    gitStatus=$(git -C "$repoRoot" status --short 2>/dev/null | head -25)
    gitLog=$(git -C "$repoRoot" log --oneline -10 2>/dev/null)
    gitDiffStat=$(git -C "$repoRoot" diff --stat 2>/dev/null | head -20)
fi
[ -z "$gitBranch" ] && gitBranch="(not a git repo)"

# Daily notes: one summary line per completed session today; full JSON stays on disk.
today=$(date +%Y-%m-%d)
dailyContent=""
dailyDir="$KB_DIR/daily"
if [ -d "$dailyDir" ]; then
    # This session's own note only. Sibling sessions' summaries cost real context
    # and carry nothing this session can act on; their notes stay on disk, one
    # glob away.
    for note in "$dailyDir/$today-"*"-$sessionId.json"; do
        [ -f "$note" ] || continue
        summary=$(jq -r '.summary // empty' "$note" 2>/dev/null)
        if [ -n "$summary" ]; then
            dailyContent+="- \`$note\`: $summary"$'\n'
        fi
    done
    [ -n "$dailyContent" ] && dailyContent+="_Sibling sessions' notes: \`ls $dailyDir/$today-*.json\`_"$'\n'
fi
[ -z "$dailyContent" ] && dailyContent="(no completed sessions today)"

specDir="$SPECS_DIR"
specContent="(no active specs for this session)"
sessionEditsFile="$stateDir/.session-edits-$sessionId"
if [ -d "$specDir" ]; then
    specEntries=()
    otherSessionCount=0
    for spec in "$specDir/"*.md; do
        [ -f "$spec" ] || continue
        raw=$(cat "$spec" 2>/dev/null)
        [ -z "$raw" ] && continue
        # Header-only Status check: body prose can quote historical "Status: planning"
        if ! echo "$raw" | head -10 | grep -qE 'Status:\s*(in-progress|planning)'; then
            continue
        fi
        # Filter to specs owned by THIS session (or unowned, or edited here)
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
        step=$(echo "$raw" | sed -n '/^## >> Current Step/,/^## /{ /^## >> Current Step/d; /^## /d; p; }' | head -3 | sed 's/^[[:space:]]*//')
        if [ -n "$step" ]; then
            specEntries+=("- \`$spec\`:"$'\n'"$step")
        else
            specEntries+=("- \`$spec\`: (no current step)")
        fi
    done
    if [ ${#specEntries[@]} -gt 0 ]; then
        specContent=$(printf '%s\n' "${specEntries[@]}")
        if [ "$otherSessionCount" -gt 0 ]; then
            specContent+=$'\n'"($otherSessionCount in-progress spec(s) belong to other sessions — excluded to prevent contamination)"
        fi
    elif [ "$otherSessionCount" -gt 0 ]; then
        specContent="(none for this session; $otherSessionCount in-progress spec(s) belong to sibling sessions)"
    fi
fi

# ============================================================
# JSONL compaction event
# ============================================================

jsonlFile="$stateDir/session-events-$sessionId.jsonl"
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
fi

# ============================================================
# Write save file
# ============================================================

tmpSave="$saveFile.tmp.$$"
cat > "$tmpSave" << SAVEEOF
# Auto-Context Save (Pre-Compaction Hook)
Saved: $timestamp
Trigger: $trigger (compaction window $windowNum)
Session ID: $sessionId
Working directory: $cwd
Repo root: $repoRoot

> Pointer-first save: this file is the advisory MAP. Canonical docs, specs, and the
> entity KB live on disk at the listed paths. The /context-save skill writes the
> gated orientation companion at \`auto-context-save-$sessionId.md\`.

$frameMapBlock

## Active Specs
$specContent

> ADVISORY after compaction: consult \`>> Current Step\` when tactical state needs reconstruction.

## Git State
Branch: $gitBranch

### Status
\`\`\`
$gitStatus
\`\`\`

### Recent Commits
\`\`\`
$gitLog
\`\`\`

### Uncommitted Diff Stat
\`\`\`
$gitDiffStat
\`\`\`

## Today's Daily Notes (summaries; full JSON on disk)
$dailyContent

## Recovery
This advisory map complements \`auto-context-save-$sessionId.md\` (skill-written, if present), whose North Star anchors carry the gated strategic frame.
Transcript backup: $transcriptPath
SAVEEOF
mv -f "$tmpSave" "$saveFile"

# Backup transcript (full-fidelity history; keep 5)
if [ -n "$transcriptPath" ] && [ -f "$transcriptPath" ]; then
    backupDir="$STRATA_HOME/transcript-backups"
    mkdir -p "$backupDir"
    backupName="pre-compaction-$sessionId-$(date +%Y-%m-%d--%H-%M-%S).jsonl"
    cp "$transcriptPath" "$backupDir/$backupName"
    ls -1t "$backupDir"/pre-compaction-*.jsonl 2>/dev/null | tail -n +6 | while read -r f; do
        rm -f "$f"
    done
fi

# Age out saves left by other / dead sessions (>24h). BOTH of this session's saves
# (hook + skill-written semantic) are excluded — a live long session keeps its saves;
# stale per-window copies from the retired v2 format age out here too.
find "$stateDir" -maxdepth 1 -name "auto-context-save*.md" -mmin +1440 \
    ! -path "$saveFile" ! -name "auto-context-save-$sessionId.md" -delete 2>/dev/null
find "$stateDir" -maxdepth 1 -name "auto-context-save*.md.tmp.*" -mmin +60 -delete 2>/dev/null
find "$stateDir" -maxdepth 1 -name "session-events-*.jsonl" -mmin +1440 ! -name "session-events-$sessionId.jsonl" -delete 2>/dev/null

exit 0
