#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

repo="$tmpdir/api.v2"
brief="$tmpdir/brief.md"
fakebin="$tmpdir/bin"
mkdir -p "$repo" "$fakebin"

git -C "$repo" init -b main >/dev/null
printf 'brief\n' >"$brief"

cat >"$fakebin/tmux" <<'SH'
#!/usr/bin/env bash
case "${1:-}" in
  list-sessions)
    printf '%s\n' dmux-apiXv2 dmux-api.v2
    ;;
esac
SH
chmod +x "$fakebin/tmux"

out="$tmpdir/out"
PATH="$fakebin:$PATH" "$ROOT/bin/dmux-dispatch.sh" \
  --project "$repo" \
  --slug literal-match \
  --agent codex \
  --brief "$brief" \
  --dry-run >"$out"

if ! grep -Fxq 'Using tmux session: dmux-api.v2' "$out"; then
  echo "dispatch did not choose the literal project session" >&2
  cat "$out" >&2
  exit 1
fi

if grep -Fxq 'Using tmux session: dmux-apiXv2' "$out"; then
  echo "dispatch selected a regex-compatible non-literal session" >&2
  cat "$out" >&2
  exit 1
fi
