#!/usr/bin/env bash
# gate-destructive-git.sh - PreToolUse(Bash) confirm gate.
#
# Asks for confirmation before destructive, NON-push git operations that can
# discard uncommitted or otherwise-unrecoverable work (reset --hard, clean -fd,
# checkout/restore of paths, branch -D, stash clear/drop).
#
# Uses the ASK contract, not a hard deny: it emits
#   {"hookSpecificOutput":{"hookEventName":"PreToolUse",
#    "permissionDecision":"ask","permissionDecisionReason":"..."}}
# on STDOUT and exits 0. This surfaces an interactive confirm prompt, so routine
# work is never hard-blocked and a confirmed command never re-blocks on re-run.
#
# git push is out of scope here: force-push is governed separately (warn before
# force-pushing main/master); this gate covers worktree-destructive ops only.
#
# Contract: settings.json matcher "Bash"; this script performs its own relevance
# check. Input is the tool call JSON on STDIN; the command is read from
# .tool_input.command. Infra failure
# (no jq) WARNS to stderr and allows (fail open); a confirm gate never hard-blocks
# on its own broken plumbing.
set -uo pipefail

INPUT="$(</dev/stdin)"
case "$INPUT" in
    *git*|*eval*|*sh\ -c*|*sh\ -lc*|*\\*|*\'*|*'`'*|*'$'*) ;;
    *) exit 0 ;;
esac

# Only relevant calls need the JSON parser; guarded calls retain the fail-open warning.
if ! command -v jq >/dev/null 2>&1; then
    echo "[gate-destructive-git] jq not found; allowing command without destructive-git check." >&2
    exit 0
fi

COMMAND="$(jq -r '.tool_input.command // empty' <<<"$INPUT" 2>/dev/null || true)"

case "$COMMAND" in
    *git*|*eval*|*sh\ -c*|*sh\ -lc*|*\\*|*\'*|*\"*) ;;
    *) exit 0 ;;
esac

# Keep plainly irrelevant calls on a Bash-only fast path. The tokenizer remains
# authoritative for quoted, escaped, wrapped, and interpreter-built commands.
# shellcheck disable=SC2016  # Literal shell syntax is matched, not expanded here.
plausibly_mentions_git() {
    local command="$1"
    local git_re data_command_re control_re interpreter_re

    git_re='(^|[;&|()`[:space:]])([^[:space:];&|()`]+/)?git([[:space:];&|()`]|$)'
    data_command_re='^[[:space:]]*([^[:space:];&|()`]+/)?(echo|printf|grep|cat|ls)([[:space:]]|$)'
    control_re='[;&|()`]'
    interpreter_re='(^|[;&|()`[:space:]])(eval|([^/[:space:]]+/)?(ba|z|da|k)?sh)([[:space:]]|$)'

    if [[ $command =~ $data_command_re && ! $command =~ $control_re &&
          $command != *$'\n'* && $command != *'$('* ]]; then
        return 1
    fi
    [[ $command =~ $git_re || $command =~ $interpreter_re ||
       $command == *\\* || $command == *\'* || $command == *\"* ]]
}

plausibly_mentions_git "$COMMAND" || exit 0

if ! command -v python3 >/dev/null 2>&1; then
    echo "[gate-destructive-git] python3 not found; allowing command without destructive-git check." >&2
    exit 0
fi

REASON="$(GIT_GATE_COMMAND="$COMMAND" python3 - <<'PY'
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
SHELL_OPTIONS_WITH_VALUE = {"-O", "+O", "-o", "+o", "--init-file", "--rcfile"}
KEYWORDS = {"do", "then", "else", "elif", "if", "while", "until", "!"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
DURATION = re.compile(r"^\d+(?:\.\d+)?[smhd]?$")
TOOL_WORD = re.compile(r"(?:^|[^A-Za-z0-9_/-])git(?:[^A-Za-z0-9_-]|$)")
GIT_OPTIONS_WITH_VALUES = {
    "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix",
    "--config-env",
}


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


def candidates_from_argv(argv, tool, depth):
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
                return candidates_from_argv(split_argv + argv[index + 2 :], tool, depth + 1)
            if wrapper == "env" and token.startswith("--split-string="):
                try:
                    split_argv = shlex.split(token.split("=", 1)[1], posix=True)
                except ValueError:
                    return candidates, True
                return candidates_from_argv(split_argv + argv[index + 1 :], tool, depth + 1)
            if wrapper == "env" and token.startswith("-S") and token != "-S":
                try:
                    split_argv = shlex.split(token[2:], posix=True)
                except ValueError:
                    return candidates, True
                return candidates_from_argv(split_argv + argv[index + 1 :], tool, depth + 1)
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
                return command_candidates(argv[option_index + 1], tool, depth + 1)
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
            return command_candidates(" ".join(argv[index + 1 :]), tool, depth + 1)
        return candidates, ambiguous

    later_tools = [
        candidate_index
        for candidate_index in range(index + 1, len(argv))
        if command_basename(argv[candidate_index]) == tool
    ]
    if later_tools:
        candidates.extend(argv[candidate_index:] for candidate_index in later_tools)
        ambiguous = True
    elif TOOL_WORD.search(" ".join(argv[index + 1 :])):
        ambiguous = True
    return candidates, ambiguous


def command_candidates(command, tool, depth=0):
    if depth > MAX_SCAN_DEPTH:
        return [], True
    candidates = []
    nested, malformed = nested_commands(command)
    ambiguous = malformed
    for inner in nested:
        inner_candidates, inner_ambiguous = command_candidates(inner, tool, depth + 1)
        candidates.extend(inner_candidates)
        ambiguous = ambiguous or inner_ambiguous
    try:
        tokens = shell_tokens(command)
    except ValueError:
        return candidates, True
    for words in simple_commands(tokens):
        word_candidates, word_ambiguous = candidates_from_argv(argv_words(words), tool, depth)
        candidates.extend(word_candidates)
        ambiguous = ambiguous or word_ambiguous
    return candidates, ambiguous


def git_args(argv):
    index = 1
    while index < len(argv):
        arg = argv[index]
        if arg == "--":
            return argv[index + 1 :], False
        if arg in NO_EXEC_WRAPPER_OPTIONS:
            return [], False
        if not arg.startswith("-") or arg == "-":
            return argv[index:], False
        if arg in GIT_OPTIONS_WITH_VALUES:
            if index + 1 >= len(argv):
                return [], True
            index += 2
        elif arg.startswith("--") and arg.split("=", 1)[0] in GIT_OPTIONS_WITH_VALUES:
            index += 1 if "=" in arg else 2
        elif any(arg.startswith(option) and arg != option for option in {"-C", "-c"}):
            index += 1
        else:
            index += 1
    return [], False


def reason_for(args):
    if not args:
        return ""
    command = args[0]
    command_args = args[1:]
    if command == "reset" and "--hard" in command_args:
        return "git reset --hard discards all uncommitted changes in the worktree"
    if command == "clean" and any(
        arg == "--force" or (arg.startswith("-") and not arg.startswith("--") and "f" in arg[1:])
        for arg in command_args
    ):
        return "git clean -f permanently deletes untracked files"
    if command == "branch" and (
        any(arg.startswith("-D") for arg in command_args)
        or ("--delete" in command_args and "--force" in command_args)
    ):
        return "git branch -D force-deletes a branch and can drop unmerged commits"
    if command in {"checkout", "restore"} and ("." in command_args or "--" in command_args):
        return "git checkout/restore of paths overwrites uncommitted worktree changes"
    if command == "stash" and command_args and command_args[0] in {"clear", "drop"}:
        return "git stash clear/drop discards stashed work"
    return ""


def fallback_reason(command):
    patterns = (
        (r"git\s+reset\s+.*--hard", "git reset --hard discards all uncommitted changes in the worktree"),
        (r"git\s+clean\s+(?:-[A-Za-z]*f|--force)", "git clean -f permanently deletes untracked files"),
        (r"git\s+branch\s+(?:-D|.*--delete\s+--force|.* -D )", "git branch -D force-deletes a branch and can drop unmerged commits"),
        (r"git\s+(?:checkout|restore)\s+(?:\.|--(?:$|\s))", "git checkout/restore of paths overwrites uncommitted worktree changes"),
        (r"git\s+stash\s+(?:clear|drop)", "git stash clear/drop discards stashed work"),
    )
    for pattern, reason in patterns:
        if re.search(pattern, command):
            return reason
    return ""


command = os.environ.get("GIT_GATE_COMMAND", "")
candidates, ambiguous = command_candidates(command, "git")
for candidate in candidates:
    args, git_ambiguous = git_args(candidate)
    ambiguous = ambiguous or git_ambiguous
    reason = reason_for(args)
    if reason:
        print(reason)
        raise SystemExit
if ambiguous:
    print(fallback_reason(command))
PY
)"

[ -z "$REASON" ] && exit 0

jq -n --arg r "$REASON. Confirm this is intended before it runs. (git push is not gated here.)" \
  '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$r}}'
exit 0
