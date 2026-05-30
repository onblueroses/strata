#!/usr/bin/env bash
# Stop hook: warn if any project repos have unpushed commits.
# Advisory only - exits 0 always. Output appears in session close summary.

WARN_REPOS=()

check_repo() {
    local dir="$1"
    [ -d "$dir/.git" ] || return
    local remote
    remote=$(git -C "$dir" remote get-url origin 2>/dev/null) || return
    local status
    status=$(git -C "$dir" status -sb 2>/dev/null | head -1)
    if echo "$status" | grep -q "\[ahead"; then
        local ahead
        ahead=$(echo "$status" | grep -o '\[ahead [0-9]*\]')
        WARN_REPOS+=("$(basename "$dir") $ahead ($dir)")
    fi
}

# Check Work/ repos
for d in $HOME/Work/*/; do
    check_repo "$d"
done

# Check home-level repos (the stale-clone risk zone)
for d in $HOME/*/; do
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
