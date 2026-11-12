#!/usr/bin/env bash
# Contract test for the minimal post-compaction restore hook.
# Eight cases: it stays silent off a compaction boundary, it gives no missing-save
# instruction when no save exists (a ticket, 2026-09-04), it inlines a short save, it
# points at an unchanged save instead of repeating it, it inlines a rewritten save again,
# it caps a long save by characters with a counted trailer, it prefers a brief in the vault, and it survives an unset HOME.
set -euo pipefail

hook="$(cd "$(dirname "$0")" && pwd)/session-post-compaction-restore.sh"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/test-restore-XXXXXX")"
trap 'rm -rf "$tmp"' EXIT

state="$tmp/state"; mkdir -p "$state"
sid="abcd1234-0000-1111-2222-333344445555"
save="$state/auto-context-save-${sid:0:8}.md"
export TELEMETRY_SYNTHETIC=1 COMPACTION_STATE_DIR="$tmp/seen" BRIEF_DIR="$tmp/vault"

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
[[ ! -e "$tmp/seen" ]] || { echo "FAIL: an off-boundary run recorded a save as inlined"; exit 1; }

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
[[ "$out" != *"more characters in the file"* ]] || { echo "FAIL: trailer on a short save"; exit 1; }

# 4. The next compaction with the same save: one line naming it, not the content again.
out="$(run compact)"
[[ "$out" == *"POST-COMPACTION"* ]] || { echo "FAIL: header missing on a repeat boundary"; exit 1; }
[[ "$out" == *"$save"*"has not changed since"* ]] || { echo "FAIL: unchanged save not pointed at: $out"; exit 1; }
[[ "$out" != *"Cut the continuity layer."* ]] || { echo "FAIL: unchanged save inlined a second time"; exit 1; }

# 5. A rewritten save is new information: inlined again.
sleep 1; printf '# Session save\nGoal: second version.\n' > "$save"
out="$(run compact)"
[[ "$out" == *"Goal: second version."* ]] || { echo "FAIL: rewritten save not inlined"; exit 1; }

# 6. A 20,000-character save of long lines: the payload stays under a sample bound of
#    10,000 characters (the sample SAVE_CHARS plus the header), ends on a whole line, and counts what it left out.
for i in $(seq 1 50); do printf 'line %03d %s\n' "$i" "$(printf 'x%.0s' $(seq 1 390))"; done > "$save"
out="$(run compact)"
[[ "${#out}" -lt 10000 ]] || { echo "FAIL: payload of ${#out} characters breaks the sample bound"; exit 1; }
[[ "$out" == *"line 001 "* ]] || { echo "FAIL: head of the long save missing"; exit 1; }
[[ "$out" != *"line 050 "* ]] || { echo "FAIL: long save inlined whole"; exit 1; }
[[ "$out" =~ \(\+([0-9]+)\ more\ characters\ in\ the\ file\) ]] || { echo "FAIL: trailer wrong or absent"; exit 1; }
[[ "${BASH_REMATCH[1]}" -gt 12000 ]] || { echo "FAIL: trailer undercounts: ${BASH_REMATCH[1]}"; exit 1; }
last="$(printf '%s\n' "$out" | grep '^line ' | tail -1)"
[[ "${#last}" -eq 399 ]] || { echo "FAIL: cut mid-line (${#last} characters)"; exit 1; }

# 7. A brief in the vault is found by session id and wins over the legacy file; of two
#    briefs for one session the later date wins.
mkdir -p "$tmp/vault"
printf 'Goal: older vault brief.\n' > "$tmp/vault/2026-11-09-claude-${sid:0:8}-brief.md"
printf 'Goal: newest vault brief.\n' > "$tmp/vault/2026-11-10-claude-${sid:0:8}-brief.md"
printf 'Goal: someone else.\n' > "$tmp/vault/2026-11-10-claude-ffff0000-brief.md"
out="$(run compact)"
[[ "$out" == *"Goal: newest vault brief."* ]] || { echo "FAIL: vault brief not inlined: $out"; exit 1; }
[[ "$out" != *"older vault brief"* && "$out" != *"someone else"* && "$out" != *"line 001"* ]] \
    || { echo "FAIL: wrong brief inlined beside the vault one"; exit 1; }
rm -rf "$tmp/vault"

# 8. HOME and STATE_DIR both unset: still exit 0 with the header, never
#    an unbound-variable abort (set -u is on).
out="$(jq -nc --arg sid "$sid" --arg c "$tmp" '{source:"compact",session_id:$sid,cwd:$c}' \
    | env -u HOME -u STATE_DIR -u COMPACTION_STATE_DIR -u BRIEF_DIR bash "$hook")" || { echo "FAIL: nonzero exit with HOME unset"; exit 1; }
[[ "$out" == *"POST-COMPACTION"* ]] || { echo "FAIL: HOME unset lost the header"; exit 1; }

printf 'session-post-compaction-restore: silent off-boundary, no save demand when unsaved, save inlined once, rewritten save inlined again, character cap with counted trailer\n'
