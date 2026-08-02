#!/usr/bin/env bash
# gate-codex-exec.sh - PreToolUse(Bash) deny gate
# Denies bare `codex exec` calls and redirects to the lane wrappers (fast / strong)
# or the /codex-review skill, which encode the canonical flag set and handle quota
# fallback. See reference/codex-invocation.md and reference/model-delegation.md.
#
# Config: matcher "Bash"; this script performs its own relevance check. Input: stdin JSON.
# Deny: exit 2 + a human-readable reason on stderr (the PreToolUse deny signal).
# Fails OPEN (exit 0) on infrastructure errors unless the raw command still
# plausibly invokes the guarded tool and flags cannot be verified.
#
# Allows: `codex exec` invocations that carry the full sandbox flag set
# (--dangerously-bypass-approvals-and-sandbox + --skip-git-repo-check), the canonical
# form used by the /codex-review skill per reference/codex-invocation.md.
set -uo pipefail

INPUT="$(</dev/stdin)"
case "$INPUT" in
    *codex*|*eval*|*sh\ -c*|*sh\ -lc*|*\\*|*\'*|*'`'*|*'$'*) ;;
    *) exit 0 ;;
esac

# Only relevant calls need the JSON parser. Keep ordinary Bash commands on the
# raw-input fast path while preserving the fail-open warning for guarded calls.
if ! command -v jq >/dev/null 2>&1; then
    echo "[gate-codex-exec] jq not found; allowing command unchecked." >&2
    exit 0
fi

COMMAND="$(jq -r '.tool_input.command // empty' <<<"$INPUT" 2>/dev/null || true)"

# A literal-free command cannot reach this gate's policy. This lightweight glob
# keeps the common path within the measured pre-change latency budget.
case "$COMMAND" in
    *codex*|*eval*|*sh\ -c*|*sh\ -lc*|*\\*|*\'*|*\"*) ;;
    *) exit 0 ;;
esac

# This gate is best-effort; the sandbox is the real boundary, and deeply
# obfuscated shell forms are out of scope when parsing is unavailable.
# shellcheck disable=SC2016  # Literal shell syntax is matched, not expanded here.
plausibly_invokes_codex_exec() {
    local command="$1"
    local codex_exec_re codex_exec_fragment_re data_command_re control_re interpreter_re

    # Permit any text between the executable and subcommand so global options,
    # wrappers, and uncertain tokenization reach the parser. Extra parser runs
    # are preferable to allowing a plausible codex exec unchecked.
    codex_exec_re='(^|[^[:alnum:]_/-])["'\'']?([^"'\''[:space:];|&()<>]+/)?codex["'\'']?([^[:alnum:]_-]|$).*["'\'']?exec($|[^[:alnum:]_-])'
    codex_exec_fragment_re='(^|[^[:alnum:]_/-])["'\'']*c["'\'']*o["'\'']*d["'\'']*e["'\'']*x["'\'']*([^[:alnum:]_-]|$).*["'\'']*e["'\'']*x["'\'']*e["'\'']*c["'\'']*($|[^[:alnum:]_-])'
    data_command_re='^[[:space:]]*([^[:space:];&|()`]+/)?(echo|printf|grep|cat|ls)([[:space:]]|$)'
    control_re='[;&|()`]'
    interpreter_re='(^|[;&|()`[:space:]])(eval|([^/[:space:]]+/)?(ba|z|da|k)?sh)([[:space:]]|$)'

    if [[ $command =~ $data_command_re && ! $command =~ $control_re &&
          $command != *$'\n'* && $command != *'$('* ]]; then
        return 1
    fi
    [[ $command =~ $codex_exec_re || $command =~ $codex_exec_fragment_re ||
       $command =~ $interpreter_re || $command == *\\* ]]
}

plausibly_invokes_codex_exec "$COMMAND" || exit 0

if ! command -v python3 >/dev/null 2>&1; then
    echo "[gate-codex-exec] python3 not found; blocking plausible codex exec unchecked." >&2
    POLICY_STATUS="blocked"
else
# Act only on `codex exec`; leave fast/strong, codex review, codex login, etc. alone.
POLICY_STATUS="$(
    CODEX_GATE_COMMAND="$COMMAND" python3 - <<'PY'
import os
import re
import shlex

FLAG_APPROVALS = "--dangerously-bypass-approvals-and-sandbox"
FLAG_REPO = "--skip-git-repo-check"
CONTROL_OPERATORS = {"\n", ";", ";;", ";&", ";;&", "&&", "||", "|", "|&", "&", "(", ")"}
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
GLOBAL_OPTIONS_WITH_VALUES = {
    "-C",
    "--cd",
    "-c",
    "--config",
    "--enable",
    "--disable",
    "-i",
    "--image",
    "-m",
    "--model",
    "--local-provider",
    "-p",
    "--profile",
    "-s",
    "--sandbox",
    "-a",
    "--ask-for-approval",
    "--add-dir",
}
SHORT_GLOBAL_OPTIONS_WITH_VALUES = {"-C", "-c", "-i", "-m", "-p", "-s", "-a"}
TERMINAL_GLOBAL_OPTIONS = {"-h", "--help", "-V", "--version"}
MAX_SCAN_DEPTH = 3  # Matches the rm guard's existing bounded wrapper recursion.
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
SHELL_OPTIONS_WITH_VALUE = {"-O", "+O", "-o", "+o", "--init-file", "--rcfile"}
KEYWORDS = {"do", "then", "else", "elif", "if", "while", "until", "!"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
DURATION = re.compile(r"^\d+(?:\.\d+)?[smhd]?$")
TOOL_WORD = re.compile(r"(?:^|[^A-Za-z0-9_/-])codex(?:[^A-Za-z0-9_-]|$)")


def strip_line_comments(command):
    out = []
    quote = None
    word_start = True
    i = 0

    while i < len(command):
        char = command[i]

        if quote:
            if quote == '"' and char == "\\" and i + 1 < len(command):
                if command[i + 1] == "\n":
                    i += 2
                    continue
                out.append(char)
                i += 1
                out.append(command[i])
                i += 1
                continue
            out.append(char)
            if char == quote:
                quote = None
            i += 1
            continue

        if char == "\\" and i + 1 < len(command):
            if command[i + 1] == "\n":
                out.append(" ")
                i += 2
                continue
            out.append(char)
            i += 1
            out.append(command[i])
            word_start = False
            i += 1
            continue

        if char == "#" and word_start:
            while i < len(command) and command[i] != "\n":
                i += 1
            continue

        if char in "'\"":
            quote = char
            out.append(char)
            word_start = False
            i += 1
            continue

        out.append(char)
        word_start = char.isspace() or char in ";|&()<>"
        i += 1

    return "".join(out)


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


def shell_tokens(command):
    lexer = shlex.shlex(strip_line_comments(command), posix=True, punctuation_chars="();<>|&\n")
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


def is_codex_word(word):
    return os.path.basename(word) == "codex"


def args_after_global_options(args):
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--" or arg in TERMINAL_GLOBAL_OPTIONS:
            return []
        if arg in GLOBAL_OPTIONS_WITH_VALUES:
            index += 2
            continue
        if arg.startswith("--") and arg.split("=", 1)[0] in GLOBAL_OPTIONS_WITH_VALUES:
            index += 1 if "=" in arg else 2
            continue
        if any(
            arg.startswith(option) and arg != option
            for option in SHORT_GLOBAL_OPTIONS_WITH_VALUES
        ):
            index += 1
            continue
        if arg.startswith("-") and arg != "-":
            index += 1
            continue
        return args[index:]
    return []


def exec_flags(args):
    flags = set()
    for arg in args:
        if arg == "--":
            break
        if arg in {FLAG_APPROVALS, FLAG_REPO}:
            flags.add(arg)
    return flags


def candidates_from_argv(argv, depth):
    if depth > MAX_SCAN_DEPTH:
        return [], True
    candidates = []
    ambiguous = False
    index = 0
    while index < len(argv) and (argv[index] in KEYWORDS or ASSIGNMENT.match(argv[index])):
        index += 1

    while index < len(argv) and os.path.basename(argv[index]) in WRAPPERS:
        wrapper = os.path.basename(argv[index])
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
    head = os.path.basename(argv[index])
    if head == "codex":
        return [argv[index:]], ambiguous
    if head in PLAIN_NON_EXECUTING:
        return candidates, ambiguous
    if head in SHELLS:
        option_index = index + 1
        while option_index < len(argv):
            option = argv[option_index]
            if option == "-c" or (
                option.startswith("-") and not option.startswith("--") and "c" in option[1:]
            ):
                if option_index + 1 >= len(argv):
                    return candidates, True
                return command_candidates(argv[option_index + 1], depth + 1)
            if option in SHELL_OPTIONS_WITH_VALUE:
                if option_index + 1 >= len(argv):
                    return candidates, True
                option_index += 2
                continue
            if not option.startswith(("-", "+")) or option in {"-", "+"}:
                break
            option_index += 1
        return candidates, ambiguous
    if head == "eval":
        if index + 1 < len(argv):
            return command_candidates(" ".join(argv[index + 1 :]), depth + 1)
        return candidates, ambiguous

    later_codex = [
        candidate_index
        for candidate_index in range(index + 1, len(argv))
        if is_codex_word(argv[candidate_index])
    ]
    if later_codex:
        candidates.extend(argv[candidate_index:] for candidate_index in later_codex)
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
    for command_words in simple_commands(tokens):
        word_candidates, word_ambiguous = candidates_from_argv(argv_words(command_words), depth)
        candidates.extend(word_candidates)
        ambiguous = ambiguous or word_ambiguous
    return candidates, ambiguous


candidates, ambiguous = command_candidates(os.environ.get("CODEX_GATE_COMMAND", ""))
found = False
for candidate in candidates:
    args = args_after_global_options(candidate[1:])
    if args and args[0] == "exec":
        found = True
        if {FLAG_APPROVALS, FLAG_REPO} - exec_flags(args[1:]):
            print("blocked")
            raise SystemExit

if ambiguous:
    print("parse_error")
else:
    print("allowed" if found else "none")
PY
)"
fi

case "$POLICY_STATUS" in
    none|allowed)
        exit 0
        ;;
    blocked)
        ;;
    parse_error)
        if plausibly_invokes_codex_exec "$COMMAND"; then
            echo "[gate-codex-exec] command parse failed; blocking plausible codex exec unchecked." >&2
        else
            echo "[gate-codex-exec] command parse failed outside codex exec; allowing command unchecked." >&2
            exit 0
        fi
        ;;
    *)
        if plausibly_invokes_codex_exec "$COMMAND"; then
            echo "[gate-codex-exec] parser failed; blocking plausible codex exec unchecked." >&2
        else
            echo "[gate-codex-exec] parser failed; allowing command unchecked." >&2
            exit 0
        fi
        ;;
esac

cat >&2 <<'EOF'
Bare `codex exec` is blocked. Use a lane wrapper instead:
  - fast "prompt"      # default for code tasks
  - strong "prompt"    # load-bearing / architecture / security
  - fast --file PATH   # for prompts larger than ~1KB
  - /codex-review --plan|--hypothesis|--arch   # adversarial review
Wrappers encode the canonical flag set and handle quota fallback (reference/model-delegation.md).
For raw `codex exec` (e.g. reproducing the /codex-review invocation), include the full
flag set per reference/codex-invocation.md:
  --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check ...
EOF
exit 2
