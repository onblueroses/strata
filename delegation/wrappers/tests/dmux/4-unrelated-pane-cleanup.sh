#!/usr/bin/env bash
set -uo pipefail

SUT=${1:?"usage: $0 SCRIPT_UNDER_TEST"}
SUT=$(realpath "$SUT")
FIXTURE=$(mktemp -d "${TMPDIR:-/tmp}/work75-cleanup-pane.XXXXXX")

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
cat > "$FIXTURE/bin/fake-agent" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
cat > "$FIXTURE/bin/dmux-dispatch.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

if [[ ${1:-} == --help ]]; then
  echo 'Usage: fixture dispatch'
  exit 0
fi
if [[ $# -eq 0 ]]; then
  echo 'required arguments missing'
  exit 1
fi

PROJECT='' SLUG='' BRIEF='' BRANCH_FROM=main DRY_RUN=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --project) PROJECT=$2; shift 2 ;;
    --slug) SLUG=$2; shift 2 ;;
    --brief) BRIEF=$2; shift 2 ;;
    --branch-from) BRANCH_FROM=$2; shift 2 ;;
    --agent|--permission-mode|--session) shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    *) shift ;;
  esac
done

if [[ ! "$SLUG" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
  echo 'slug must be lowercase'
  exit 1
fi
if [[ ! -d "$PROJECT/.git" ]]; then
  echo 'not a git repo'
  exit 1
fi
if $DRY_RUN; then
  echo '[dry-run] ln -sfn scratchpad'
  echo '[dry-run] task-brief.md'
  echo '=== Dispatched fixture ==='
  exit 0
fi

WORKTREE="$PROJECT/.dmux/worktrees/$SLUG"
mkdir -p "$PROJECT/.dmux/worktrees" "$PROJECT/.dmux/scratchpad"
git -C "$PROJECT" worktree add -q "$WORKTREE" -b "$SLUG" "$BRANCH_FROM"
cp "$BRIEF" "$WORKTREE/.task-brief.md"
mkdir -p "$WORKTREE/.dmux"
ln -sfn "$PROJECT/.dmux/scratchpad" "$WORKTREE/.dmux/scratchpad"
printf '%s\n' '.task-brief.md' '.task-result.md' '.task-blocked.md' '.dmux/' >> "$WORKTREE/.gitignore"
printf 'harness-pass\n' > "$WORKTREE/harness-output.txt"
printf 'harness note\n' > "$PROJECT/.dmux/scratchpad/$SLUG.md"
cat > "$WORKTREE/.task-result.md" <<RESULT
---
status: complete
---
## Summary
fixture completed
## Surprises
none
RESULT
git -C "$WORKTREE" add .gitignore harness-output.txt
git -C "$WORKTREE" -c user.name=work75 -c user.email=example.invalid commit -q -m harness
SESSION=$(tmux list-sessions -F '#{session_name}' | grep -m1 '^dmux')
tmux split-window -d -t "$SESSION" /usr/bin/tail -f /dev/null
echo '=== Dispatched fixture ==='
EOF
chmod +x "$FIXTURE/bin/tmux" "$FIXTURE/bin/fake-agent" "$FIXTURE/bin/dmux-dispatch.sh"

git -C "$FIXTURE/project" init -q -b main
git -C "$FIXTURE/project" config user.name work75
git -C "$FIXTURE/project" config user.email example.invalid
printf 'base\n' > "$FIXTURE/project/base.txt"
git -C "$FIXTURE/project" add base.txt
git -C "$FIXTURE/project" commit -q -m base

FIRST_PANE=$(HOME="$FIXTURE/home" PATH="$FIXTURE/bin:/usr/bin:/bin" \
  tmux new-session -d -P -F '#{pane_id}' -s dmux-project /usr/bin/tail -f /dev/null)
UNRELATED_PANE=$(HOME="$FIXTURE/home" PATH="$FIXTURE/bin:/usr/bin:/bin" \
  tmux split-window -d -P -F '#{pane_id}' -t "$FIRST_PANE" /usr/bin/tail -f /dev/null)

set +e
# Five seconds is the harness's own polling quantum and therefore its minimum observable timeout.
HOME="$FIXTURE/home" PATH="$FIXTURE/bin:/usr/bin:/bin" \
  "$SUT" --project "$FIXTURE/project" --agent fake-agent --timeout 5 \
  >"$FIXTURE/sut.log" 2>&1
SUT_RC=$?
set -e

# display-message exits 0 even for a missing pane target (measured 2026-08-14),
# so pane liveness must be an exact match against the pane list.
if ! HOME="$FIXTURE/home" PATH="$FIXTURE/bin:/usr/bin:/bin" \
  tmux list-panes -a -F '#{pane_id}' 2>/dev/null | grep -qx "$UNRELATED_PANE"; then
  printf 'DESTRUCTION: unrelated pane %s was killed (sut_rc=%s)\n' "$UNRELATED_PANE" "$SUT_RC"
  cat "$FIXTURE/sut.log"
  exit 1
fi
if [[ "$SUT_RC" -ne 0 ]] || ! grep -q 'cleanup complete' "$FIXTURE/sut.log"; then
  printf 'FIXTURE ERROR: pane survived but harness did not complete (sut_rc=%s)\n' "$SUT_RC" >&2
  cat "$FIXTURE/sut.log" >&2
  exit 2
fi

printf 'PRESERVED: unrelated pane %s remains live (sut_rc=%s)\n' "$UNRELATED_PANE" "$SUT_RC"
cat "$FIXTURE/sut.log"
exit 0
