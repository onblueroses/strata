#!/usr/bin/env bash
# Stop hook: warn if the current project repo has unpushed commits.
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

# Check only the repository containing the configured scan root (or current directory).
scanRoot="${STRATA_REPO_SCAN_ROOT:-$PWD}"
repoDir=$(git -C "$scanRoot" rev-parse --show-toplevel 2>/dev/null) || repoDir=""
[ -n "$repoDir" ] && check_repo "$repoDir"

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
