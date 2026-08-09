#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK="$ROOT/hooks/session-update-check.sh"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fail() {
  echo "$1" >&2
  exit 1
}

git_q() {
  git -c user.email=t@example.com -c user.name=t "$@" >/dev/null 2>&1
}

origin="$tmpdir/origin"
install="$tmpdir/install"

git_q init "$origin"
(cd "$origin" && echo one >file && git_q add file && git_q commit -m one)
git_q clone "$origin" "$install"
(cd "$origin" && echo two >>file && git_q commit -am two && echo three >>file && git_q commit -am three)

out=$(STRATA_HOME="$install" bash "$HOOK")
echo "$out" | grep -q "2 commit(s) behind" || fail "behind install did not produce a 2-commit notice: $out"
echo "$out" | grep -q "pull --ff-only" || fail "notice did not include the update command: $out"

out=$(STRATA_HOME="$install" bash "$HOOK")
[ -z "$out" ] || fail "second check within the rate window was not silent: $out"

rm -f "$install/.local/update-check.stamp"
(cd "$install" && git_q pull --ff-only)
out=$(STRATA_HOME="$install" bash "$HOOK")
[ -z "$out" ] || fail "up-to-date install was not silent: $out"

rm -f "$install/.local/update-check.stamp"
(cd "$install" && echo local >>file && git_q commit -am local)
out=$(STRATA_HOME="$install" bash "$HOOK")
[ -z "$out" ] || fail "locally-ahead install was not silent: $out"

plain="$tmpdir/plain"
mkdir -p "$plain"
out=$(STRATA_HOME="$plain" bash "$HOOK")
[ -z "$out" ] || fail "non-git install was not silent: $out"

# A fork tracks its source through a non-origin remote; fetching only origin
# would compare against a ref that never moved.
fork="$tmpdir/fork"
git_q clone "$origin" "$fork"
(
  cd "$fork"
  git_q remote rename origin upstream
  fork_branch=$(git symbolic-ref --short HEAD)
  git_q branch --set-upstream-to="upstream/$fork_branch" "$fork_branch"
  git_q reset --hard HEAD~2
)
(cd "$origin" && echo four >>file && git_q commit -am four)
out=$(STRATA_HOME="$fork" bash "$HOOK")
echo "$out" | grep -q "behind upstream/" || fail "fork tracking a non-origin remote produced no notice: $out"

echo "session-update-check tests passed"
