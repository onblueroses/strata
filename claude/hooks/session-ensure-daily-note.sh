#!/usr/bin/env bash
# RETIRED 2026-07-28 by the OptMem cutover. UNREGISTERED from settings.json; do not
# re-register. It CREATES life/daily/<date>-<name>-<sid>.json and GCs old notes into
# ~/to-delete, and life/daily/ is now read-only, so every operation here fails. Its
# session-id job is gone too: optmem-wake.sh prints `SESSION SCOPE: @s/<id>` instead.
# Kept on disk only as part of the documented rollback path
# (life/areas/claude-code-setup/state/optmem/settings-rollback.md).
# Ensure a JSON daily note exists for this session (one note per session lifetime).

dailyDir="${CLAUDE_DAILY_DIR:-$HOME/.local/share/claude-daily}"
quarantineDir="$HOME/to-delete"
manifest="$quarantineDir/manifest.txt"
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

sessionName="unnamed"
dailyFile="$dailyDir/$today-$sessionName-$sessionId.json"

# One note per session lifetime: reuse this session's existing note on ANY day
# rather than spawning a fresh stub. SessionStart fires on resume and compaction,
# so a session that spans midnight or resumes later would otherwise accrete a new
# stub every day — the cross-day re-stub was the daily-note flood source.
# Legacy cross-day re-stubbing can leave several notes with the same short session ID.
# Select the latest valid note by its recorded date, then mtime, so resume never depends
# on find's directory order and an older completed note cannot win arbitrarily.
existing=""
existingKey=""
while IFS= read -r -d '' candidate; do
    jq empty "$candidate" 2>/dev/null || continue
    candidateDate=$(jq -r '.date // empty' "$candidate" 2>/dev/null)
    if [[ ! "$candidateDate" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]]; then
        candidateDate=$(basename "$candidate" | grep -oE '^[0-9]{4}-[0-9]{2}-[0-9]{2}' || true)
    fi
    [ -n "$candidateDate" ] || candidateDate="0000-00-00"
    candidateMtime=$(stat -c %Y "$candidate" 2>/dev/null || echo 0)
    candidateKey="$candidateDate:$candidateMtime:$candidate"
    if [ -z "$existingKey" ] || [[ "$candidateKey" > "$existingKey" ]]; then
        existing="$candidate"
        existingKey="$candidateKey"
    fi
done < <(find "$dailyDir" -maxdepth 1 -type f -name "*-$sessionId.json" -print0 2>/dev/null)
if [ -n "$existing" ]; then
    dailyFile="$existing"
else
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

# Retire abandoned null-summary stubs older than a day. Move them to the reversible
# quarantine instead of deleting (per the deletions convention): never touch this
# session's own note, and act only when jq can parse the file. An unparseable note is
# corruption to preserve for inspection, not an empty stub to reclaim — the previous
# `rm` conflated "jq failed to parse" with "summary is empty" and destroyed both.
mkdir -p "$quarantineDir"
find "$dailyDir" -maxdepth 1 -name "*.json" -mtime +1 2>/dev/null | while read -r f; do
    [ "$f" = "$dailyFile" ] && continue
    case "$(basename "$f")" in
        *-"$sessionId".json) continue ;;
    esac
    if jq empty "$f" 2>/dev/null; then
        summary=$(jq -r '.summary // ""' "$f" 2>/dev/null)
        [ -n "$summary" ] && continue
        reason="null-summary stub >1d"
    else
        reason="unparseable json quarantined"
    fi
    if mv "$f" "$quarantineDir/" 2>/dev/null; then
        echo "$(basename "$f") | $f | $today | daily-note GC: $reason" >> "$manifest"
    fi
done

# Emit the selected note path on stdout: SessionStart stdout becomes session context,
# and /end and /spec read it to recover which note to finalize. With cross-day reuse
# this now points at the real prior-dated or renamed note for this session.
echo "$dailyFile"
