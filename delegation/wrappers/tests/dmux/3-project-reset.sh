#!/usr/bin/env bash
set -uo pipefail

SUT=${1:?"usage: $0 SCRIPT_UNDER_TEST"}
SUT=$(realpath "$SUT")
FIXTURE=$(mktemp -d "${TMPDIR:-/tmp}/work75-reset.XXXXXX")

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
printf 'committed\n' > "$FIXTURE/project/user.txt"
git -C "$FIXTURE/project" add user.txt
git -C "$FIXTURE/project" commit -q -m base
printf 'uncommitted work\n' > "$FIXTURE/project/user.txt"

HOME="$FIXTURE/home" PATH="$FIXTURE/bin:/usr/bin:/bin" \
  tmux new-session -d -s dmux-project /usr/bin/tail -f /dev/null

set +e
HOME="$FIXTURE/home" PATH="$FIXTURE/bin:/usr/bin:/bin" \
  "$SUT" --project "$FIXTURE/project" --agent fake-agent --timeout 5 \
  >"$FIXTURE/sut.log" 2>&1
SUT_RC=$?
set -e

AFTER=$(cat "$FIXTURE/project/user.txt")
if [[ "$AFTER" != 'uncommitted work' ]]; then
  printf 'DESTRUCTION: dirty user.txt became %q (sut_rc=%s)\n' "$AFTER" "$SUT_RC"
  tail -n 20 "$FIXTURE/sut.log"
  exit 1
fi
if [[ "$SUT_RC" -ne 0 ]] || ! grep -q 'cleanup complete' "$FIXTURE/sut.log"; then
  printf 'FIXTURE ERROR: state survived but harness did not complete (sut_rc=%s)\n' "$SUT_RC" >&2
  tail -n 20 "$FIXTURE/sut.log" >&2
  exit 2
fi

printf 'PRESERVED: dirty user.txt still contains uncommitted work (sut_rc=%s)\n' "$SUT_RC"
tail -n 20 "$FIXTURE/sut.log"
exit 0
