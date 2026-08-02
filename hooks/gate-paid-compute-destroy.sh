#!/usr/bin/env bash
# gate-paid-compute-destroy.sh - PreToolUse(Bash) deny gate
# Blocks paid-compute teardown commands until results are confirmed synced.
# Speed-bump pattern: a teardown verb is denied with a sync reminder so the
# operator pulls every artifact locally, verifies it, then re-runs the command.
# The pause is the point.
#
# Config: settings.json matcher "Bash" with NO "if" filter — the script is the
# single source of truth for which commands are teardowns, so it must see every
# Bash command (this is what lets EXTRA_TEARDOWN_PATTERNS additions actually
# fire). Input: the tool call JSON on stdin. Deny: human-readable reason to
# stderr + exit 2 (the PreToolUse deny signal). Infra failure (missing jq) WARNS
# to stderr and allows (exit 0); an infra problem never hard-blocks a command.

set -uo pipefail

# Teardown patterns mirror the token policy below for ambiguous-parse fallback.
# Built-ins cover the common paid-compute CLIs. Add any other provider CLI by
# extending EXTRA_TEARDOWN_PATTERNS; custom regexes retain conservative raw matching:
#   EXTRA_TEARDOWN_PATTERNS+=('gpupod[[:space:]]+(stop|remove|delete)')
#   EXTRA_TEARDOWN_PATTERNS+=('mycloud[[:space:]]+(destroy|stop)')
TEARDOWN_PATTERNS=(
  'aws[[:space:]]+ec2[[:space:]]+(stop|terminate)-instances'
  'gcloud[[:space:]]+compute[[:space:]]+instances[[:space:]]+(stop|delete)'
  'runpodctl[[:space:]]+(stop|remove)[[:space:]]+pod'
  'vastai[[:space:]]+(destroy|stop)[[:space:]]+instance'
)
EXTRA_TEARDOWN_PATTERNS=()
if [ "${#EXTRA_TEARDOWN_PATTERNS[@]}" -gt 0 ]; then
  TEARDOWN_PATTERNS+=("${EXTRA_TEARDOWN_PATTERNS[@]}")
fi
TEARDOWN_PATTERN=""
for pat in "${TEARDOWN_PATTERNS[@]}"; do
  TEARDOWN_PATTERN="${TEARDOWN_PATTERN:+${TEARDOWN_PATTERN}|}${pat}"
done

deny() {
  local cmd="$1"
  {
    echo "BLOCKED: paid-compute teardown command detected."
    echo ""
    echo "Command: $cmd"
    echo ""
    echo "Confirm every result, log, and artifact is pulled to local storage first."
    echo "Pull the data, verify it locally, then re-run the teardown command."
  } >&2
  exit 2
}

# Fail open on infra problems: without jq the command cannot be parsed, so warn
# and allow rather than block on a tooling gap.
if ! command -v jq >/dev/null 2>&1; then
  echo "[paid-compute-destroy] jq not found; teardown gate skipped (fail-open)." >&2
  exit 0
fi

INPUT="$(</dev/stdin)"
case "$INPUT" in
  *aws*|*gcloud*|*runpodctl*|*vastai*|*eval*|*sh\ -c*|*sh\ -lc*|*\\*|*\'*|*'`'*|*'$'*) ;;
  *) exit 0 ;;
esac
COMMAND="$(jq -r '.tool_input.command // empty' <<<"$INPUT" 2>/dev/null || true)"
[ -n "$COMMAND" ] || exit 0

case "$COMMAND" in
  *aws*|*gcloud*|*runpodctl*|*vastai*|*eval*|*sh\ -c*|*sh\ -lc*|*\\*|*\'*|*\"*) ;;
  *) exit 0 ;;
esac

# Keep the common irrelevant path Bash-only. Quoting, escaping, and shell
# interpreters reach the tokenizer because they can hide or build a command.
# shellcheck disable=SC2016  # Literal shell syntax is matched, not expanded here.
plausibly_mentions_paid_compute() {
  local command="$1"
  local tool_re data_command_re control_re interpreter_re

  tool_re='(^|[;&|()`[:space:]])([^[:space:];&|()`]+/)?(aws|gcloud|runpodctl|vastai)([[:space:];&|()`]|$)'
  data_command_re='^[[:space:]]*([^[:space:];&|()`]+/)?(echo|printf|grep|cat|ls)([[:space:]]|$)'
  control_re='[;&|()`]'
  interpreter_re='(^|[;&|()`[:space:]])(eval|([^/[:space:]]+/)?(ba|z|da|k)?sh)([[:space:]]|$)'

  if [[ $command =~ $data_command_re && ! $command =~ $control_re &&
        $command != *$'\n'* && $command != *'$('* ]]; then
    return 1
  fi
  [[ $command =~ $tool_re || $command =~ $interpreter_re ||
     $command == *\\* || $command == *\'* || $command == *\"* ]]
}

# Preserve the documented extension point. Its regex fragments do not carry
# enough structure to infer arbitrary executable names, so additions stay on
# the old conservative path while built-in providers use command-position parsing.
if [ "${#EXTRA_TEARDOWN_PATTERNS[@]}" -gt 0 ]; then
  EXTRA_TEARDOWN_PATTERN=""
  for pat in "${EXTRA_TEARDOWN_PATTERNS[@]}"; do
    EXTRA_TEARDOWN_PATTERN="${EXTRA_TEARDOWN_PATTERN:+${EXTRA_TEARDOWN_PATTERN}|}${pat}"
  done
  if printf '%s' "$COMMAND" | grep -qE "$EXTRA_TEARDOWN_PATTERN"; then
    deny "$COMMAND"
  fi
fi

plausibly_mentions_paid_compute "$COMMAND" || exit 0

if ! command -v python3 >/dev/null 2>&1; then
  echo "[paid-compute-destroy] python3 not found; teardown gate skipped (fail-open)." >&2
  exit 0
fi

TEARDOWN_STATUS="$(PAID_COMPUTE_COMMAND="$COMMAND" python3 - <<'PY'
import os
import re
import shlex

MAX_SCAN_DEPTH = 3  # Matches the rm guard's existing bounded wrapper recursion.
CONTROL_OPERATORS = {"\n", ";", ";;", ";&", ";;&", "&&", "||", "|", "|&", "&", "(", ")"}
REDIRECT_OPERATORS = {
    "<", ">", "<<", ">>", "<>", "<<-", "<<<", ">|", "<&", ">&", "&>", "&>>",
}
WRAPPERS = {
    "sudo", "doas", "command", "builtin", "exec", "env", "nice", "ionice",
    "nohup", "stdbuf", "time", "timeout", "setsid", "xargs", "chronic",
}
WRAPPER_OPTIONS_WITH_VALUE = {
    "sudo": {
        "-u", "--user", "-g", "--group", "-h", "--host", "-p", "--prompt",
        "-C", "--close-from", "-T", "--command-timeout", "-R", "--chroot",
        "-D", "--chdir",
    },
    "doas": {"-C", "-u"},
    "exec": {"-a"},
    "env": {"-u", "--unset", "-C", "--chdir", "-S", "--split-string", "--argv0"},
    "nice": {"-n", "--adjustment"},
    "ionice": {
        "-c", "--class", "-n", "--classdata", "-p", "--pid", "-P", "--pgid",
        "-u", "--uid",
    },
    "stdbuf": {"-i", "--input", "-o", "--output", "-e", "--error"},
    "time": {"-f", "--format", "-o", "--output"},
    "timeout": {"-k", "--kill-after", "-s", "--signal"},
    "xargs": {
        "-a", "--arg-file", "-d", "--delimiter", "-E", "--eof", "-I", "--replace",
        "-L", "--max-lines", "-n", "--max-args", "-P", "--max-procs", "-s",
        "--max-chars", "--process-slot-var",
    },
}
NO_EXEC_WRAPPER_OPTIONS = {"--help", "--version"}
COMMAND_INSPECTION_OPTIONS = {"-v", "-V"}
PLAIN_NON_EXECUTING = {"echo", "printf", "grep", "cat", "ls"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
KEYWORDS = {"do", "then", "else", "elif", "if", "while", "until", "!"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
DURATION = re.compile(r"^\d+(?:\.\d+)?[smhd]?$")
TOOLS = {"aws", "gcloud", "runpodctl", "vastai"}
TOOL_WORD = re.compile(r"(?:^|[^A-Za-z0-9_/-])(?:aws|gcloud|runpodctl|vastai)(?:[^A-Za-z0-9_-]|$)")


def command_basename(token):
    return token.rsplit("/", 1)[-1]


def shell_tokens(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
    lexer.whitespace_split = True
    lexer.whitespace = " \t\r"
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
    index = 0
    while index < len(words):
        token = words[index]
        if token.isdigit() and index + 1 < len(words) and words[index + 1] in REDIRECT_OPERATORS:
            index += 3
        elif token in REDIRECT_OPERATORS:
            index += 2
        else:
            argv.append(token)
            index += 1
    return argv


def read_backtick_command(command, start):
    index = start
    while index < len(command):
        if command[index] == "\\":
            index += 2
        elif command[index] == "`":
            return command[start:index], index
        else:
            index += 1
    return None, None


def read_dollar_command(command, start):
    depth = 1
    quote = None
    index = start
    while index < len(command):
        char = command[index]
        if char == "\\" and quote != "'":
            index += 2
            continue
        if quote == "'":
            quote = None if char == "'" else quote
            index += 1
            continue
        if quote == '"':
            if char == '"':
                quote = None
            elif char == "$" and index + 1 < len(command) and command[index + 1] == "(":
                depth += 1
                index += 2
                continue
            index += 1
            continue
        if char in {"'", '"'}:
            quote = char
        elif char == "$" and index + 1 < len(command) and command[index + 1] == "(":
            depth += 1
            index += 2
            continue
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return command[start:index], index
        index += 1
    return None, None


def nested_commands(command):
    nested = []
    malformed = False
    quote = None
    index = 0
    while index < len(command):
        char = command[index]
        if char == "\\" and quote != "'":
            index += 2
            continue
        if quote == "'":
            quote = None if char == "'" else quote
            index += 1
            continue
        if char == "'" and quote is None:
            quote = "'"
        elif char == '"':
            quote = None if quote == '"' else '"'
        elif char == "$" and index + 1 < len(command) and command[index + 1] == "(":
            inner, end = read_dollar_command(command, index + 2)
            if inner is None:
                malformed = True
                break
            nested.append(inner)
            index = end
        elif char == "`":
            inner, end = read_backtick_command(command, index + 1)
            if inner is None:
                malformed = True
                break
            nested.append(inner)
            index = end
        index += 1
    return nested, malformed


def candidates_from_argv(argv, depth):
    if depth > MAX_SCAN_DEPTH:
        return [], True
    candidates = []
    ambiguous = False
    index = 0
    while index < len(argv) and (argv[index] in KEYWORDS or ASSIGNMENT.match(argv[index])):
        index += 1

    while index < len(argv) and command_basename(argv[index]) in WRAPPERS:
        wrapper = command_basename(argv[index])
        index += 1
        while index < len(argv):
            token = argv[index]
            if token == "--":
                index += 1
                break
            if token in NO_EXEC_WRAPPER_OPTIONS or (
                wrapper == "command" and token in COMMAND_INSPECTION_OPTIONS
            ):
                return candidates, ambiguous
            if wrapper == "env" and token in {"-S", "--split-string"}:
                if index + 1 >= len(argv):
                    return candidates, True
                try:
                    split_argv = shlex.split(argv[index + 1], posix=True)
                except ValueError:
                    return candidates, True
                return candidates_from_argv(split_argv + argv[index + 2 :], depth + 1)
            if wrapper == "env" and token.startswith("--split-string="):
                try:
                    split_argv = shlex.split(token.split("=", 1)[1], posix=True)
                except ValueError:
                    return candidates, True
                return candidates_from_argv(split_argv + argv[index + 1 :], depth + 1)
            if wrapper == "env" and token.startswith("-S") and token != "-S":
                try:
                    split_argv = shlex.split(token[2:], posix=True)
                except ValueError:
                    return candidates, True
                return candidates_from_argv(split_argv + argv[index + 1 :], depth + 1)
            if not token.startswith("-") or token == "-":
                break
            if token in WRAPPER_OPTIONS_WITH_VALUE.get(wrapper, set()):
                if index + 1 >= len(argv):
                    return candidates, True
                index += 2
            else:
                index += 1

        if wrapper == "timeout":
            if index < len(argv) and DURATION.match(argv[index]):
                index += 1
            else:
                ambiguous = True
        if wrapper == "env":
            while index < len(argv) and ASSIGNMENT.match(argv[index]):
                index += 1

    if index >= len(argv):
        return candidates, ambiguous
    head = command_basename(argv[index])
    if head in TOOLS:
        return [argv[index:]], ambiguous
    if head in PLAIN_NON_EXECUTING:
        return candidates, ambiguous
    if head in SHELLS:
        for option_index in range(index + 1, len(argv)):
            option = argv[option_index]
            if option == "-c" or (
                option.startswith("-") and not option.startswith("--") and "c" in option[1:]
            ):
                if option_index + 1 >= len(argv):
                    return candidates, True
                return command_candidates(argv[option_index + 1], depth + 1)
            if not option.startswith("-") or option == "-":
                break
        return candidates, ambiguous
    if head == "eval":
        if index + 1 < len(argv):
            return command_candidates(" ".join(argv[index + 1 :]), depth + 1)
        return candidates, ambiguous

    later_tools = [
        candidate_index
        for candidate_index in range(index + 1, len(argv))
        if command_basename(argv[candidate_index]) in TOOLS
    ]
    if later_tools:
        candidates.extend(argv[candidate_index:] for candidate_index in later_tools)
        ambiguous = True
    elif TOOL_WORD.search(" ".join(argv[index + 1 :])):
        ambiguous = True
    return candidates, ambiguous


def command_candidates(command, depth=0):
    if depth > MAX_SCAN_DEPTH:
        return [], True
    candidates = []
    nested, malformed = nested_commands(command)
    ambiguous = malformed
    for inner in nested:
        inner_candidates, inner_ambiguous = command_candidates(inner, depth + 1)
        candidates.extend(inner_candidates)
        ambiguous = ambiguous or inner_ambiguous
    try:
        tokens = shell_tokens(command)
    except ValueError:
        return candidates, True
    for words in simple_commands(tokens):
        word_candidates, word_ambiguous = candidates_from_argv(argv_words(words), depth)
        candidates.extend(word_candidates)
        ambiguous = ambiguous or word_ambiguous
    return candidates, ambiguous


def is_teardown(argv):
    tool = command_basename(argv[0])
    args = argv[1:]
    if tool == "aws":
        return len(args) >= 2 and args[0] == "ec2" and args[1] in {"stop-instances", "terminate-instances"}
    if tool == "gcloud":
        return len(args) >= 3 and args[:2] == ["compute", "instances"] and args[2] in {"stop", "delete"}
    if tool == "runpodctl":
        return len(args) >= 2 and args[0] in {"stop", "remove"} and args[1] == "pod"
    if tool == "vastai":
        return len(args) >= 2 and args[0] in {"destroy", "stop"} and args[1] == "instance"
    return False


candidates, ambiguous = command_candidates(os.environ.get("PAID_COMPUTE_COMMAND", ""))
if any(is_teardown(candidate) for candidate in candidates):
    print("blocked")
elif ambiguous:
    print("ambiguous")
else:
    print("none")
PY
)"

case "$TEARDOWN_STATUS" in
  blocked)
    deny "$COMMAND"
    ;;
  ambiguous)
    if printf '%s' "$COMMAND" | grep -qE "$TEARDOWN_PATTERN"; then
      deny "$COMMAND"
    fi
    ;;
  none)
    ;;
  *)
    echo "[paid-compute-destroy] command parser returned an invalid status; teardown gate skipped (fail-open)." >&2
    ;;
esac

exit 0
