#!/usr/bin/env bash
# SessionStart hook: surface a notice when the strata install is behind its
# remote. Rate-limited to one network check per day; every failure path is
# silent (fail-open) so an offline machine or a non-git install pays nothing.

set -uo pipefail

STRATA_HOME="${STRATA_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
STAMP_DIR="$STRATA_HOME/.local"
STAMP="$STAMP_DIR/update-check.stamp"
INTERVAL_SECONDS=86400

git -C "$STRATA_HOME" rev-parse --git-dir >/dev/null 2>&1 || exit 0

# Refresh the remote this branch really tracks; a fork usually tracks "upstream",
# and fetching only "origin" would compare against a ref that never moved.
branch=$(git -C "$STRATA_HOME" symbolic-ref --quiet --short HEAD 2>/dev/null)
remote=""
if [ -n "$branch" ]; then
  remote=$(git -C "$STRATA_HOME" config --get "branch.$branch.remote" 2>/dev/null)
fi
# "." tracks a local branch, so no remote carries updates.
[ "$remote" = "." ] && exit 0
[ -n "$remote" ] || remote="origin"
git -C "$STRATA_HOME" remote get-url "$remote" >/dev/null 2>&1 || exit 0

if [ -f "$STAMP" ]; then
  now=$(date +%s)
  last=$(stat -c %Y "$STAMP" 2>/dev/null || echo 0)
  [ $((now - last)) -lt "$INTERVAL_SECONDS" ] && exit 0
fi
mkdir -p "$STAMP_DIR" 2>/dev/null || exit 0
touch "$STAMP" 2>/dev/null || exit 0

timeout 8 git -C "$STRATA_HOME" fetch --quiet "$remote" 2>/dev/null || exit 0

upstream=$(git -C "$STRATA_HOME" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null)
if [ -z "$upstream" ]; then
  for candidate in "$remote/main" "$remote/master"; do
    if git -C "$STRATA_HOME" rev-parse --verify --quiet "$candidate" >/dev/null 2>&1; then
      upstream="$candidate"
      break
    fi
  done
fi
[ -n "$upstream" ] || exit 0

behind=$(git -C "$STRATA_HOME" rev-list --count "HEAD..$upstream" 2>/dev/null || echo 0)
ahead=$(git -C "$STRATA_HOME" rev-list --count "$upstream..HEAD" 2>/dev/null || echo 0)

# A locally-ahead tree belongs to a developer; stay quiet.
[ "$behind" -gt 0 ] && [ "$ahead" -eq 0 ] || exit 0

echo "strata update available: this install is $behind commit(s) behind $upstream."
echo "Update with: git -C \"\$STRATA_HOME\" pull --ff-only"

exit 0
