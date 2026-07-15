#!/usr/bin/env bash
# gate-nested-clone.sh - PreToolUse(Bash) deny gate
# Denies `git clone` that would create a clone inside an existing git repo.
# The clone-inside-clone footgun: running `git clone <url>` while already inside
# a working tree silently nests the new repo as a subdirectory, almost never intended.
# Config: matcher "Bash" + if "Bash(git clone*)". Input: stdin JSON. Deny: exit 2 + stderr.
set -uo pipefail

# Fail OPEN on infra problems: without jq we cannot parse the input, so warn and allow.
if ! command -v jq >/dev/null 2>&1; then
    echo "[nested-clone] jq not found; skipping nested-clone check." >&2
    exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "[nested-clone] python3 not found; skipping nested-clone check." >&2
    exit 0
fi

INPUT="$(cat)"
COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"

# Only act on git clone; any other command is allowed.
echo "$COMMAND" | grep -qE 'git[[:space:]]+clone' || exit 0

# Are we inside a git repo? If yes, resolve the clone target against its toplevel.
# Fail OPEN when git is unavailable or we are not inside a repo (nothing to nest into).
PARENT_REPO=$(git rev-parse --show-toplevel 2>/dev/null) || exit 0

# Parse clone operands without mistaking option values for the source or target.
CLONE_STATUS="$(
    NESTED_CLONE_COMMAND="$COMMAND" NESTED_CLONE_PARENT_REPO="$PARENT_REPO" python3 - <<'PY'
import os
import shlex

OPTIONS_WITH_VALUES = {
    "-b", "--branch", "-c", "--config", "--depth", "--filter", "-j", "--jobs",
    "-o", "--origin", "--reference", "--reference-if-able", "--ref-format",
    "--revision", "--separate-git-dir", "--server-option", "--shallow-exclude",
    "--shallow-since", "--template", "-u", "--upload-pack", "--bundle-uri",
}
SHORT_OPTIONS_WITH_VALUES = {"-b", "-c", "-j", "-o", "-u"}
CONTROL_OPERATORS = {";", "&&", "||", "|", "|&", "&", "\n"}

try:
    argv = shlex.split(os.environ["NESTED_CLONE_COMMAND"], posix=True)
except (KeyError, ValueError):
    print("parse_error")
    raise SystemExit

clone_index = next(
    (
        index
        for index in range(len(argv) - 1)
        if os.path.basename(argv[index]) == "git" and argv[index + 1] == "clone"
    ),
    None,
)
if clone_index is None:
    print("outside")
    raise SystemExit

operands = []
options = True
index = clone_index + 2
while index < len(argv):
    arg = argv[index]
    if arg in CONTROL_OPERATORS:
        break
    if options and arg == "--":
        options = False
        index += 1
        continue
    if options and arg in OPTIONS_WITH_VALUES:
        index += 2
        continue
    if options and arg.startswith("--") and "=" in arg:
        index += 1
        continue
    if options and any(arg.startswith(option) and arg != option for option in SHORT_OPTIONS_WITH_VALUES):
        index += 1
        continue
    if options and arg.startswith("-") and arg != "-":
        index += 1
        continue
    operands.append(arg)
    index += 1

if not operands:
    print("outside")
    raise SystemExit

# With no explicit target, git derives one beneath the current directory.
destination = operands[-1] if len(operands) > 1 else "."
destination = os.path.realpath(os.path.expanduser(destination))
parent_repo = os.path.realpath(os.environ["NESTED_CLONE_PARENT_REPO"])
try:
    inside = os.path.commonpath((parent_repo, destination)) == parent_repo
except ValueError:
    inside = False
print("inside" if inside else "outside")
PY
)"

case "$CLONE_STATUS" in
    outside)
        exit 0
        ;;
    inside)
        ;;
    *)
        echo "[nested-clone] command parse failed; skipping nested-clone check." >&2
        exit 0
        ;;
esac

# Inside a repo + target resolving beneath it = nested clone-inside-clone. Deny.
echo "git clone inside existing repo at ${PARENT_REPO}. This creates a nested clone-inside-clone, which is almost never intended. Pass an absolute-path target, or cd to a parent directory first (e.g. 'cd ~ && git clone ...')." >&2
exit 2
