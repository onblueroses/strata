#!/usr/bin/env bash
# End-to-end install contract: disposable checkout, disposable HOME, real hooks.

set -uo pipefail

SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEST_ROOT="$(mktemp -d /tmp/strata-fresh-install.XXXXXX)"

cleanup() {
  python3 - "$TEST_ROOT" <<'PY'
from pathlib import Path
import shutil
import sys

root = Path(sys.argv[1]).resolve()
expected_parent = Path("/tmp")
if root.parent != expected_parent or not root.name.startswith("strata-fresh-install."):
    raise SystemExit(f"refusing to clean unexpected test root: {root}")
shutil.rmtree(root)
PY
}
trap cleanup EXIT

HOME="$TEST_ROOT/home"
INSTALL_ROOT="$HOME/.strata"
KB_DIR="$HOME/kb"
STATE_DIR="$HOME/state"
RUN_DIR="$HOME/run"
SPECS_DIR="$STATE_DIR/specs"
PROJECT_DIR="$HOME/project"
export HOME KB_DIR STATE_DIR RUN_DIR SPECS_DIR
mkdir -p "$HOME" "$STATE_DIR" "$RUN_DIR" "$PROJECT_DIR"
PATH="/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin"
XDG_CONFIG_HOME="$HOME/.config"
XDG_CACHE_HOME="$HOME/.cache"
XDG_DATA_HOME="$HOME/.local/share"
PIP_CONFIG_FILE="/dev/null"
GIT_CONFIG_GLOBAL="/dev/null"
export PATH XDG_CONFIG_HOME XDG_CACHE_HOME XDG_DATA_HOME
export PIP_CONFIG_FILE GIT_CONFIG_GLOBAL
SOURCE_STATUS_BEFORE="$(git -C "$SOURCE_ROOT" status --porcelain=v1 --untracked-files=all)"

python3 - "$SOURCE_ROOT" "$INSTALL_ROOT" <<'PY'
from pathlib import Path
import os
import shutil
import subprocess
import sys

source = Path(sys.argv[1]).resolve()
target = Path(sys.argv[2]).resolve()
tracked = subprocess.run(
    ["git", "-C", str(source), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
    check=True,
    stdout=subprocess.PIPE,
).stdout.split(b"\0")

for raw_path in tracked:
    if not raw_path:
        continue
    relative = Path(os.fsdecode(raw_path))
    source_path = source / relative
    target_path = target / relative
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if source_path.is_symlink():
        target_path.symlink_to(os.readlink(source_path))
    else:
        try:
            shutil.copy2(source_path, target_path)
        except FileNotFoundError:
            # The listing and the copy are two moments. A file removed between them
            # means the checkout moved under us, so the staged tree is not the tree
            # under test.
            raise SystemExit(f"source changed during staging: {relative}")
PY
stage_status=$?

# Every later assertion runs the staged copy. When staging is incomplete they all
# fail for one reason, which reads as many broken behaviours instead of one broken
# setup. Stop here and say which it is.
if [[ "$stage_status" -ne 0 ]]; then
  echo "ERROR: could not stage the source checkout into $INSTALL_ROOT" >&2
  exit 1
fi
for required in bin/strata-init bin/strata-doctor settings.json; do
  if [[ ! -e "$INSTALL_ROOT/$required" ]]; then
    echo "ERROR: staged tree is missing $required; refusing to run install checks" >&2
    exit 1
  fi
done


PASSED=0
FAILED=0
SKIPPED=0

pass_check() {
  PASSED=$((PASSED + 1))
  printf 'PASS: %s\n' "$1"
}

fail_check() {
  FAILED=$((FAILED + 1))
  printf 'FAIL: %s\n' "$1" >&2
}

skip_check() {
  SKIPPED=$((SKIPPED + 1))
  printf 'SKIP: %s\n' "$1"
}

DOCUMENTED_EXECUTABLES=(
  bin/strata-init
  bin/strata-doctor
  bin/strong
  bin/fast
  bin/grader
  bin/breadth
  bin/dmux-dispatch.sh
)
for executable in "${DOCUMENTED_EXECUTABLES[@]}"; do
  indexed_mode="$(git -C "$SOURCE_ROOT" ls-files -s -- "$executable" | awk '{print $1}')"
  if [[ "$indexed_mode" == "100755" ]]; then
    pass_check "documented entry point is executable in the index: $executable"
  else
    fail_check "documented entry point is not executable in the index: $executable (mode ${indexed_mode:-missing})"
  fi
done

REAL_PYTHON="$(command -v python3)"

snapshot_tree() {
  "$REAL_PYTHON" - "$1" <<'PY'
from hashlib import sha256
from pathlib import Path
import os
import stat
import sys

root = Path(sys.argv[1])
paths = [root]
if root.exists():
    paths.extend(sorted(root.rglob("*")))
for path in paths:
    details = path.lstat()
    relative = "." if path == root else path.relative_to(root).as_posix()
    fields = [
        relative,
        oct(stat.S_IMODE(details.st_mode)),
        str(details.st_size),
        str(details.st_mtime_ns),
    ]
    if path.is_symlink():
        fields.extend(["symlink", os.readlink(path)])
    elif path.is_file():
        fields.extend(["file", sha256(path.read_bytes()).hexdigest()])
    elif path.is_dir():
        fields.append("directory")
    else:
        fields.append("other")
    print("\t".join(fields))
PY
}

# A Python version failure must happen before the installer touches either root.
VERSION_INSTALL_ROOT="$TEST_ROOT/version-install"
VERSION_HOME="$TEST_ROOT/version-home"
OLD_PYTHON_BIN="$TEST_ROOT/python-3.9-bin"
cp -a "$INSTALL_ROOT" "$VERSION_INSTALL_ROOT"
mkdir -p "$VERSION_HOME" "$OLD_PYTHON_BIN"
cat >"$OLD_PYTHON_BIN/python3" <<'EOF'
#!/usr/bin/env bash
if [[ ${1:-} == "-c" ]]; then
  printf '3.9.0\n'
fi
exit 1
EOF
chmod +x "$OLD_PYTHON_BIN/python3"

VERSION_HOME_BEFORE="$(snapshot_tree "$VERSION_HOME")"
VERSION_INSTALL_BEFORE="$(snapshot_tree "$VERSION_INSTALL_ROOT")"
OLD_PYTHON_INIT_LOG="$TEST_ROOT/install-python-3.9.log"
HOME="$VERSION_HOME" SHELL="/bin/bash" PATH="$OLD_PYTHON_BIN:$PATH" \
  "$VERSION_INSTALL_ROOT/bin/strata-init" --non-interactive "$VERSION_INSTALL_ROOT" \
  </dev/null >"$OLD_PYTHON_INIT_LOG" 2>&1
old_python_init_status=$?
VERSION_HOME_AFTER="$(snapshot_tree "$VERSION_HOME")"
VERSION_INSTALL_AFTER="$(snapshot_tree "$VERSION_INSTALL_ROOT")"

if [[ "$old_python_init_status" -ne 0 ]] && \
    grep -qF 'Python 3.10 or newer' "$OLD_PYTHON_INIT_LOG" && \
    grep -qF 'found 3.9.0' "$OLD_PYTHON_INIT_LOG"; then
  pass_check "installer rejects Python 3.9 with the measured 3.10 requirement"
else
  fail_check "installer did not reject Python 3.9 with an actionable 3.10 requirement"
fi
if [[ "$VERSION_HOME_AFTER" == "$VERSION_HOME_BEFORE" && \
      "$VERSION_INSTALL_AFTER" == "$VERSION_INSTALL_BEFORE" ]]; then
  pass_check "Python version rejection occurs before any install or HOME write"
else
  fail_check "installer wrote files before rejecting the unsupported Python version"
fi

OLD_PYTHON_DOCTOR_LOG="$TEST_ROOT/doctor-python-3.9.log"
HOME="$VERSION_HOME" STRATA_HOME="$VERSION_INSTALL_ROOT" \
  PATH="$OLD_PYTHON_BIN:$PATH" "$VERSION_INSTALL_ROOT/bin/strata-doctor" \
  >"$OLD_PYTHON_DOCTOR_LOG" 2>&1
old_python_doctor_status=$?
if [[ "$old_python_doctor_status" -ne 0 ]] && \
    grep -qF 'OUTDATED required python3' "$OLD_PYTHON_DOCTOR_LOG" && \
    grep -qF 'Python 3.10 or newer' "$OLD_PYTHON_DOCTOR_LOG" && \
    grep -qF 'found 3.9.0' "$OLD_PYTHON_DOCTOR_LOG"; then
  pass_check "doctor rejects Python 3.9 and reports the measured minimum"
else
  fail_check "doctor did not reject Python 3.9 with the measured 3.10 requirement"
fi

# Marker corruption must stop at the rc file. Removing a later seed source keeps
# the pre-fix failure path isolated and fast without changing the source checkout.
MARKER_INSTALL_ROOT="$TEST_ROOT/marker-install"
cp -a "$INSTALL_ROOT" "$MARKER_INSTALL_ROOT"
mv "$MARKER_INSTALL_ROOT/config/private-tokens.example.txt" \
  "$MARKER_INSTALL_ROOT/config/private-tokens.example.unavailable"
BEGIN_MARK='# >>> strata env >>>'
END_MARK='# <<< strata env <<<'

run_marker_install() {
  local marker_home="$1" log_path="$2"
  HOME="$marker_home" SHELL="/bin/bash" \
    "$MARKER_INSTALL_ROOT/bin/strata-init" --non-interactive "$MARKER_INSTALL_ROOT" \
    </dev/null >"$log_path" 2>&1
  MARKER_STATUS=$?
}

UNMATCHED_HOME="$TEST_ROOT/marker-unmatched-begin"
UNMATCHED_RC="$UNMATCHED_HOME/.bashrc"
UNMATCHED_ORIGINAL="$TEST_ROOT/marker-unmatched-begin.original"
mkdir -p "$UNMATCHED_HOME"
printf '%s\n' 'user line before' "$BEGIN_MARK" 'user line after stale marker' \
  >"$UNMATCHED_RC"
cp -p "$UNMATCHED_RC" "$UNMATCHED_ORIGINAL"
UNMATCHED_LOG_ONE="$TEST_ROOT/marker-unmatched-begin-one.log"
UNMATCHED_LOG_TWO="$TEST_ROOT/marker-unmatched-begin-two.log"
run_marker_install "$UNMATCHED_HOME" "$UNMATCHED_LOG_ONE"
unmatched_status_one=$MARKER_STATUS
run_marker_install "$UNMATCHED_HOME" "$UNMATCHED_LOG_TWO"
unmatched_status_two=$MARKER_STATUS

if [[ "$unmatched_status_one" -ne 0 && "$unmatched_status_two" -ne 0 ]] && \
    grep -qF "refusing to modify $UNMATCHED_RC" "$UNMATCHED_LOG_ONE" && \
    grep -qF 'found 1 begin marker(s) and 0 end marker(s)' "$UNMATCHED_LOG_ONE" && \
    grep -qF "refusing to modify $UNMATCHED_RC" "$UNMATCHED_LOG_TWO"; then
  pass_check "unmatched begin marker is refused on two consecutive installs"
else
  fail_check "unmatched begin marker was not refused with an exact diagnostic on both installs"
fi
if cmp -s "$UNMATCHED_ORIGINAL" "$UNMATCHED_RC"; then
  pass_check "two refused installs leave the unmatched-marker rc file unchanged"
else
  fail_check "a refused install truncated or otherwise changed the unmatched-marker rc file"
fi
unmatched_backup_count=0
unmatched_backups_match=true
for backup in "$UNMATCHED_RC".pre-strata.*; do
  [[ -f "$backup" ]] || continue
  unmatched_backup_count=$((unmatched_backup_count + 1))
  cmp -s "$UNMATCHED_ORIGINAL" "$backup" || unmatched_backups_match=false
done
if [[ "$unmatched_backup_count" -eq 2 ]] && $unmatched_backups_match; then
  pass_check "each refused unmatched-marker install creates a distinct exact backup"
else
  fail_check "refused unmatched-marker installs did not retain two exact backups"
fi

assert_malformed_markers_refused() {
  local case_id="$1" expected_report="$2" content="$3"
  local marker_home="$TEST_ROOT/marker-$case_id"
  local rc_file="$marker_home/.bashrc"
  local original="$TEST_ROOT/marker-$case_id.original"
  local log_path="$TEST_ROOT/marker-$case_id.log"
  local backup_found=false

  mkdir -p "$marker_home"
  printf '%s\n' "$content" >"$rc_file"
  cp -p "$rc_file" "$original"
  run_marker_install "$marker_home" "$log_path"
  for backup in "$rc_file".pre-strata.*; do
    [[ -f "$backup" ]] || continue
    if cmp -s "$original" "$backup"; then
      backup_found=true
      break
    fi
  done
  if [[ "$MARKER_STATUS" -ne 0 ]] && cmp -s "$original" "$rc_file" && \
      $backup_found && grep -qF "refusing to modify $rc_file" "$log_path" && \
      grep -qF "$expected_report" "$log_path"; then
    pass_check "$case_id marker state is backed up and refused unchanged"
  else
    fail_check "$case_id marker state was modified, guessed, or not backed up"
  fi
}

assert_malformed_markers_refused \
  "unmatched-end" \
  'found 0 begin marker(s) and 1 end marker(s)' \
  "$(printf '%s\n' 'user line before' "$END_MARK" 'user line after')"
assert_malformed_markers_refused \
  "duplicate-begin" \
  'found 2 begin marker(s) and 1 end marker(s)' \
  "$(printf '%s\n' "$BEGIN_MARK" 'user line one' "$BEGIN_MARK" "$END_MARK")"
assert_malformed_markers_refused \
  "out-of-order" \
  'found 1 begin marker(s) and 1 end marker(s); markers are out of order' \
  "$(printf '%s\n' "$END_MARK" 'user line between' "$BEGIN_MARK")"

run_install() {
  local label="$1" shell_path="$2" log_path="$3" status
  SHELL="$shell_path" "$INSTALL_ROOT/bin/strata-init" \
    --non-interactive "$INSTALL_ROOT" </dev/null >"$log_path" 2>&1
  status=$?
  if [[ "$status" -eq 0 ]]; then
    pass_check "$label install completed non-interactively"
  else
    fail_check "$label install exited $status; log follows"
    while IFS= read -r line || [[ -n "$line" ]]; do
      printf '%s\n' "$line" >&2
    done <"$log_path"
  fi
}

FIRST_LOG="$TEST_ROOT/install-fish.log"
run_install "fish" "/usr/bin/fish" "$FIRST_LOG"

if [[ -f "$INSTALL_ROOT/config/private-tokens.txt" ]]; then
  pass_check "fresh install seeded config/private-tokens.txt"
  if git diff --no-index --quiet \
      "$INSTALL_ROOT/config/private-tokens.example.txt" \
      "$INSTALL_ROOT/config/private-tokens.txt"; then
    pass_check "fresh denylist exactly matches the shipped example"
  else
    fail_check "fresh denylist does not match config/private-tokens.example.txt"
  fi
else
  fail_check "fresh install did not seed config/private-tokens.txt"
fi

SEEDED_DOCTOR_LOG="$TEST_ROOT/doctor-seeded-denylist.log"
STRATA_HOME="$INSTALL_ROOT" "$INSTALL_ROOT/bin/strata-doctor" \
  >"$SEEDED_DOCTOR_LOG" 2>&1
seeded_doctor_status=$?
if [[ "$seeded_doctor_status" -eq 0 ]] && \
    grep -qF 'INCOMPLETE config private denylist' "$SEEDED_DOCTOR_LOG" && \
    grep -qF 'add at least one active token' "$SEEDED_DOCTOR_LOG"; then
  pass_check "doctor reports the seeded comment-only denylist as incomplete with a remedy"
else
  fail_check "doctor reports the seeded comment-only denylist as ready or gives no remedy"
fi

FISH_CONFIG="$HOME/.config/fish/config.fish"
if [[ -f "$FISH_CONFIG" ]]; then
  pass_check "fish install created config.fish"
  if grep -qF 'set -gx STRATA_HOME' "$FISH_CONFIG" && \
      ! grep -qE '^[[:space:]]*export[[:space:]]' "$FISH_CONFIG"; then
    pass_check "fish block uses fish set syntax and contains no bash exports"
  else
    fail_check "fish config is not shell-correct: expected set -gx and no export statements"
  fi
  if command -v fish >/dev/null 2>&1; then
    if fish -c '
        set -e STRATA_HOME KB_DIR STATE_DIR SPECS_DIR
        source $argv[1]
        test "$STRATA_HOME" = $argv[2]
        and test "$KB_DIR" = "$STRATA_HOME/workspace"
        and test "$STATE_DIR" = "$KB_DIR/state"
        and test "$SPECS_DIR" = "$STATE_DIR/specs"
      ' "$FISH_CONFIG" "$INSTALL_ROOT"; then
      pass_check "fish sourced the generated config successfully"
    else
      fail_check "fish could not source the generated config or resolve its variables"
    fi
  else
    skip_check "fish executable is absent; static fish syntax assertions still ran"
  fi
else
  fail_check "fish install did not create $FISH_CONFIG"
  if ! command -v fish >/dev/null 2>&1; then
    skip_check "fish executable is absent; source check cannot run"
  fi
fi

CLAUDE_SETTINGS="$HOME/.claude/settings.json"
if [[ -f "$CLAUDE_SETTINGS" ]] && jq -e . "$CLAUDE_SETTINGS" >/dev/null; then
  pass_check "installed Claude settings are valid JSON"
  if jq -e '(.permissions | has("defaultMode")) | not' "$CLAUDE_SETTINGS" >/dev/null; then
    pass_check "clean install leaves permission defaultMode unset"
  else
    fail_check "clean install changed global permission defaultMode"
  fi
  if jq -e '
      .permissions.allow as $allow
      | ($allow | index("Bash")) == null
        and ($allow | index("Write")) == null
        and ($allow | index("Edit")) == null
        and ($allow | index("MultiEdit")) == null
        and ($allow | index("mcp__*")) == null
    ' "$CLAUDE_SETTINGS" >/dev/null; then
    pass_check "declined bypass does not blanket-preapprove shell, writes, edits, or MCP tools"
  else
    fail_check "declined bypass still blanket-preapproves shell, writes, edits, or MCP tools"
  fi
else
  fail_check "installed Claude settings are missing or invalid"
fi

if grep -qF 'bypassPermissions' "$FIRST_LOG" && \
    grep -qF -- '--enable-bypass-permissions' "$FIRST_LOG" && \
    grep -qF 'other shell commands, file changes, and MCP tools require approval' "$FIRST_LOG"; then
  pass_check "non-interactive output names the declined grants and explicit opt-in"
else
  fail_check "non-interactive output does not explain the declined grants and how to opt in"
fi

if [[ -f "$CLAUDE_SETTINGS" ]]; then
  mapfile -t HOOK_COMMANDS < <(jq -r '.. | objects | .command? // empty' "$CLAUDE_SETTINGS")
  if [[ "${#HOOK_COMMANDS[@]}" -gt 0 ]]; then
    pass_check "installed settings register hook commands"
  else
    fail_check "installed settings register no hook commands"
  fi
  for hook_command in "${HOOK_COMMANDS[@]}"; do
    if [[ "$hook_command" != "bash "* ]]; then
      fail_check "unsupported hook command shape: $hook_command"
      continue
    fi
    hook_path="${hook_command#bash }"
    if [[ -f "$hook_path" ]]; then
      pass_check "hook path resolves: ${hook_path#"$INSTALL_ROOT"/}"
    else
      fail_check "hook path does not resolve: $hook_path"
    fi
    case "$hook_path" in
      "$HOME"/*) ;;
      *) fail_check "installed hook path escapes the throwaway HOME: $hook_path" ;;
    esac
  done
else
  HOOK_COMMANDS=()
fi

# Give the rerun user edits that must survive in backups, plus a permission mode
# that must remain active unless bypass is explicitly requested.
if [[ -f "$CLAUDE_SETTINGS" ]]; then
  jq '.permissions.defaultMode = "plan" | .userEditSentinel = true' \
    "$CLAUDE_SETTINGS" >"$TEST_ROOT/settings-edited.json" && \
    mv "$TEST_ROOT/settings-edited.json" "$CLAUDE_SETTINGS"
fi
if [[ -f "$HOME/.claude/CLAUDE.md" ]]; then
  printf '\n# user-edit-sentinel\n' >>"$HOME/.claude/CLAUDE.md"
fi
if [[ -f "$INSTALL_ROOT/config/private-tokens.txt" ]]; then
  printf '\nlocal-only-sentinel\n' >>"$INSTALL_ROOT/config/private-tokens.txt"
fi

BASH_CONFIG="$HOME/.bashrc"
printf '%s\n' '# existing-user-bashrc-sentinel' >"$BASH_CONFIG"
SECOND_LOG="$TEST_ROOT/install-bash-rerun.log"
run_install "bash rerun" "/bin/bash" "$SECOND_LOG"

if [[ -f "$BASH_CONFIG" ]] && bash -n "$BASH_CONFIG"; then
  pass_check "bash install created syntactically valid .bashrc"
  if bash -c '
      unset STRATA_HOME KB_DIR STATE_DIR SPECS_DIR
      source "$1"
      [[ "$STRATA_HOME" == "$2" ]]
      [[ "$KB_DIR" == "$STRATA_HOME/workspace" ]]
      [[ "$STATE_DIR" == "$KB_DIR/state" ]]
      [[ "$SPECS_DIR" == "$STATE_DIR/specs" ]]
    ' _ "$BASH_CONFIG" "$INSTALL_ROOT"; then
    pass_check "bash sourced the generated config successfully"
  else
    fail_check "bash could not source the generated config or resolve its variables"
  fi
else
  fail_check "bash rerun did not create a syntactically valid .bashrc"
fi
if grep -qFx '# existing-user-bashrc-sentinel' "$BASH_CONFIG" && \
    grep -qFx "$BEGIN_MARK" "$BASH_CONFIG" && \
    grep -qFx "$END_MARK" "$BASH_CONFIG"; then
  pass_check "marker-free existing bash rc is preserved while one managed block is added"
else
  fail_check "marker-free existing bash rc was refused, overwritten, or received no managed block"
fi

if [[ -f "$INSTALL_ROOT/config/private-tokens.txt" ]] && \
    grep -qFx 'local-only-sentinel' "$INSTALL_ROOT/config/private-tokens.txt"; then
  pass_check "rerun preserved the existing private-token denylist"
else
  fail_check "rerun overwrote or removed the existing private-token denylist"
fi

ACTIVE_DOCTOR_LOG="$TEST_ROOT/doctor-active-denylist.log"
STRATA_HOME="$INSTALL_ROOT" "$INSTALL_ROOT/bin/strata-doctor" \
  >"$ACTIVE_DOCTOR_LOG" 2>&1
active_doctor_status=$?
if [[ "$active_doctor_status" -eq 0 ]] && \
    grep -qF 'OK config private denylist' "$ACTIVE_DOCTOR_LOG" && \
    grep -qF 'contains at least one active token' "$ACTIVE_DOCTOR_LOG"; then
  pass_check "doctor reports a denylist with an active token as ready"
else
  fail_check "doctor did not recognize an active private denylist token"
fi

if [[ -f "$CLAUDE_SETTINGS" ]] && \
    jq -e '.permissions.defaultMode == "plan" and (.userEditSentinel? == null)' \
      "$CLAUDE_SETTINGS" >/dev/null; then
  pass_check "rerun refreshed settings while preserving the user's permission mode"
else
  fail_check "rerun did not refresh settings and preserve the user's permission mode"
fi

settings_backup_found=false
for backup in "$CLAUDE_SETTINGS".pre-strata.*; do
  [[ -f "$backup" ]] || continue
  if jq -e '.userEditSentinel == true' "$backup" >/dev/null 2>&1; then
    settings_backup_found=true
    break
  fi
done
if $settings_backup_found; then
  pass_check "rerun backed up user-edited settings before refresh"
else
  fail_check "rerun did not back up user-edited settings before refresh"
fi

claude_backup_found=false
for backup in "$HOME/.claude/CLAUDE.md".pre-strata.*; do
  [[ -f "$backup" ]] || continue
  if grep -qFx '# user-edit-sentinel' "$backup"; then
    claude_backup_found=true
    break
  fi
done
if [[ -f "$HOME/.claude/CLAUDE.md" ]] && \
    ! grep -qFx '# user-edit-sentinel' "$HOME/.claude/CLAUDE.md" && \
    $claude_backup_found; then
  pass_check "rerun refreshed CLAUDE.md and preserved the user edit in a backup"
else
  fail_check "rerun did not refresh CLAUDE.md with a recoverable user-edit backup"
fi

if grep -qF 'refreshed' "$SECOND_LOG" && grep -qF 'backed up' "$SECOND_LOG"; then
  pass_check "rerun output reports refreshed copies and backup locations"
else
  fail_check "rerun output does not report exactly that copies were refreshed and backed up"
fi

THIRD_LOG="$TEST_ROOT/install-bypass-opt-in.log"
SHELL="/bin/bash" "$INSTALL_ROOT/bin/strata-init" \
  --non-interactive --enable-bypass-permissions "$INSTALL_ROOT" \
  </dev/null >"$THIRD_LOG" 2>&1
third_status=$?
if [[ "$third_status" -eq 0 ]] && \
    jq -e '.permissions.defaultMode == "bypassPermissions"' \
      "$CLAUDE_SETTINGS" >/dev/null; then
  pass_check "explicit bypass opt-in sets bypassPermissions"
else
  fail_check "explicit bypass opt-in exited $third_status or did not set bypassPermissions"
fi
if grep -qF 'permission prompts are disabled globally' "$THIRD_LOG"; then
  pass_check "explicit bypass opt-in output names its global consequence"
else
  fail_check "explicit bypass opt-in output does not name its global consequence"
fi
# Two changed settings installs occurred, so two distinct backups must remain.
settings_backup_count=0
plan_backup_found=false
for backup in "$CLAUDE_SETTINGS".pre-strata.*; do
  [[ -f "$backup" ]] || continue
  settings_backup_count=$((settings_backup_count + 1))
  if jq -e '.permissions.defaultMode == "plan"' "$backup" >/dev/null 2>&1; then
    plan_backup_found=true
  fi
done
if [[ "$settings_backup_count" -ge 2 ]] && $plan_backup_found; then
  pass_check "separate settings refreshes retained distinct recoverable backups"
else
  fail_check "settings backup names collided or the pre-opt-in permission mode was not preserved"
fi

git -C "$PROJECT_DIR" init -q
# Hook state keys use the documented eight-character session prefix.
printf -v SID_PREFIX '%08x' "$$"
SESSION_ID="$SID_PREFIX-fresh-install"
VALID_TOOL_INPUT="$(jq -cn \
  --arg sid "$SESSION_ID" \
  --arg cwd "$PROJECT_DIR" \
  '{session_id:$sid,hook_event_name:"PreToolUse",source:"startup",cwd:$cwd,tool_name:"Bash",tool_input:{command:"printf harmless"}}')"
VALID_SESSION_INPUT="$(jq -cn \
  --arg sid "$SESSION_ID" \
  --arg cwd "$PROJECT_DIR" \
  '{session_id:$sid,hook_event_name:"SessionStart",source:"startup",cwd:$cwd}')"

if command -v strace >/dev/null 2>&1; then
  TRACE_HOOK_WRITES=true
else
  TRACE_HOOK_WRITES=false
  skip_check "strace is absent; syscall-level write-boundary tracing cannot run, so source-tree and unique system-temp boundary checks remain active"
fi

check_trace_writes() {
  local trace_path="$1" hook_name="$2"
  python3 - "$trace_path" "$HOME" "$hook_name" <<'PY'
from pathlib import Path
import re
import sys

trace_path = Path(sys.argv[1])
home = Path(sys.argv[2]).resolve()
mutating = re.compile(
    r"(?:open|openat|creat).*?(?:O_WRONLY|O_RDWR|O_CREAT|O_TRUNC|O_APPEND)"
    r"|(?:rename|renameat|unlink|unlinkat|mkdir|mkdirat|rmdir|symlink|link|truncate|chmod)\("
)
quoted_absolute = re.compile(r'"(/[^"]*)"')
violations = []
for line in trace_path.read_text(errors="replace").splitlines():
    if not mutating.search(line):
        continue
    for raw_path in quoted_absolute.findall(line):
        if raw_path == "/dev/null":
            continue
        path = Path(raw_path)
        try:
            path.resolve().relative_to(home)
        except (ValueError, OSError):
            violations.append(raw_path)
if violations:
    print(f"{sys.argv[3]} wrote outside throwaway HOME: {sorted(set(violations))}", file=sys.stderr)
    raise SystemExit(1)
PY
}

run_hook_case() {
  local event="$1" hook_command="$2" case_name="$3" input="$4"
  local hook_path hook_name output_path error_path trace_path status
  hook_path="${hook_command#bash }"
  hook_name="$(basename "$hook_path")"
  output_path="$RUN_DIR/${event}-${hook_name}-${case_name}.out"
  error_path="$RUN_DIR/${event}-${hook_name}-${case_name}.err"
  trace_path="$RUN_DIR/${event}-${hook_name}-${case_name}.trace"

  if $TRACE_HOOK_WRITES; then
    (
      cd "$PROJECT_DIR" || exit
      printf '%s' "$input" | strace -f -qq -e trace=%file -o "$trace_path" \
        env HOME="$HOME" STRATA_HOME="$INSTALL_ROOT" KB_DIR="$KB_DIR" \
          STATE_DIR="$STATE_DIR" RUN_DIR="$RUN_DIR" SPECS_DIR="$SPECS_DIR" \
          CLAUDE_SESSION_ID="$SESSION_ID" CLAUDE_PROJECT_DIR="$PROJECT_DIR" \
          CLAUDE_ENV_FILE="$STATE_DIR/claude-env" bash "$hook_path"
    ) >"$output_path" 2>"$error_path"
    status=$?
  else
    (
      cd "$PROJECT_DIR" || exit
      printf '%s' "$input" | env HOME="$HOME" STRATA_HOME="$INSTALL_ROOT" \
        KB_DIR="$KB_DIR" STATE_DIR="$STATE_DIR" RUN_DIR="$RUN_DIR" \
        SPECS_DIR="$SPECS_DIR" CLAUDE_SESSION_ID="$SESSION_ID" \
        CLAUDE_PROJECT_DIR="$PROJECT_DIR" CLAUDE_ENV_FILE="$STATE_DIR/claude-env" \
        bash "$hook_path"
    ) >"$output_path" 2>"$error_path"
    status=$?
  fi

  if [[ "$status" -eq 0 ]]; then
    pass_check "$event $hook_name accepts $case_name input"
  else
    fail_check "$event $hook_name exits $status on $case_name input"
  fi
  if grep -qi 'traceback' "$output_path" "$error_path"; then
    fail_check "$event $hook_name prints a traceback on $case_name input"
  else
    pass_check "$event $hook_name prints no traceback on $case_name input"
  fi
  if $TRACE_HOOK_WRITES; then
    if check_trace_writes "$trace_path" "$hook_name"; then
      pass_check "$event $hook_name keeps traced writes inside throwaway HOME"
    else
      fail_check "$event $hook_name attempted a traced write outside throwaway HOME"
    fi
  fi
}

if [[ -f "$CLAUDE_SETTINGS" ]]; then
  for event in SessionStart PreToolUse; do
    mapfile -t EVENT_COMMANDS < <(jq -r --arg event "$event" \
      '.hooks[$event][]?.hooks[]?.command // empty' "$CLAUDE_SETTINGS")
    if [[ "$event" == "SessionStart" ]]; then
      event_input="$VALID_SESSION_INPUT"
    else
      event_input="$VALID_TOOL_INPUT"
    fi
    for hook_command in "${EVENT_COMMANDS[@]}"; do
      run_hook_case "$event" "$hook_command" valid "$event_input"
      run_hook_case "$event" "$hook_command" empty ""
    done
  done
fi

SOURCE_STATUS_AFTER="$(git -C "$SOURCE_ROOT" status --porcelain=v1 --untracked-files=all)"
if [[ "$SOURCE_STATUS_AFTER" == "$SOURCE_STATUS_BEFORE" ]]; then
  pass_check "install and hook execution did not write to the source checkout"
else
  fail_check "install or hook execution changed the source checkout"
  # Print only what moved. The full status reads as "the tree is dirty", which sends
  # the reader after their own uncommitted work instead of the entries that appeared.
  diff <(printf '%s\n' "$SOURCE_STATUS_BEFORE") <(printf '%s\n' "$SOURCE_STATUS_AFTER") >&2 || true
fi

mapfile -t SYSTEM_TMP_WRITES < <(
  # The hooks' system-temp state files are direct children of /tmp.
  find /tmp -maxdepth 1 -mindepth 1 -name "*${SID_PREFIX}*" \
    ! -path "$TEST_ROOT" -print 2>/dev/null
)
if [[ "${#SYSTEM_TMP_WRITES[@]}" -eq 0 ]]; then
  pass_check "hooks created no session-keyed files in system temp outside throwaway HOME"
else
  fail_check "hooks wrote session-keyed paths outside throwaway HOME: ${SYSTEM_TMP_WRITES[*]}"
fi

printf 'SUMMARY: %s passed, %s failed, %s skipped (measured checks)\n' \
  "$PASSED" "$FAILED" "$SKIPPED"
if [[ "$FAILED" -ne 0 ]]; then
  exit 1
fi
