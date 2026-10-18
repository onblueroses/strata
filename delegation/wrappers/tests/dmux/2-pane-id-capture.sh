#!/usr/bin/env bash
set -uo pipefail

SUT=${1:?"usage: $0 SCRIPT_UNDER_TEST"}
SUT=$(realpath "$SUT")
FIXTURE=$(mktemp -d "${TMPDIR:-/tmp}/work75-pane.XXXXXX")

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
printf '%s\n' '# fixture brief' > "$FIXTURE/brief.md"

FIRST_PANE=$(HOME="$FIXTURE/home" PATH="$FIXTURE/bin:/usr/bin:/bin" \
  tmux new-session -d -P -F '#{pane_id}' -s dmux-project /usr/bin/tail -f /dev/null)
OLD_LAST=$(HOME="$FIXTURE/home" PATH="$FIXTURE/bin:/usr/bin:/bin" \
  tmux split-window -d -P -F '#{pane_id}' -t "$FIRST_PANE" /usr/bin/tail -f /dev/null)
HOME="$FIXTURE/home" PATH="$FIXTURE/bin:/usr/bin:/bin" tmux select-pane -t "$FIRST_PANE"
BEFORE=$(HOME="$FIXTURE/home" PATH="$FIXTURE/bin:/usr/bin:/bin" \
  tmux list-panes -t dmux-project -F '#{pane_id}')

set +e
HOME="$FIXTURE/home" PATH="$FIXTURE/bin:/usr/bin:/bin" \
  "$SUT" --project "$FIXTURE/project" --slug pane-probe \
  --agent "$FIXTURE/bin/fixture-agent" --brief "$FIXTURE/brief.md" \
  --branch-from main --session dmux-project >"$FIXTURE/sut.log" 2>&1
SUT_RC=$?
set -e

AFTER=$(HOME="$FIXTURE/home" PATH="$FIXTURE/bin:/usr/bin:/bin" \
  tmux list-panes -t dmux-project -F '#{pane_id}')
NEW_PANE=$(comm -13 <(printf '%s\n' "$BEFORE" | sort) <(printf '%s\n' "$AFTER" | sort))
LIST_LAST=$(printf '%s\n' "$AFTER" | tail -n 1)
NEW_REMAIN=$(HOME="$FIXTURE/home" PATH="$FIXTURE/bin:/usr/bin:/bin" \
  tmux show-options -p -v -t "$NEW_PANE" remain-on-exit 2>/dev/null || true)
LAST_REMAIN=$(HOME="$FIXTURE/home" PATH="$FIXTURE/bin:/usr/bin:/bin" \
  tmux show-options -p -v -t "$LIST_LAST" remain-on-exit 2>/dev/null || true)

if [[ -z "$NEW_PANE" || "$NEW_PANE" == *$'\n'* ]]; then
  printf 'FIXTURE ERROR: expected exactly one new pane, got %q (sut_rc=%s)\n' "$NEW_PANE" "$SUT_RC" >&2
  sed -n '1,20p' "$FIXTURE/sut.log" >&2
  exit 2
fi

if [[ "$NEW_REMAIN" != "on" ]]; then
  printf 'MISTARGET: created=%s remain=%s list_tail=%s remain=%s old_last=%s (sut_rc=%s)\n' \
    "$NEW_PANE" "${NEW_REMAIN:-unset}" "$LIST_LAST" "${LAST_REMAIN:-unset}" "$OLD_LAST" "$SUT_RC"
  sed -n '1,20p' "$FIXTURE/sut.log"
  exit 1
fi

printf 'PRESERVED: created=%s has remain-on-exit=on; list_tail=%s (sut_rc=%s)\n' \
  "$NEW_PANE" "$LIST_LAST" "$SUT_RC"
sed -n '1,20p' "$FIXTURE/sut.log"
exit 0
