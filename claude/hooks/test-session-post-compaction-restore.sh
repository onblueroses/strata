#!/usr/bin/env bash
# Contract test for the minimal post-compaction restore hook.
# Five cases: it stays silent off a compaction boundary, it gives no missing-save
# instruction when no save exists (a ticket, 2026-09-04), it inlines a short save,
# it caps a long save at 150 lines with a counted trailer, and it survives an unset HOME.
set -euo pipefail

hook="$(cd "$(dirname "$0")" && pwd)/session-post-compaction-restore.sh"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/test-restore-XXXXXX")"
trap 'rm -rf "$tmp"' EXIT

state="$tmp/state"; mkdir -p "$state"
sid="abcd1234-0000-1111-2222-333344445555"
save="$state/auto-context-save-${sid:0:8}.md"

run() {  # run <source>
    jq -nc --arg s "$1" --arg sid "$sid" --arg c "$tmp" \
        '{source:$s,session_id:$sid,cwd:$c}' \
        | STATE_DIR="$state" bash "$hook"
}

# 1. Not a compaction boundary: silence, whatever else is on disk.
printf '# Save\nGoal: must not appear\n' > "$save"
out="$(run startup)"
[[ -z "$out" ]] || { echo "FAIL: non-compact source printed: $out"; exit 1; }
out="$(run resume)"
[[ -z "$out" ]] || { echo "FAIL: resume source printed: $out"; exit 1; }

# 2. Compaction with no save: the header, and no instruction to save (saves are
#    made only when useful, a ticket).
mv "$save" "$save.hidden"
out="$(run compact)"
[[ "$out" == *"POST-COMPACTION"* ]] || { echo "FAIL: header missing without a save"; exit 1; }
[[ "$out" != *"/context-save"* ]] || { echo "FAIL: unsaved compaction still demands /context-save"; exit 1; }
mv "$save.hidden" "$save"

# 3. Compaction with a short save: inlined verbatim, no trailer.
cat > "$save" <<'EOF'
# Session save
## Goal
Cut the continuity layer.
## Next moves
1. Rewrite the restore hook.
EOF
out="$(run compact)"
[[ "$out" == *"Cut the continuity layer."* ]] || { echo "FAIL: short save not inlined"; exit 1; }
[[ "$out" == *"1. Rewrite the restore hook."* ]] || { echo "FAIL: short save truncated"; exit 1; }
[[ "$out" == *"$save"* ]] || { echo "FAIL: header does not name the save path"; exit 1; }
[[ "$out" != *"more lines in the file"* ]] || { echo "FAIL: trailer on a short save"; exit 1; }

# 4. A 200-line save: 150 lines inlined, 50 reported.
seq 1 200 | sed 's/^/line /' > "$save"
out="$(run compact)"
[[ "$out" == *"line 150"* ]] || { echo "FAIL: line 150 missing"; exit 1; }
[[ "$out" != *"line 151"* ]] || { echo "FAIL: inlined past the 150-line cap"; exit 1; }
[[ "$out" == *"(+50 more lines in the file)"* ]] || { echo "FAIL: trailer wrong or absent"; exit 1; }

# 5. HOME and STATE_DIR both unset: still exit 0 with the header, never
#    an unbound-variable abort (set -u is on).
out="$(jq -nc --arg sid "$sid" --arg c "$tmp" '{source:"compact",session_id:$sid,cwd:$c}' \
    | env -u HOME -u STATE_DIR bash "$hook")" || { echo "FAIL: nonzero exit with HOME unset"; exit 1; }
[[ "$out" == *"POST-COMPACTION"* ]] || { echo "FAIL: HOME unset lost the header"; exit 1; }

printf 'session-post-compaction-restore: silent off-boundary, no save demand when unsaved, save inlined, 150-line cap with counted trailer\n'
