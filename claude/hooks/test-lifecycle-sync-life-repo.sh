#!/usr/bin/env bash
set -euo pipefail

rootDir=$(cd "$(dirname -- "$0")/.." && pwd -P)
sourceHook="$rootDir/hooks/lifecycle-sync-life-repo.sh"
settingsFile="$rootDir/settings.example.json"
scratchDir=$(mktemp -d /tmp/work215-life-sync.XXXXXX)
toDeleteDir=${TO_DELETE_DIR:-${TMPDIR:-/tmp}/strata-test-to-delete}
testHook="$scratchDir/lifecycle-sync-life-repo.sh"
failingGitDir="$scratchDir/failing-git"
failingDiffGitDir="$scratchDir/failing-diff-git"
passCount=0

cleanup() {
    local archiveDir
    archiveDir="$toDeleteDir/$(basename -- "$scratchDir")"
    if [ -e "$scratchDir" ]; then
        mkdir -p -- "$toDeleteDir"
        mv -- "$scratchDir" "$archiveDir"
        printf '%s | %s | %s | %s\n' \
            "$(basename -- "$archiveDir")" "$scratchDir" "$(date +%F)" \
            "a ticket lifecycle-sync test fixture" >> "$toDeleteDir/manifest.txt"
    fi
}
trap cleanup EXIT

# The replacement hook has a synthetic repo seam. Rewriting the original literal keeps
# this test safe when run red against the predecessor, which otherwise targets ~/life.
# The replacement text must stay literal in the generated hook.
# shellcheck disable=SC2016
sed 's|lifeDir="$HOME/life"|lifeDir="${LIFE_SYNC_REPO:-$HOME/life}"|' \
    "$sourceHook" > "$testHook"
chmod +x "$testHook"
mkdir -p "$failingGitDir"
realGit=$(command -v git)
# The wrapper expands its arguments when the fixture runs.
# shellcheck disable=SC2016
printf '%s\n' '#!/usr/bin/env bash' \
    'for argument in "$@"; do' \
    '    [ "$argument" != status ] || exit 73' \
    'done' \
    "exec $realGit \"\$@\"" > "$failingGitDir/git"
chmod +x "$failingGitDir/git"
mkdir -p "$failingDiffGitDir"
# The wrapper expands arguments when the fixture runs.
# shellcheck disable=SC2016
printf '%s\n' '#!/usr/bin/env bash' \
    'for argument in "$@"; do' \
    '    [ "$argument" != --name-only ] || exit 74' \
    'done' \
    "exec $realGit \"\$@\"" > "$failingDiffGitDir/git"
chmod +x "$failingDiffGitDir/git"

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

pass() {
    passCount=$((passCount + 1))
    printf 'ok %d - %s\n' "$passCount" "$1"
}

assert_eq() {
    local expected=$1 actual=$2 message=$3
    [ "$actual" = "$expected" ] || fail "$message (expected '$expected', got '$actual')"
}

new_fixture() {
    local fixtureDir="$scratchDir/$1" repo="$scratchDir/$1/work"
    local remote="$scratchDir/$1/remote.git"

    mkdir -p "$fixtureDir"
    git init -q --bare "$remote"
    git init -q -b master "$repo"
    git -C "$repo" config user.email example.invalid
    git -C "$repo" config user.name "Lifecycle test"
    mkdir -p "$repo/areas/claude-code-setup/state"
    printf 'areas/claude-code-setup/state/.session-edits-*\n' > "$repo/.gitignore"
    printf 'owned base\n' > "$repo/owned.txt"
    printf 'shared base\n' > "$repo/shared.txt"
    printf 'staged base\n' > "$repo/staged.txt"
    git -C "$repo" add .gitignore owned.txt shared.txt staged.txt
    git -C "$repo" commit -qm "Initialize fixture"
    git -C "$repo" remote add origin "$remote"
    git -C "$repo" push -q -u origin master
    printf '%s\n' "$repo"
}

ledger_path() {
    local repo=$1 sid=$2
    printf '%s/areas/claude-code-setup/state/.session-edits-%s\n' "$repo" "${sid:0:8}"
}

write_ledger() {
    local repo=$1 sid=$2
    shift 2
    printf '%s\n' "$@" > "$(ledger_path "$repo" "$sid")"
}

run_event() {
    local repo=$1 sid=$2 event=$3 processPid=$4
    shift 4
    printf '{"session_id":"%s","hook_event_name":"%s","source":"startup"}\n' "$sid" "$event" |
        env LIFE_SYNC_SYNTHETIC=1 LIFE_SYNC_REPO="$repo" \
            LIFE_SYNC_PROCESS_PID="$processPid" "$@" bash "$testHook"
}

run_event_from_short_lived_process() {
    local repo=$1 sid=$2 event=$3
    shift 3
    (
        run_event "$repo" "$sid" "$event" "$BASHPID" "$@"
    )
}

head_oid() {
    git -C "$1" rev-parse HEAD
}

remote_oid() {
    git --git-dir="$(dirname -- "$1")/remote.git" rev-parse refs/heads/master
}

settings_count() {
    local event=$1
    jq --arg event "$event" --arg command "bash ~/.claude/hooks/lifecycle-sync-life-repo.sh" \
        '[.hooks[$event][]?.hooks[]? | select(.command == $command)] | length' "$settingsFile"
}

assert_eq 0 "$(settings_count Stop)" "Stop must not register life synchronization"
assert_eq 1 "$(settings_count SessionStart)" "SessionStart must register interrupted-session recovery once"
assert_eq 1 "$(settings_count SessionEnd)" "SessionEnd must register synchronization once"
assert_eq 0 "$(jq --arg command "bash ~/.claude/hooks/gate-session-record.sh" \
    '[.hooks.SessionEnd[]?.hooks[]? | select(.command == $command)] | length' "$settingsFile")" \
    "SessionEnd debt recording must run inside the serialized synchronization hook"
pass "settings place synchronization only on lifecycle boundaries"

repo=$(new_fixture coalesces)
base=$(head_oid "$repo")
printf 'owned after two turns\n' > "$repo/owned.txt"
write_ledger "$repo" aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa "$repo/owned.txt"
run_event "$repo" aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa Stop "$$"
run_event "$repo" aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa Stop "$$"
assert_eq "$base" "$(head_oid "$repo")" "per-turn Stop must not commit"
assert_eq "$base" "$(remote_oid "$repo")" "per-turn Stop must not push"
run_event_from_short_lived_process "$repo" aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa SessionStart
run_event_from_short_lived_process "$repo" aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa SessionEnd
assert_eq 1 "$(git -C "$repo" rev-list --count "$base..HEAD")" "one session must coalesce to one commit"
assert_eq "$(head_oid "$repo")" "$(remote_oid "$repo")" "SessionEnd must finish its push"
pass "two Stops coalesce into one synchronous SessionEnd commit and push"

repo=$(new_fixture ownership)
base=$(head_oid "$repo")
printf 'owned by ending session\n' > "$repo/owned.txt"
printf 'foreign work\n' > "$repo/foreign.txt"
write_ledger "$repo" bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb "$repo/owned.txt"
run_event_from_short_lived_process "$repo" bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb SessionStart
run_event_from_short_lived_process "$repo" bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb SessionEnd
assert_eq "owned.txt" "$(git -C "$repo" diff-tree --no-commit-id --name-only -r HEAD)" \
    "SessionEnd must commit only paths in its ledger"
assert_eq "?? foreign.txt" "$(git -C "$repo" status --short -- foreign.txt)" \
    "unowned untracked work must remain uncommitted"
assert_eq "$(head_oid "$repo")" "$(remote_oid "$repo")" "owned commit must reach the remote"
pass "SessionEnd cannot sweep another session's unowned path"

# The session-record witness retired with the 2026-09-01 lean-out: SessionEnd now moves an
# active marker straight to recorded. This case keeps the witness from returning unbidden --
# the hook still sweeps end-debt.jsonl into the commit whenever the file exists, so a
# reintroduced writer would silently widen every scoped commit again.
repo=$(new_fixture session-record)
printf 'owned with no witness\n' > "$repo/owned.txt"
write_ledger "$repo" bcbcbcbc-bcbc-bcbc-bcbc-bcbcbcbcbcbc "$repo/owned.txt"
run_event_from_short_lived_process "$repo" bcbcbcbc-bcbc-bcbc-bcbc-bcbcbcbcbcbc SessionEnd
assert_eq "owned.txt" \
    "$(git -C "$repo" diff-tree --no-commit-id --name-only -r HEAD | sort)" \
    "the scoped commit must carry the ledger alone"
[ ! -e "$repo/areas/claude-code-setup/state/end-debt.jsonl" ] ||
    fail "the retired session-record witness must write no debt ledger"
pass "SessionEnd records the marker without a session-record witness"

repo=$(new_fixture active-owner)
base=$(head_oid "$repo")
run_event "$repo" cccccccc-cccc-cccc-cccc-cccccccccccc SessionStart "$$"
write_ledger "$repo" cccccccc-cccc-cccc-cccc-cccccccccccc "$repo/shared.txt"
write_ledger "$repo" dddddddd-dddd-dddd-dddd-dddddddddddd "$repo/shared.txt"
printf 'shared concurrent edit\n' > "$repo/shared.txt"
run_event_from_short_lived_process "$repo" dddddddd-dddd-dddd-dddd-dddddddddddd SessionEnd
assert_eq "$base" "$(head_oid "$repo")" "an ending session must not commit a live owner's shared path"
git -C "$repo" diff --quiet -- shared.txt && fail "shared path should remain dirty"
pass "live ownership conflicts remain dirty for a later boundary"

repo=$(new_fixture recovery)
base=$(head_oid "$repo")
run_event_from_short_lived_process "$repo" eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee SessionStart
printf 'recover me\n' > "$repo/owned.txt"
printf 'do not recover me\n' > "$repo/foreign.txt"
write_ledger "$repo" eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee "$repo/owned.txt"
run_event "$repo" ffffffff-ffff-ffff-ffff-ffffffffffff SessionStart "$$"
assert_eq 1 "$(git -C "$repo" rev-list --count "$base..HEAD")" \
    "next SessionStart must recover an interrupted session"
assert_eq "owned.txt" "$(git -C "$repo" diff-tree --no-commit-id --name-only -r HEAD)" \
    "recovery must remain ledger-scoped"
assert_eq "?? foreign.txt" "$(git -C "$repo" status --short -- foreign.txt)" \
    "recovery must preserve unowned dirt"
assert_eq "$(head_oid "$repo")" "$(remote_oid "$repo")" "recovery must push synchronously"
pass "next SessionStart recovers only a dead session's owned work"

repo=$(new_fixture process-fallback)
base=$(head_oid "$repo")
printf 'sync without process marker\n' > "$repo/owned.txt"
write_ledger "$repo" abababab-abab-abab-abab-abababababab "$repo/owned.txt"
run_event "$repo" abababab-abab-abab-abab-abababababab SessionEnd 99999999
assert_eq 1 "$(git -C "$repo" rev-list --count "$base..HEAD")" \
    "missing process identity must not disable the ordinary SessionEnd sync"
assert_eq "$(head_oid "$repo")" "$(remote_oid "$repo")" \
    "markerless SessionEnd must still push synchronously"
pass "process-marker failure degrades recovery, not current synchronization"

repo=$(new_fixture git-failure)
base=$(head_oid "$repo")
run_event_from_short_lived_process "$repo" cdcdcdcd-cdcd-cdcd-cdcd-cdcdcdcdcdcd SessionStart
printf 'recover after git works again\n' > "$repo/owned.txt"
write_ledger "$repo" cdcdcdcd-cdcd-cdcd-cdcd-cdcdcdcdcdcd "$repo/owned.txt"
run_event "$repo" dededede-dede-dede-dede-dededededede SessionStart "$$" \
    PATH="$failingGitDir:$PATH"
assert_eq "$base" "$(head_oid "$repo")" "a failed status read must not fabricate a clean recovery"
run_event "$repo" efefefef-efef-efef-efef-efefefefefef SessionStart "$$"
assert_eq 1 "$(git -C "$repo" rev-list --count "$base..HEAD")" \
    "a failed status read must retain recovery state for the next boundary"
pass "Git read failure keeps the interrupted session recoverable"

repo=$(new_fixture staged-read-failure)
base=$(head_oid "$repo")
printf 'do not commit after unreadable index projection\n' > "$repo/owned.txt"
write_ledger "$repo" 67676767-6767-6767-6767-676767676767 "$repo/owned.txt"
run_event "$repo" 67676767-6767-6767-6767-676767676767 SessionEnd "$$" \
    PATH="$failingDiffGitDir:$PATH"
assert_eq "$base" "$(head_oid "$repo")" \
    "failure to enumerate staged paths must stop the scoped commit"
pass "staged-path verification fails closed"

repo=$(new_fixture marker-write)
base=$(head_oid "$repo")
sid=78787878-7878-7878-7878-787878787878
run_event "$repo" "$sid" SessionStart "$$"
marker="$repo/.git/life-sync-sessions/${sid:0:8}"
IFS=$'\t' read -r markerPid markerStart _ markerFull < "$marker"
printf '%s\t%s\trecorded\t%s\n' "$markerPid" "$markerStart" "$markerFull" > "$marker.next"
mv "$marker.next" "$marker"
chmod 500 "$repo/.git/life-sync-sessions"
printf 'do not commit without durable state\n' > "$repo/owned.txt"
write_ledger "$repo" "$sid" "$repo/owned.txt"
run_event "$repo" "$sid" SessionEnd "$$"
chmod 700 "$repo/.git/life-sync-sessions"
assert_eq "$base" "$(head_oid "$repo")" \
    "a failed pre-commit marker transition must leave owned work dirty"
pass "commit waits for a durable crash-recovery transition"

repo=$(new_fixture push-recovery)
base=$(head_oid "$repo")
run_event_from_short_lived_process "$repo" 11111111-1111-1111-1111-111111111111 SessionStart
printf 'committed before interruption\n' > "$repo/owned.txt"
write_ledger "$repo" 11111111-1111-1111-1111-111111111111 "$repo/owned.txt"
set +e
run_event_from_short_lived_process "$repo" 11111111-1111-1111-1111-111111111111 SessionEnd \
    LIFE_SYNC_FAIL_AFTER_COMMIT=1
failRc=$?
set -e
[ "$failRc" -ne 0 ] || fail "synthetic post-commit interruption must fire"
assert_eq 1 "$(git -C "$repo" rev-list --count "$base..HEAD")" \
    "post-commit interruption must preserve the local commit"
assert_eq "$base" "$(remote_oid "$repo")" "post-commit interruption must precede push"
run_event "$repo" 22222222-2222-2222-2222-222222222222 SessionStart "$$"
assert_eq "$(head_oid "$repo")" "$(remote_oid "$repo")" \
    "next SessionStart must finish a push interrupted after commit"
pass "interrupted post-commit state is recoverable"

repo=$(new_fixture lock)
base=$(head_oid "$repo")
printf 'wait behind lock\n' > "$repo/owned.txt"
write_ledger "$repo" 33333333-3333-3333-3333-333333333333 "$repo/owned.txt"
exec 8> "$repo/.git/life-sync.lock"
flock -n 8 || fail "test could not acquire fixture lock"
run_event_from_short_lived_process "$repo" 33333333-3333-3333-3333-333333333333 SessionEnd
assert_eq "$base" "$(head_oid "$repo")" "lock contention must defer synchronization"
flock -u 8
exec 8>&-
run_event "$repo" 44444444-4444-4444-4444-444444444444 SessionStart "$$"
assert_eq "$(head_oid "$repo")" "$(remote_oid "$repo")" "next boundary must recover lock-deferred work"
pass "nonblocking lock contention preserves work for recovery"

repo=$(new_fixture staged)
base=$(head_oid "$repo")
printf 'deliberately staged\n' > "$repo/staged.txt"
git -C "$repo" add staged.txt
printf 'owned but deferred\n' > "$repo/owned.txt"
write_ledger "$repo" 55555555-5555-5555-5555-555555555555 "$repo/owned.txt"
run_event_from_short_lived_process "$repo" 55555555-5555-5555-5555-555555555555 SessionEnd
assert_eq "$base" "$(head_oid "$repo")" "pre-staged work must defer auto-commit"
assert_eq "M  staged.txt" "$(git -C "$repo" status --short -- staged.txt)" \
    "pre-staged work must remain staged"
pass "pre-existing index state is preserved"

printf 'PASS: %d lifecycle sync controls\n' "$passCount"
