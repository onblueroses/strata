#!/usr/bin/env bash
set -euo pipefail
# Any hook_block row this run produces is test output, not a real block: tag it at the
# source so the digest can drop it without a junk-sid denylist (audit I-7).
export TELEMETRY_SYNTHETIC=1
script_dir="$(cd "$(dirname "$0")" && pwd)"; hook="$script_dir/gate-repo-pair-isolation.sh"
tmp="$(mktemp -d)"; trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/private-repo" "$tmp/public-repo" "$tmp/hook-cwd" "$tmp/home/.claude"
git -C "$tmp/private-repo" init -q
git -C "$tmp/public-repo" init -q
git -C "$tmp/private-repo" remote add origin https://github.com/example/public-repo.git
git -C "$tmp/public-repo" remote add origin https://github.com/example/private-repo.git
export PRIVATE_REPO_MATCH=private-repo PUBLIC_REPO_MATCH=public-repo
json() { jq -nc --arg c "$1" '{session_id:"cwd-test",tool_input:{command:$c}}'; }
set +e
blocked="$(cd "$tmp/hook-cwd" && HOME="$tmp/home" printf '%s' "$(json "cd $tmp/private-repo && git push origin main")" | HOME="$tmp/home" bash "$hook" 2>&1)"
rc=$?
set -e
[[ $rc -eq 2 && "$blocked" == *'Cross-push blocked'* ]]

# An active registration must refuse a push when either matcher is absent.
set +e
blocked="$(printf '%s' "$(json "cd $tmp/hook-cwd && git push")" | env -u PRIVATE_REPO_MATCH HOME="$tmp/home" bash "$hook" 2>&1)"
rc=$?
set -e
[[ $rc -eq 2 && "$blocked" == *'configure both'* ]]

# A trailing `cd elsewhere` after the push must not move the resolved target off the
# private repo (regression: tail -1 cd resolution picked the last cd and let it through).
run() { set +e; out="$(cd "$tmp/hook-cwd" && printf '%s' "$(json "$1")" | HOME="$tmp/home" bash "$hook" 2>&1)"; rc=$?; set -e; }
run "cd $tmp/private-repo && git push origin main && cd $tmp/public-repo"
[[ $rc -eq 2 ]]
# A second `git -C otherrepo` in the same line must not become the resolved push target.
run "git -C $tmp/private-repo push origin main && git -C $tmp/public-repo status"
[[ $rc -eq 2 ]]
# The reverse direction is blocked too.
run "cd $tmp/public-repo && git push origin main"
[[ $rc -eq 2 ]]
# A safe push stays allowed even when a later cd names the private repo.
git -C "$tmp/hook-cwd" init -q 2>/dev/null; git -C "$tmp/hook-cwd" remote add origin https://github.com/example/safe.git 2>/dev/null || true
run "cd $tmp/hook-cwd && git push && cd $tmp/private-repo"
[[ $rc -eq 0 ]]

[[ "$(cd "$tmp/hook-cwd" && HOME="$tmp/home" printf '%s' "$(json 'echo git push is just text')" | HOME="$tmp/home" bash "$hook")" == "" ]]
printf 'gate-repo-pair-isolation: both cross-push directions blocked; unset matchers refuse; per-segment target resolved\n'
