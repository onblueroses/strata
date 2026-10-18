#!/usr/bin/env bash
# Refuse to stage control files unless origin/main is the reviewed tree and all
# control changes since the last deployment carry the configured owner identity.
# Usage: BRIDGE_OWNER_NAME=... verify-reviewed.sh <reviewed-commit> <deployed-rev-file>
set -euo pipefail
repo="$(cd "$(dirname "$0")/.." && pwd)"
reviewed="${1:?reviewed commit required}"
rev_file="${2:?root-controlled DEPLOYED_REV file required}"
owner="${BRIDGE_OWNER_NAME:?BRIDGE_OWNER_NAME required}"
[ -r "$rev_file" ] || { echo 'refusing: deployed revision unreadable' >&2; exit 1; }
last="$(cat "$rev_file")"
reviewed="$(git -C "$repo" rev-parse --verify "$reviewed^{commit}")"
main="$(git -C "$repo" rev-parse --verify refs/remotes/origin/main^{commit})"
last="$(git -C "$repo" rev-parse --verify "$last^{commit}")"
controls=(tools AGENTS.md ASSISTANT.md bridge-policy.toml)
git -C "$repo" merge-base --is-ancestor "$last" "$reviewed" || { echo 'refusing: deployed revision is not an ancestor' >&2; exit 1; }
git -C "$repo" merge-base --is-ancestor "$reviewed" "$main" || { echo 'refusing: reviewed commit is not on origin/main' >&2; exit 1; }
git -C "$repo" diff --quiet "$reviewed" "$main" -- "${controls[@]}" || { echo 'refusing: main control files differ from reviewed commit' >&2; exit 1; }
while IFS= read -r commit; do
  [ -n "$commit" ] || continue
  author="$(git -C "$repo" show -s --format=%an "$commit")"
  committer="$(git -C "$repo" show -s --format=%cn "$commit")"
  [ "$author" = "$owner" ] && [ "$committer" = "$owner" ] || { echo "refusing: control change $commit has a different author or committer" >&2; exit 1; }
done < <(git -C "$repo" log --format=%H "$last..$main" -- "${controls[@]}")
printf '%s\n' "$reviewed"
