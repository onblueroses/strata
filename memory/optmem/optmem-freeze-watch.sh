#!/usr/bin/env bash
# Observe a frozen tree during a memory migration. The baseline is content and
# git history, not permissions: sibling state may remain writable. This monitor
# always exits zero so an observer failure cannot become a second write failure.
set -uo pipefail

if [[ -z "${FREEZE_REPO:-}" || -z "${FREEZE_STATE:-}" || -z "${FREEZE_TRACKED_DIR:-}" ]]; then
    printf 'Set FREEZE_REPO, FREEZE_STATE and FREEZE_TRACKED_DIR\n' >&2
    exit 0
fi
case "$FREEZE_TRACKED_DIR" in
  /*|..|../*|*/../*|*/..) printf 'FREEZE_TRACKED_DIR must stay inside FREEZE_REPO\n' >&2; exit 0 ;;
esac
log="$FREEZE_STATE/freeze-watch.jsonl"
ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
emit() { printf '%s\n' "$1" >> "$log"; }

if [[ ! -f "$FREEZE_STATE/freeze-baseline.sums" ]]; then
    emit "{\"ts\":\"$ts\",\"status\":\"no_baseline\"}"
    exit 0
fi
cd "$FREEZE_REPO" || { emit "{\"ts\":\"$ts\",\"status\":\"error\",\"reason\":\"repo_unavailable\"}"; exit 0; }

check=$(sha256sum -c "$FREEZE_STATE/freeze-baseline.sums" 2>/dev/null)
edited=$(printf '%s\n' "$check" | grep -c ': FAILED$' || true)
missing=$(printf '%s\n' "$check" | grep -c ': FAILED open or read$' || true)
expected=$(wc -l < "$FREEZE_STATE/freeze-baseline.sums")
checked=$(printf '%s\n' "$check" | grep -c ': ' || true)
if (( expected == 0 || checked != expected )); then
    emit "{\"ts\":\"$ts\",\"status\":\"VIOLATION\",\"reason\":\"baseline_unverifiable\",\"expected\":$expected,\"checked\":$checked}"
    exit 0
fi

listing_delta=0
if ! ls -1 "$FREEZE_TRACKED_DIR" 2>/dev/null | sort | diff -q - "$FREEZE_STATE/freeze-baseline.list" >/dev/null 2>&1; then
    listing_delta=1
fi
base=$(tr -d '[:space:]' < "$FREEZE_STATE/freeze-baseline.commit" 2>/dev/null)
if [[ -z "$base" ]] || ! git rev-parse --verify "$base^{commit}" >/dev/null 2>&1; then
    emit "{\"ts\":\"$ts\",\"status\":\"baseline_unverifiable\",\"reason\":\"commit_missing\"}"
    exit 0
fi
commits=$(git log --oneline "$base..HEAD" -- "$FREEZE_TRACKED_DIR" 2>/dev/null | wc -l)
if (( edited == 0 && missing == 0 && listing_delta == 0 && commits == 0 )); then status=clean; else status=VIOLATION; fi
emit "{\"ts\":\"$ts\",\"status\":\"$status\",\"content_edited\":$edited,\"files_missing\":$missing,\"listing_changed\":$listing_delta,\"commits_touching_tree\":$commits,\"files_checked\":$checked}"
exit 0
