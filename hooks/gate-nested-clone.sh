#!/usr/bin/env bash
# gate-nested-clone.sh - PreToolUse(Bash) deny gate
# Denies `git clone` that would create a clone inside an existing git repo.
# The clone-inside-clone footgun: running `git clone <url>` while already inside
# a working tree silently nests the new repo as a subdirectory, almost never intended.
# Config: matcher "Bash"; this script performs its own relevance check. Input:
# stdin JSON. Deny: exit 2 + stderr.
set -uo pipefail

# Fail OPEN on infra problems: without jq we cannot parse the input, so warn and allow.
if ! command -v jq >/dev/null 2>&1; then
    echo "[nested-clone] jq not found; skipping nested-clone check." >&2
    exit 0
fi

INPUT="$(</dev/stdin)"
case "$INPUT" in
    *git*|*eval*|*sh\ -c*|*sh\ -lc*|*\\*|*\'*|*'`'*|*'$'*) ;;
    *) exit 0 ;;
esac
COMMAND="$(jq -r '.tool_input.command // empty' <<<"$INPUT" 2>/dev/null || true)"

case "$COMMAND" in
    *git*|*eval*|*sh\ -c*|*sh\ -lc*|*\\*|*\'*|*\"*) ;;
    *) exit 0 ;;
esac

# Keep plainly irrelevant calls on a Bash-only fast path. Quotes, escapes, and
# interpreter commands are sent to the tokenizer because they can hide or build
# an invocation; the Python policy below is authoritative about command position.
# shellcheck disable=SC2016  # Literal shell syntax is matched, not expanded here.
plausibly_mentions_git_clone() {
    local command="$1"
    local git_re clone_re data_command_re control_re interpreter_re

    git_re='(^|[;&|()`[:space:]])([^[:space:];&|()`]+/)?git([[:space:];&|()`]|$)'
    clone_re='(^|[^[:alnum:]_-])clone([^[:alnum:]_-]|$)'
    data_command_re='^[[:space:]]*([^[:space:];&|()`]+/)?(echo|printf|grep|cat|ls)([[:space:]]|$)'
    control_re='[;&|()`]'
    interpreter_re='(^|[;&|()`[:space:]])(eval|([^/[:space:]]+/)?(ba|z|da|k)?sh)([[:space:]]|$)'

    if [[ $command =~ $data_command_re && ! $command =~ $control_re &&
          $command != *$'\n'* && $command != *'$('* ]]; then
        return 1
    fi
    [[ ($command =~ $git_re && $command =~ $clone_re) ||
       $command =~ $interpreter_re || $command == *\\* ||
       $command == *\'* || $command == *\"* ]]
}

plausibly_mentions_git_clone "$COMMAND" || exit 0

if ! command -v python3 >/dev/null 2>&1; then
    echo "[nested-clone] python3 not found; skipping nested-clone check." >&2
    exit 0
fi

# The hook's cwd is only the initial shell cwd. A later `cd` or `git -C` can move the
# clone into or out of a repository, so the parser determines the enclosing repo per clone.
PARENT_REPO=$(git rev-parse --show-toplevel 2>/dev/null || true)

# Parse clone operands without mistaking option values for the source or target.
CLONE_STATUS="$(
    NESTED_CLONE_COMMAND="$COMMAND" python3 - <<'PY'
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
TOOL_WORD = re.compile(r"(?:^|[^A-Za-z0-9_/-])git(?:[^A-Za-z0-9_-]|$)")
GIT_OPTIONS_WITH_VALUES = {
    "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix",
    "--config-env",
}
OPTIONS_WITH_VALUES = {
    "-b", "--branch", "-c", "--config", "--depth", "--filter", "-j", "--jobs",
    "-o", "--origin", "--reference", "--reference-if-able", "--ref-format",
    "--revision", "--separate-git-dir", "--server-option", "--shallow-exclude",
    "--shallow-since", "--template", "-u", "--upload-pack", "--bundle-uri",
}
SHORT_OPTIONS_WITH_VALUES = {"-b", "-c", "-j", "-o", "-u"}


def command_basename(token):
    return token.rsplit("/", 1)[-1]


def shell_tokens(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
    lexer.whitespace_split = True
    lexer.whitespace = " \t\r"
    lexer.commenters = ""
    return list(lexer)


def simple_commands(tokens):
    separator = ""
    current = []
    for token in tokens:
        if token in CONTROL_OPERATORS:
            if current:
                yield separator, current
                current = []
            separator = token
            continue
        current.append(token)
    if current:
        yield separator, current


def argv_words(words):
    argv = []
    index = 0
    while index < len(words):
        token = words[index]
        if token.isdigit() and index + 1 < len(words) and words[index + 1] in REDIRECT_OPERATORS:
            index += 3
            continue
        if token in REDIRECT_OPERATORS:
            index += 2
            continue
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


def candidates_from_argv(argv, tool, depth, cwd):
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
                nested_candidates, nested_ambiguous = candidates_from_argv(
                    split_argv + argv[index + 2 :], tool, depth + 1, cwd
                )
                return candidates + nested_candidates, ambiguous or nested_ambiguous
            if wrapper == "env" and token.startswith("--split-string="):
                try:
                    split_argv = shlex.split(token.split("=", 1)[1], posix=True)
                except ValueError:
                    return candidates, True
                nested_candidates, nested_ambiguous = candidates_from_argv(
                    split_argv + argv[index + 1 :], tool, depth + 1, cwd
                )
                return candidates + nested_candidates, ambiguous or nested_ambiguous
            if wrapper == "env" and token.startswith("-S") and token != "-S":
                try:
                    split_argv = shlex.split(token[2:], posix=True)
                except ValueError:
                    return candidates, True
                nested_candidates, nested_ambiguous = candidates_from_argv(
                    split_argv + argv[index + 1 :], tool, depth + 1, cwd
                )
                return candidates + nested_candidates, ambiguous or nested_ambiguous
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
    if head == tool:
        candidates.append((argv[index:], cwd))
        return candidates, ambiguous
    if head in PLAIN_NON_EXECUTING:
        return candidates, ambiguous
    if head in SHELLS:
        script = None
        for option_index in range(index + 1, len(argv)):
            option = argv[option_index]
            if option == "-c" or (
                option.startswith("-") and not option.startswith("--") and "c" in option[1:]
            ):
                if option_index + 1 < len(argv):
                    script = argv[option_index + 1]
                else:
                    ambiguous = True
                break
            if not option.startswith("-") or option == "-":
                break
        if script is not None:
            nested_candidates, nested_ambiguous = command_candidates(
                script, tool, depth + 1, cwd
            )
            candidates.extend(nested_candidates)
            ambiguous = ambiguous or nested_ambiguous
        return candidates, ambiguous
    if head == "eval":
        if index + 1 < len(argv):
            nested_candidates, nested_ambiguous = command_candidates(
                " ".join(argv[index + 1 :]), tool, depth + 1, cwd
            )
            candidates.extend(nested_candidates)
            ambiguous = ambiguous or nested_ambiguous
        return candidates, ambiguous

    later_tools = [
        candidate_index
        for candidate_index in range(index + 1, len(argv))
        if command_basename(argv[candidate_index]) == tool
    ]
    if later_tools:
        candidates.extend((argv[candidate_index:], cwd) for candidate_index in later_tools)
        ambiguous = True
    elif TOOL_WORD.search(" ".join(argv[index + 1 :])):
        ambiguous = True
    return candidates, ambiguous


def literal_directory(base, target):
    if (
        not target
        or target.startswith("~")
        or any(character in target for character in "$`*?[]{}")
    ):
        return None
    expanded = os.path.expanduser(target)
    resolved = os.path.realpath(
        expanded if os.path.isabs(expanded) else os.path.join(base, expanded)
    )
    return resolved if os.path.isdir(resolved) else None


def direct_cd_target(argv):
    if not argv or command_basename(argv[0]) != "cd":
        return None
    index = 1
    while index < len(argv) and argv[index] in {"-L", "-P", "-e"}:
        index += 1
    if index < len(argv) and argv[index] == "--":
        index += 1
    return argv[index] if index + 1 == len(argv) else ""


def command_candidates(command, tool, depth=0, cwd=None):
    if depth > MAX_SCAN_DEPTH:
        return [], True
    if cwd is None:
        cwd = os.getcwd()
    candidates = []
    nested, malformed = nested_commands(command)
    ambiguous = malformed
    for inner in nested:
        inner_candidates, inner_ambiguous = command_candidates(inner, tool, depth + 1, cwd)
        candidates.extend(inner_candidates)
        ambiguous = ambiguous or inner_ambiguous
    try:
        tokens = shell_tokens(command)
    except ValueError:
        return candidates, True
    commands = list(simple_commands(tokens))
    current_cwd = cwd
    for command_index, (_, words) in enumerate(commands):
        argv = argv_words(words)
        cd_target = direct_cd_target(argv)
        if cd_target is not None:
            next_separator = commands[command_index + 1][0] if command_index + 1 < len(commands) else ""
            if cd_target and next_separator in {";", "&&", "\n"}:
                resolved_cd = literal_directory(current_cwd, cd_target)
                if resolved_cd is None:
                    ambiguous = True
                else:
                    current_cwd = resolved_cd
            elif next_separator:
                ambiguous = True
            continue
        word_candidates, word_ambiguous = candidates_from_argv(
            argv, tool, depth, current_cwd
        )
        candidates.extend(word_candidates)
        ambiguous = ambiguous or word_ambiguous
    return candidates, ambiguous


def git_args(argv, cwd):
    index = 1
    effective_cwd = cwd
    while index < len(argv):
        arg = argv[index]
        if arg == "--":
            return argv[index + 1 :], False, effective_cwd
        if arg in NO_EXEC_WRAPPER_OPTIONS:
            return [], False, effective_cwd
        if not arg.startswith("-") or arg == "-":
            return argv[index:], False, effective_cwd
        if arg in GIT_OPTIONS_WITH_VALUES:
            if index + 1 >= len(argv):
                return [], True, effective_cwd
            if arg == "-C":
                resolved_cwd = literal_directory(effective_cwd, argv[index + 1])
                if resolved_cwd is None:
                    return [], True, effective_cwd
                effective_cwd = resolved_cwd
            elif arg in {"--git-dir", "--work-tree"}:
                return [], True, effective_cwd
            index += 2
        elif arg.startswith("--") and arg.split("=", 1)[0] in GIT_OPTIONS_WITH_VALUES:
            if arg.split("=", 1)[0] in {"--git-dir", "--work-tree"}:
                return [], True, effective_cwd
            index += 1 if "=" in arg else 2
        elif arg.startswith("-C") and arg != "-C":
            resolved_cwd = literal_directory(effective_cwd, arg[2:])
            if resolved_cwd is None:
                return [], True, effective_cwd
            effective_cwd = resolved_cwd
            index += 1
        elif arg.startswith("-c") and arg != "-c":
            index += 1
        else:
            index += 1
    return [], False, effective_cwd


def clone_destination(args):
    if not args or args[0] != "clone":
        return None, False
    operands = []
    options = True
    index = 1
    while index < len(args):
        arg = args[index]
        if options and arg == "--":
            options = False
            index += 1
        elif options and arg in OPTIONS_WITH_VALUES:
            if index + 1 >= len(args):
                return None, True
            index += 2
        elif options and arg.startswith("--") and "=" in arg:
            index += 1
        elif options and any(
            arg.startswith(option) and arg != option for option in SHORT_OPTIONS_WITH_VALUES
        ):
            index += 1
        elif options and arg.startswith("-") and arg != "-":
            index += 1
        else:
            operands.append(arg)
            index += 1
    if not operands:
        return None, False
    return operands[-1] if len(operands) > 1 else ".", False


def enclosing_repository(path):
    current = os.path.realpath(path)
    while True:
        if os.path.exists(os.path.join(current, ".git")):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


command = os.environ.get("NESTED_CLONE_COMMAND", "")
candidates, ambiguous = command_candidates(command, "git")
for candidate, candidate_cwd in candidates:
    args, git_ambiguous, effective_cwd = git_args(candidate, candidate_cwd)
    destination, clone_ambiguous = clone_destination(args)
    ambiguous = ambiguous or git_ambiguous or clone_ambiguous
    if destination is None:
        continue
    destination = os.path.expanduser(destination)
    destination = os.path.realpath(
        destination
        if os.path.isabs(destination)
        else os.path.join(effective_cwd, destination)
    )
    repository = enclosing_repository(destination)
    if repository is None:
        continue
    try:
        if os.path.commonpath((repository, destination)) == repository:
            print(f"inside:{repository}")
            raise SystemExit
    except ValueError:
        pass

if ambiguous and (TOOL_WORD.search(command) and re.search(r"(?:^|[^A-Za-z0-9_-])clone(?:[^A-Za-z0-9_-]|$)", command)):
    print("ambiguous")
else:
    print("outside")
PY
)"

case "$CLONE_STATUS" in
    outside)
        exit 0
        ;;
    inside:*)
        PARENT_REPO="${CLONE_STATUS#inside:}"
        ;;
    ambiguous)
        echo "[nested-clone] clone destination is ambiguous; blocking because it could land inside an existing repository." >&2
        exit 2
        ;;
    *)
        echo "[nested-clone] command parse failed; blocking a plausible clone whose destination could not be classified safely." >&2
        exit 2
        ;;
esac

# Inside a repo + target resolving beneath it = nested clone-inside-clone. Deny.
echo "git clone inside existing repo at ${PARENT_REPO}. This creates a nested clone-inside-clone, which is almost never intended. Pass an absolute-path target, or cd to a parent directory first (e.g. 'cd ~ && git clone ...')." >&2
exit 2
