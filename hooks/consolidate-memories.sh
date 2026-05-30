#!/usr/bin/env bash
# consolidate-memories.sh — Nightly memory maintenance.
# Run via systemd timer or cron. Two phases:
#   1. Extract durable facts from recent daily notes into memories (via claude -p)
#   2. Flag stale memories (not updated in STALE_DAYS)
#
# Usage: bash consolidate-memories.sh [--dry-run]
#
# Reads $STATE_DIR/memory for the memory store and $KB_DIR/daily for daily notes.
# Defaults to the strata workspace layout when those are unset.

set -uo pipefail

STATE_DIR="${STATE_DIR:-$HOME/strata-workspace/state}"
KB_DIR="${KB_DIR:-$HOME/strata-workspace}"
MEMORY_DIR="${MEMORY_DIR:-$STATE_DIR/memory}"
DAILY_DIR="${DAILY_DIR:-$KB_DIR/daily}"
STALE_DAYS="${STALE_DAYS:-30}"
TODAY=$(date +%Y-%m-%d)
DRY_RUN=0

[[ "${1:-}" == "--dry-run" ]] && DRY_RUN=1

[[ -d "$MEMORY_DIR" ]] || { echo "[consolidate] memory dir missing: $MEMORY_DIR" >&2; exit 0; }
[[ -d "$DAILY_DIR" ]] || { echo "[consolidate] daily dir missing: $DAILY_DIR" >&2; exit 0; }

log() { echo "[consolidate] $(date +%H:%M:%S) $*"; }

# --- Phase 1: Extract memories from recent daily notes ---

CONSOLIDATED_LOG="$MEMORY_DIR/.consolidated-dates.txt"
touch "$CONSOLIDATED_LOG" 2>/dev/null

notes_to_process=()
for i in 0 1 2; do
    date_str=$(date -d "$i days ago" +%Y-%m-%d 2>/dev/null || date -v-${i}d +%Y-%m-%d 2>/dev/null)
    [[ -z "$date_str" ]] && continue
    grep -qF "$date_str" "$CONSOLIDATED_LOG" 2>/dev/null && continue

    note=$(find "$DAILY_DIR" -name "${date_str}*.json" -type f 2>/dev/null | head -1)
    [[ -n "$note" ]] && notes_to_process+=("$note")
done

if [[ ${#notes_to_process[@]} -eq 0 ]]; then
    log "No new daily notes to consolidate."
else
    log "Found ${#notes_to_process[@]} daily notes to process."

    existing_memories=""
    for f in "$MEMORY_DIR"/*.md; do
        [[ -f "$f" ]] || continue
        [[ "$(basename "$f")" == "MEMORY.md" ]] && continue
        name=$(awk '{ gsub(/\r/, "") } /^---$/{n++;next} n==1 && /^name:/{sub(/^name: */,"");print;exit}' "$f")
        desc=$(awk '{ gsub(/\r/, "") } /^---$/{n++;next} n==1 && /^description:/{sub(/^description: */,"");print;exit}' "$f")
        existing_memories+="- $name: $desc\n"
    done

    notes_content=""
    for note in "${notes_to_process[@]}"; do
        notes_content+="$(cat "$note")\n\n---\n\n"
    done

    prompt="You are a memory consolidation agent. Extract durable facts from these daily session notes into the existing memory system.

EXISTING MEMORIES:
$(echo -e "$existing_memories")

DAILY NOTES:
$(echo -e "$notes_content")

RULES:
- Only extract information useful in FUTURE sessions
- Skip: debugging steps, temporary state, things derivable from code/git
- If an existing memory covers this topic, say UPDATE and which one
- If truly new, say CREATE with type (user/feedback/project/reference)
- Keep entries to 3-10 lines
- Format each as: ACTION: CREATE|UPDATE|SKIP
  FILE: filename.md (for UPDATE) or suggested_name.md (for CREATE)
  TYPE: user|feedback|project|reference
  CONTENT: the memory content

If nothing worth persisting, say NOTHING_TO_EXTRACT."

    if [[ "$DRY_RUN" -eq 1 ]]; then
        log "[dry-run] Would send ${#notes_to_process[@]} notes to claude -p"
        log "[dry-run] Prompt length: ${#prompt} chars"
    else
        log "Running consolidation via claude -p..."
        result=$(echo "$prompt" | claude -p --model haiku 2>/dev/null) || {
            log "claude -p failed (exit $?), skipping extraction."
            result=""
        }

        if [[ -n "$result" ]] && ! echo "$result" | grep -qF "NOTHING_TO_EXTRACT"; then
            output_file="$MEMORY_DIR/.consolidation-$(date +%Y%m%d).md"
            echo "$result" > "$output_file"
            log "Consolidation output saved to $output_file for review."
            log "Review and apply changes manually (memories are not auto-written)."
        else
            log "Nothing to extract from recent notes."
        fi

        for note in "${notes_to_process[@]}"; do
            date_str=$(basename "$note" | grep -oP '\d{4}-\d{2}-\d{2}')
            [[ -n "$date_str" ]] && echo "$date_str" >> "$CONSOLIDATED_LOG"
        done
    fi
fi

# --- Phase 2: Staleness check ---

CUTOFF=$(date -d "$STALE_DAYS days ago" +%Y-%m-%d 2>/dev/null || date -v-${STALE_DAYS}d +%Y-%m-%d 2>/dev/null)

if [[ -z "$CUTOFF" ]]; then
    log "Could not compute staleness cutoff, skipping."
    exit 0
fi

log "Checking for memories not updated since $CUTOFF..."

stale=()
for f in "$MEMORY_DIR"/*.md; do
    [[ -f "$f" ]] || continue
    basename_f=$(basename "$f")
    [[ "$basename_f" == "MEMORY.md" ]] && continue
    [[ "$basename_f" == .* ]] && continue

    file_date=$(date -r "$f" +%Y-%m-%d 2>/dev/null)
    [[ -z "$file_date" ]] && continue

    if [[ "$file_date" < "$CUTOFF" ]]; then
        days_old=$(( ($(date +%s) - $(date -r "$f" +%s)) / 86400 ))
        stale+=("$basename_f ($days_old days)")
    fi
done

if [[ ${#stale[@]} -eq 0 ]]; then
    log "No stale memories found."
else
    log "Found ${#stale[@]} stale memories (>${STALE_DAYS} days):"
    for s in "${stale[@]}"; do
        log "  - $s"
    done
    if [[ "$DRY_RUN" -eq 0 ]]; then
        {
            echo "# Stale Memory Review ($TODAY)"
            echo ""
            echo "These memories haven't been modified in ${STALE_DAYS}+ days."
            echo "Review: update content, or forget if no longer relevant."
            echo ""
            for s in "${stale[@]}"; do
                echo "- $s"
            done
        } > "$MEMORY_DIR/.stale-review.md"
        log "Written to $MEMORY_DIR/.stale-review.md"
    fi
fi

log "Done."
