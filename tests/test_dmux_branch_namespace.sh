#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

repo="$tmpdir/repo"
brief="$tmpdir/brief.md"
fakebin="$tmpdir/bin"
mkdir -p "$repo" "$fakebin"

git -C "$repo" init -b main >/dev/null
git -C "$repo" config user.email test@example.invalid
git -C "$repo" config user.name "Test User"
printf 'base\n' >"$repo/file.txt"
git -C "$repo" add file.txt
git -C "$repo" commit -m base >/dev/null
git -C "$repo" checkout -b auth-middleware >/dev/null 2>&1
printf 'protected\n' >"$repo/protected.txt"
git -C "$repo" add protected.txt
git -C "$repo" commit -m protected >/dev/null
protected_ref="$(git -C "$repo" rev-parse auth-middleware)"
git -C "$repo" checkout main >/dev/null 2>&1
printf 'brief\n' >"$brief"

cat >"$fakebin/tmux" <<'SH'
#!/usr/bin/env bash
case "${1:-}" in
  list-sessions)
    printf '%s\n' dmux-branch-test
    ;;
  list-panes)
    printf '%%1\n'
    ;;
  capture-pane)
    printf '%s\n' codex
    ;;
esac
SH
chmod +x "$fakebin/tmux"

cat >"$fakebin/sleep" <<'SH'
#!/usr/bin/env bash
exit 0
SH
chmod +x "$fakebin/sleep"

dispatch_out="$tmpdir/dispatch.out"
dispatch_err="$tmpdir/dispatch.err"
if ! PATH="$fakebin:$PATH" "$ROOT/bin/dmux-dispatch.sh" \
  --project "$repo" \
  --slug auth-middleware \
  --agent codex \
  --brief "$brief" >"$dispatch_out" 2>"$dispatch_err"; then
  cat "$dispatch_err" >&2
  exit 1
fi

# The dispatcher starts a short-lived trust-prompt helper after creating the pane.
sleep 1

current_ref="$(git -C "$repo" rev-parse auth-middleware)"
if [[ "$current_ref" != "$protected_ref" ]]; then
  echo "dispatch changed the existing auth-middleware branch ref" >&2
  exit 1
fi

if ! git -C "$repo" show-ref --verify --quiet refs/heads/dmux/auth-middleware; then
  echo "dispatch did not create the namespaced dmux/auth-middleware branch" >&2
  exit 1
fi

worktree_branch="$(git -C "$repo/.dmux/worktrees/auth-middleware" branch --show-current)"
if [[ "$worktree_branch" != dmux/auth-middleware ]]; then
  echo "worktree checked out $worktree_branch, expected dmux/auth-middleware" >&2
  exit 1
fi
