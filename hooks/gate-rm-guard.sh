#!/usr/bin/env bash
# gate-rm-guard.sh - PreToolUse(Bash) blocking hook
# Blocks rm on project/home files. Redirects to the ~/to-delete/ workflow.
# Allows rm on safe targets: /tmp/, *.pyc, __pycache__, node_modules, build/dist artifacts.
# Config: matcher "Bash" + if "Bash(rm *)". Input: hook JSON on stdin. Deny: exit 2 + stderr.
set -uo pipefail

INPUT="$(cat)"

# Fail open on infra problems: without jq we cannot parse, so allow rather than hard-block.
if ! command -v jq >/dev/null 2>&1; then
    echo "gate-rm-guard: jq unavailable, allowing command" >&2
    exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "gate-rm-guard: python3 unavailable, allowing command" >&2
    exit 0
fi

COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)"

# Tokenize before policy checks so one safe artifact operand cannot mask an
# unsafe project/home operand in the same rm invocation.
POLICY_STATUS="$(
    RM_GUARD_COMMAND="$COMMAND" python3 - <<'PY'
import os
import re
import shlex

CONTROL_OPERATORS = {";", ";;", ";&", ";;&", "&&", "||", "|", "|&", "&", "(", ")"}
REDIRECT_OPERATORS = {
    "<",
    ">",
    "<<",
    ">>",
    "<>",
    "<<-",
    "<<<",
    ">|",
    "<&",
    ">&",
    "&>",
    "&>>",
}
SAFE_DIRS = {"__pycache__", "node_modules", ".cache", "build", "dist", "target"}
SAFE_SUFFIXES = (".pyc", ".o", ".class")


def shell_tokens(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    return list(lexer)


def simple_commands(tokens):
    current = []
    for token in tokens:
        if token in CONTROL_OPERATORS:
            if current:
                yield current
                current = []
            continue
        current.append(token)
    if current:
        yield current


def argv_words(words):
    argv = []
    i = 0
    while i < len(words):
        token = words[i]
        if token.isdigit() and i + 1 < len(words) and words[i + 1] in REDIRECT_OPERATORS:
            i += 3
            continue
        if token in REDIRECT_OPERATORS:
            i += 2
            continue
        argv.append(token)
        i += 1
    return argv


def is_assignment(word):
    return re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word) is not None


def command_name_index(argv):
    index = 0
    while index < len(argv) and is_assignment(argv[index]):
        index += 1
    if index >= len(argv):
        return None
    return index


def is_rm_word(word):
    return os.path.basename(word) == "rm"


def rm_targets(args):
    targets = []
    options_done = False
    for arg in args:
        if not options_done and arg == "--":
            options_done = True
            continue
        if not options_done and arg.startswith("-") and arg != "-":
            continue
        options_done = True
        targets.append(arg)
    return targets


def safe_target(target):
    normalized = target.rstrip("/")
    parts = [part for part in normalized.split("/") if part]
    if ".." in parts:
        return False
    return (
        target == "/dev/null"
        or target.startswith("/tmp/")
        or os.path.basename(normalized).endswith(SAFE_SUFFIXES)
        or any(part in SAFE_DIRS for part in parts)
    )


try:
    tokens = shell_tokens(os.environ.get("RM_GUARD_COMMAND", ""))
except ValueError:
    print("parse_error")
    raise SystemExit

found = False
for command_words in simple_commands(tokens):
    argv = argv_words(command_words)
    index = command_name_index(argv)
    if index is None or not is_rm_word(argv[index]):
        continue
    found = True
    if any(not safe_target(target) for target in rm_targets(argv[index + 1 :])):
        print("blocked")
        raise SystemExit

print("allowed" if found else "none")
PY
)"

case "$POLICY_STATUS" in
    none|allowed)
        exit 0
        ;;
    blocked)
        ;;
    parse_error)
        echo "gate-rm-guard: command parse failed, allowing command" >&2
        exit 0
        ;;
    *)
        echo "gate-rm-guard: parser failed, allowing command" >&2
        exit 0
        ;;
esac

cat >&2 <<'EOF'
Direct deletion blocked. Use the to-delete workflow instead:
  mv <file> ~/to-delete/<name>
  echo '<name> | <original-path> | <YYYY-MM-DD> | <reason>' >> ~/to-delete/manifest.txt
If the file is a true temp/artifact (/tmp, __pycache__, node_modules, build/dist), rm is fine.
EOF
exit 2
