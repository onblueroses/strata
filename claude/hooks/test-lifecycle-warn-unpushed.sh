#!/usr/bin/env bash
set -euo pipefail

rootDir=$(cd "$(dirname -- "$0")/.." && pwd -P)
sourceHook="$rootDir/hooks/lifecycle-warn-unpushed.sh"
scratchDir=$(mktemp -d /tmp/work214-unpushed.XXXXXX)
toDeleteDir=${TO_DELETE_DIR:-${TMPDIR:-/tmp}/strata-test-to-delete}
testHook="$scratchDir/lifecycle-warn-unpushed.sh"
workRoot="$scratchDir/home/Work"
homeRoot="$scratchDir/home"
remoteRoot="$scratchDir/remotes"
gitTrace="$scratchDir/git-trace.log"
gitWrapperDir="$scratchDir/bin"
passCount=0

cleanup() {
    local archiveDir
    archiveDir="$toDeleteDir/$(basename -- "$scratchDir")"
    if [ -e "$scratchDir" ]; then
        mkdir -p -- "$toDeleteDir"
        mv -- "$scratchDir" "$archiveDir"
        printf '%s | %s | %s | %s\n' \
            "$(basename -- "$archiveDir")" "$scratchDir" "$(date +%F)" \
            "a ticket unpushed-warning fixture" >> "$toDeleteDir/manifest.txt"
    fi
}
trap cleanup EXIT

mkdir -p "$workRoot" "$remoteRoot" "$gitWrapperDir"

# Redirect the predecessor's literal estate loops when this test runs red. The replacement
# reads these synthetic roots directly, so the rewrite becomes a no-op after implementation.
# shellcheck disable=SC2016
sed \
    -e 's|for d in $HOME/Work/\*/; do|for d in "$UNPUSHED_WORK_ROOT"/*/; do|' \
    -e 's|for d in $HOME/\*/; do|for d in "$UNPUSHED_HOME_ROOT"/*/; do|' \
    "$sourceHook" > "$testHook"
chmod +x "$testHook"

realGit=$(command -v git)
# The generated wrapper expands its arguments only when the hook invokes it.
# shellcheck disable=SC2016
printf '%s\n' '#!/usr/bin/env bash' \
    'printf '\''%s\n'\'' "$*" >> "$UNPUSHED_GIT_TRACE"' \
    "exec $realGit \"\$@\"" > "$gitWrapperDir/git"
chmod +x "$gitWrapperDir/git"

fail() {
    printf 'FAIL: %s\n' "$*" >&2
    exit 1
}

pass() {
    passCount=$((passCount + 1))
    printf 'ok %d - %s\n' "$passCount" "$1"
}

assert_has() {
    local haystack=$1 needle=$2 message=$3
    [[ $haystack == *"$needle"* ]] || fail "$message (missing '$needle')"
}

assert_lacks() {
    local haystack=$1 needle=$2 message=$3
    [[ $haystack != *"$needle"* ]] || fail "$message (found '$needle')"
}

new_repo() {
    local repo=$1 remoteName=${2:-origin}
    local remote
    remote="$remoteRoot/$(basename -- "$repo").git"
    mkdir -p "$(dirname -- "$repo")"
    git init -q --bare "$remote"
    git --git-dir="$remote" symbolic-ref HEAD refs/heads/master
    git init -q -b master "$repo"
    git -C "$repo" config user.email example.invalid
    git -C "$repo" config user.name "Unpushed test"
    printf 'seed\n' > "$repo/seed.txt"
    git -C "$repo" add seed.txt
    git -C "$repo" commit -qm "Initialize fixture"
    git -C "$repo" remote add "$remoteName" "$remote"
    git -C "$repo" push -q -u "$remoteName" master
}

commit_file() {
    local repo=$1 file=$2 content=$3
    printf '%s\n' "$content" > "$repo/$file"
    git -C "$repo" add "$file"
    git -C "$repo" commit -qm "Update fixture"
}

push_remote_commit() {
    local repo=$1 name=$2
    local clone="$scratchDir/writers/$name"
    mkdir -p "$(dirname -- "$clone")"
    git clone -q "$(git -C "$repo" remote get-url origin)" "$clone"
    git -C "$clone" config user.email example.invalid
    git -C "$clone" config user.name "Remote writer"
    printf '%s\n' "$name" > "$clone/$name.txt"
    git -C "$clone" add "$name.txt"
    git -C "$clone" commit -qm "Advance remote fixture"
    git -C "$clone" push -q origin master
    git -C "$repo" fetch -q origin
}

aheadRepo="$workRoot/ahead-work"
new_repo "$aheadRepo"
commit_file "$aheadRepo" ahead.txt ahead

divergedRepo="$workRoot/diverged-work"
new_repo "$divergedRepo"
commit_file "$divergedRepo" local.txt local
push_remote_commit "$divergedRepo" diverged-remote

alternateRepo="$workRoot/origin-with-backup-work"
new_repo "$alternateRepo"
alternateRemote="$remoteRoot/origin-with-backup-alt.git"
git init -q --bare "$alternateRemote"
git --git-dir="$alternateRemote" symbolic-ref HEAD refs/heads/master
git -C "$alternateRepo" remote add backup "$alternateRemote"
git -C "$alternateRepo" push -q -u backup master
commit_file "$alternateRepo" local.txt local

equalRepo="$homeRoot/equal-home"
new_repo "$equalRepo"
printf 'dirty but not ahead\n' >> "$equalRepo/seed.txt"

behindRepo="$homeRoot/behind-home"
new_repo "$behindRepo"
push_remote_commit "$behindRepo" behind-remote

noUpstreamRepo="$homeRoot/no-upstream-home"
new_repo "$noUpstreamRepo"
git -C "$noUpstreamRepo" branch --unset-upstream
commit_file "$noUpstreamRepo" local.txt local

missingOriginRepo="$homeRoot/missing-origin-home"
new_repo "$missingOriginRepo" backup
commit_file "$missingOriginRepo" local.txt local

staleOriginRepo="$homeRoot/stale-origin-home"
new_repo "$staleOriginRepo"
commit_file "$staleOriginRepo" local.txt local
git -C "$staleOriginRepo" config --unset remote.origin.url

unbornRepo="$homeRoot/unborn-home"
git init -q -b master "$unbornRepo"
git -C "$unbornRepo" remote add origin "$remoteRoot/unborn-home.git"

set +e
output=$(PATH="$gitWrapperDir:$PATH" UNPUSHED_SYNTHETIC=1 \
    UNPUSHED_WORK_ROOT="$workRoot" UNPUSHED_HOME_ROOT="$homeRoot" \
    UNPUSHED_GIT_TRACE="$gitTrace" bash "$testHook" 2>&1)
rc=$?
set -e

[ "$rc" -eq 0 ] || fail "advisory hook returned $rc"
pass "the hook remains advisory"

assert_has "$output" "WARNING: Unpushed commits in 3 repo(s):" \
    "warning count must include only ahead repositories"
assert_has "$output" "ahead-work [ahead 1] ($aheadRepo/)" "ahead repository missing"
assert_has "$output" "diverged-work [ahead 1] ($divergedRepo/)" "diverged repository missing"
assert_has "$output" "origin-with-backup-work [ahead 1] ($alternateRepo/)" \
    "repository with origin and a different upstream missing"
pass "ahead, diverged, and alternate-upstream refs retain exact commit counts"

for quietName in equal-home behind-home no-upstream-home missing-origin-home stale-origin-home unborn-home; do
    assert_lacks "$output" "$quietName" "$quietName must remain non-warning"
done
pass "equal, behind, no-upstream, missing/stale-origin, and unborn repositories stay quiet"

trace=$(cat "$gitTrace")
assert_lacks "$trace" " status " "the hook must not refresh worktrees or indexes"
assert_lacks "$trace" "status -sb" "the hook must not invoke status at command start"
assert_has "$trace" "for-each-ref" "the hook must compare commit refs"
pass "Git trace contains ref comparisons and no worktree scan"

assert_has "$output" "Run 'git push' in each or re-run /end to push." \
    "operator recovery guidance changed"
pass "warning guidance is preserved"

printf 'PASS: %d ref-only unpushed controls\n' "$passCount"
