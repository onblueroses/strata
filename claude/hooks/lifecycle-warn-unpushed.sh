#!/usr/bin/env bash
# Stop hook: warn if any project repos have unpushed commits.
# Advisory only - exits 0 always. Output appears in session close summary.

WARN_REPOS=()
WORK_ROOT="${UNPUSHED_WORK_ROOT:-$HOME/Work}"
HOME_ROOT="$HOME"
if [ "${UNPUSHED_SYNTHETIC:-0}" = 1 ]; then
    WORK_ROOT=${UNPUSHED_WORK_ROOT:-$WORK_ROOT}
    HOME_ROOT=${UNPUSHED_HOME_ROOT:-$HOME_ROOT}
fi

check_repo() {
    local dir="$1"
    [ -d "$dir/.git" ] || return
    local refs headMarker track ahead
    refs=$(LC_ALL=C git -C "$dir" for-each-ref \
        --format='%(HEAD)%09%(upstream:track)' refs/heads 2>/dev/null) || return
    headMarker=""
    track=""
    while IFS=$'\t' read -r headMarker track; do
        [ "$headMarker" = "*" ] && break
    done <<< "$refs"
    [ "$headMarker" = "*" ] || return
    [[ $track =~ \[ahead[[:space:]]([0-9]+) ]] || return
    ahead=${BASH_REMATCH[1]}
    git -C "$dir" config --get remote.origin.url >/dev/null 2>&1 || return
    WARN_REPOS+=("$(basename "$dir") [ahead $ahead] ($dir)")
}

# Check Work/ repos
for d in "$WORK_ROOT"/*/; do
    check_repo "$d"
done

# Check home-level repos (the stale-clone risk zone)
for d in "$HOME_ROOT"/*/; do
    [[ "$d" == */Work/* ]] && continue
    [[ "$d" == */.* ]] && continue
    [[ "$d" == */to-delete/* ]] && continue
    check_repo "$d"
done

if [ ${#WARN_REPOS[@]} -gt 0 ]; then
    echo ""
    echo "WARNING: Unpushed commits in ${#WARN_REPOS[@]} repo(s):"
    for r in "${WARN_REPOS[@]}"; do
        echo "  - $r"
    done
    echo "Run 'git push' in each or re-run /end to push."
    echo ""
fi

exit 0
