#!/usr/bin/env bash
set -uo pipefail

SUT=${1:?"usage: $0 SCRIPT_UNDER_TEST"}
SUT=$(realpath "$SUT")
FIXTURE=$(mktemp -d "${TMPDIR:-/tmp}/work75-branch.XXXXXX")

cleanup() {
  /usr/bin/tmux -L work75 kill-server >/dev/null 2>&1 || true
  rm -rf -- "$FIXTURE"
}
trap cleanup EXIT HUP INT TERM

/usr/bin/tmux -L work75 kill-server >/dev/null 2>&1 || true
mkdir -p "$FIXTURE/home" "$FIXTURE/bin" "$FIXTURE/project"
cat > "$FIXTURE/bin/tmux" <<'EOF'
#!/usr/bin/env bash
exec /usr/bin/tmux -L work75 "$@"
EOF
cat > "$FIXTURE/bin/fixture-agent" <<'EOF'
#!/usr/bin/env bash
exec /usr/bin/tail -f /dev/null
EOF
chmod +x "$FIXTURE/bin/tmux" "$FIXTURE/bin/fixture-agent"

git -C "$FIXTURE/project" init -q -b main
git -C "$FIXTURE/project" config user.name work75
git -C "$FIXTURE/project" config user.email example.invalid
printf 'base\n' > "$FIXTURE/project/base.txt"
git -C "$FIXTURE/project" add base.txt
git -C "$FIXTURE/project" commit -q -m base
git -C "$FIXTURE/project" switch -q -c occupied
printf 'unique branch work\n' > "$FIXTURE/project/unique.txt"
git -C "$FIXTURE/project" add unique.txt
git -C "$FIXTURE/project" commit -q -m unique
UNIQUE_COMMIT=$(git -C "$FIXTURE/project" rev-parse refs/heads/occupied)
git -C "$FIXTURE/project" switch -q main
printf '%s\n' '# fixture brief' > "$FIXTURE/brief.md"

HOME="$FIXTURE/home" PATH="$FIXTURE/bin:/usr/bin:/bin" \
  tmux new-session -d -s dmux-project /usr/bin/tail -f /dev/null

set +e
HOME="$FIXTURE/home" PATH="$FIXTURE/bin:/usr/bin:/bin" \
  "$SUT" --project "$FIXTURE/project" --slug occupied \
  --agent "$FIXTURE/bin/fixture-agent" --brief "$FIXTURE/brief.md" \
  --branch-from main --session dmux-project >"$FIXTURE/sut.log" 2>&1
SUT_RC=$?
set -e

AFTER_COMMIT=$(git -C "$FIXTURE/project" rev-parse refs/heads/occupied 2>/dev/null || true)
if [[ "$AFTER_COMMIT" != "$UNIQUE_COMMIT" ]]; then
  printf 'DESTRUCTION: occupied moved from %s to %s (sut_rc=%s)\n' \
    "$UNIQUE_COMMIT" "${AFTER_COMMIT:-missing}" "$SUT_RC"
  sed -n '1,20p' "$FIXTURE/sut.log"
  exit 1
fi

printf 'PRESERVED: occupied remains at %s (sut_rc=%s)\n' "$UNIQUE_COMMIT" "$SUT_RC"
sed -n '1,20p' "$FIXTURE/sut.log"
exit 0
