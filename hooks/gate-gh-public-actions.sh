#!/usr/bin/env bash
# gate-gh-public-actions.sh - PreToolUse(Bash) deny gate.
#
# Two layers enforcing the no-public-posts + privacy rules on gh CLI usage:
#   Layer 1: deny public-facing gh actions (issue/pr/release/gist/repo
#            create/comment/edit/close/reopen/merge/delete/publish) AND
#            gh api WRITE calls (-X / --method POST|PATCH|PUT|DELETE, plus the
#            implicit POST that field flags force) without explicit approval.
#   Layer 2: privacy scrub. Deny any gh command whose PUBLISHABLE content
#            (inline --body/--title or a referenced --body-file) carries a
#            private identifier from the local denylist.
#
# Contract: matcher "Bash"; this script performs its own relevance check. Input is
# tool JSON on STDIN. Deny = human-readable reason on stderr + exit 2. Allow =
# exit 0. Infrastructure failure (no jq/python3) WARNS and allows (fail open); a gate
# never hard-blocks on its own broken plumbing.
#
# The denylist is NOT hardcoded: it is read from gitignored token files (see
# config/private-tokens.example.txt). Ship the .example.txt template only.
set -uo pipefail

# Fail open if jq is unavailable: warn, allow. (infra error, not a policy hit)
if ! command -v jq >/dev/null 2>&1; then
    echo "[gate-gh-public-actions] jq not found; allowing command without gh public-action check." >&2
    exit 0
fi

INPUT="$(</dev/stdin)"
case "$INPUT" in
    *gh*|*eval*|*sh\ -c*|*sh\ -lc*|*\\*|*\'*|*'`'*|*'$'*) ;;
    *) exit 0 ;;
esac
COMMAND="$(jq -r '.tool_input.command // empty' <<<"$INPUT" 2>/dev/null || true)"

case "$COMMAND" in
    *gh*|*eval*|*sh\ -c*|*sh\ -lc*|*\\*|*\'*|*\"*) ;;
    *) exit 0 ;;
esac

# Start the full parser for command-position gh, common launch wrappers, and any
# ambiguous quoting. A guarded name passed only to a plainly non-executing data
# command is irrelevant; uncertain heads still reach the parser.
plausibly_invokes_gh() {
    local command="$1"
    local direct_re wrapper_re gh_any_re gh_fragment_re data_command_re control_re interpreter_re
    local quote="" character previous following
    local index

    # shellcheck disable=SC2016  # Backticks and dollar syntax are literal regex input.
    direct_re='(^|[;&|()`])[[:space:]]*([[:alpha:]_][[:alnum:]_]*=[^[:space:];&|()`]+[[:space:]]+)*["'\'']?([^"'\''[:space:];&|()`]+/)?gh["'\'']?([[:space:];&|()`]|$)'
    # shellcheck disable=SC2016  # Backticks and dollar syntax are literal regex input.
    wrapper_re='(^|[;&|()`])[[:space:]]*(sudo|doas|command|builtin|exec|env|nice|ionice|nohup|stdbuf|time|timeout|xargs|setsid|chronic)[[:space:]]+[^;&|()`]*["'\'']?([^"'\''[:space:];&|()`]+/)?gh["'\'']?([[:space:];&|()`]|$)'
    gh_any_re='(^|[^[:alnum:]_-])gh([^[:alnum:]_-]|$)'
    gh_fragment_re='(^|[^[:alnum:]_-])["'\'']*g["'\'']*h["'\'']*([^[:alnum:]_-]|$)'
    data_command_re='^[[:space:]]*([^[:space:];&|()`]+/)?(echo|printf|grep|cat|ls)([[:space:]]|$)'
    control_re='[;&|()`]'
    interpreter_re='(^|[;&|()`[:space:]])(eval|([^/[:space:]]+/)?(ba|z|da|k)?sh)([[:space:]]|$)'

    # A guarded name used only as data to one of these commands cannot execute.
    # Substitutions and later shell segments deliberately bypass this fast path.
    # shellcheck disable=SC2016  # Match a literal command-substitution opener.
    if [[ $command =~ $data_command_re && ! $command =~ $control_re &&
          $command != *$'\n'* && $command != *'$('* ]]; then
        return 1
    fi

    if [[ $command =~ $direct_re ]] || [[ $command =~ $wrapper_re ]] || [[ $command =~ $interpreter_re ]]; then
        return 0
    fi

    # Find an unquoted gh word without spawning another interpreter. Backslashes
    # and malformed quotes are ambiguous, so they deliberately reach Python.
    for ((index = 0; index < ${#command}; index++)); do
        character="${command:index:1}"
        if [[ $character == \\ ]]; then
            return 0
        fi
        if [[ -n $quote ]]; then
            if [[ $character == "$quote" ]]; then
                quote=""
            fi
            continue
        fi
        if [[ $character == "'" || $character == '"' ]]; then
            quote="$character"
            continue
        fi
        if [[ ${command:index:2} == gh ]]; then
            previous=""
            following=""
            if ((index > 0)); then
                previous="${command:index-1:1}"
            fi
            if ((index + 2 < ${#command})); then
                following="${command:index+2:1}"
            fi
            if [[ ! $previous =~ [[:alnum:]_-] && ! $following =~ [[:alnum:]_-] ]]; then
                return 0
            fi
        fi
    done

    if [[ -n $quote ]]; then
        return 0
    fi

    if [[ $command =~ $gh_any_re || $command =~ $gh_fragment_re ]]; then
        return 0
    fi

    return 1
}

plausibly_invokes_gh "$COMMAND" || exit 0

if ! command -v python3 >/dev/null 2>&1; then
    echo "[gate-gh-public-actions] python3 not found; allowing command without gh public-action check." >&2
    exit 0
fi

# --- Layer 1: public-facing / write actions require explicit approval ---
public_action_status() {
    GH_GATE_COMMAND="$COMMAND" python3 - <<'PY'
import os
import re
import shlex

PUBLIC_GROUPS = {"issue", "pr", "release", "gist", "repo"}
PUBLIC_ACTIONS = {
    "create",
    "comment",
    "review",
    "edit",
    "close",
    "reopen",
    "merge",
    "delete",
    "publish",
    "upload",
    "delete-asset",
    "transfer",
    "rename",
    "fork",
    "clone-as-public",
}
API_WRITE_METHODS = {"POST", "PATCH", "PUT", "DELETE"}
API_FIELD_FLAGS = {"-f", "-F", "--field", "--raw-field", "--input"}
CONTROL_OPERATORS = {"\n", ";", ";;", ";&", ";;&", "&&", "||", "|", "|&", "&", "(", ")"}
REDIRECT_OPERATORS = {
    "<", ">", "<<", ">>", "<>", "<<-", "<<<", ">|", "<&", ">&", "&>", "&>>",
}
LOOSE_CONTROL_OPERATORS = {";", ";;", ";&", "&&", "||", "|", "|&", "&", "(", ")", "\n"}
LOOSE_CONTROL_STARTS = {";", "&", "|", "(", ")", "\n"}
GLOBAL_FLAGS_WITH_VALUES = {"-R", "--repo", "--hostname", "--jq", "--template", "--config-dir"}
GLOBAL_FLAGS_WITH_ATTACHED_VALUES = ("-R",)
TERMINAL_GLOBAL_FLAGS = {"-h", "--help", "--version"}
SHELL_WRAPPERS = {"bash", "sh", "zsh", "dash", "ksh"}
MAX_NESTING_DEPTH = 32
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
KEYWORDS = {"do", "then", "else", "elif", "if", "while", "until", "!"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
DURATION = re.compile(r"^\d+(?:\.\d+)?[smhd]?$")
GH_WORD = re.compile(r"(?:^|[^A-Za-z0-9_/-])gh(?:[^A-Za-z0-9_-]|$)")


def shell_tokens(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
    lexer.whitespace_split = True
    lexer.whitespace = " \t\r"
    lexer.commenters = ""
    return list(lexer)


def loose_shell_tokens(command):
    tokens = []
    current = []
    quote = None
    index = 0

    def flush_current():
        if current:
            tokens.append("".join(current))
            current.clear()

    while index < len(command):
        char = command[index]
        if char == "\\" and quote != "'":
            if index + 1 < len(command):
                current.append(command[index + 1])
            index += 2
            continue
        if quote is not None:
            if char == quote:
                quote = None
            else:
                current.append(char)
            index += 1
            continue
        if char in {"'", '"'}:
            quote = char
            index += 1
            continue
        if char.isspace():
            flush_current()
            index += 1
            continue
        if char in LOOSE_CONTROL_STARTS:
            flush_current()
            pair = command[index : index + 2]
            if pair in LOOSE_CONTROL_OPERATORS:
                tokens.append(pair)
                index += 2
            else:
                tokens.append(char)
                index += 1
            continue
        current.append(char)
        index += 1

    flush_current()
    return tokens


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


def command_args_after_global_flags(args):
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--":
            return args[index + 1 :]
        if arg in TERMINAL_GLOBAL_FLAGS:
            return []
        if arg in GLOBAL_FLAGS_WITH_VALUES:
            index += 2
            continue
        if any(arg.startswith(flag) and arg != flag for flag in GLOBAL_FLAGS_WITH_ATTACHED_VALUES):
            index += 1
            continue
        if arg.startswith("--") and arg.split("=", 1)[0] in GLOBAL_FLAGS_WITH_VALUES:
            index += 1 if "=" in arg else 2
            continue
        if arg.startswith("-") and arg != "-":
            index += 1
            continue
        return args[index:]
    return []


def is_gh_word(word):
    return os.path.basename(word) == "gh"


def is_shell_wrapper(word):
    return os.path.basename(word) in SHELL_WRAPPERS


def inline_shell_script(command_words):
    if not command_words or not is_shell_wrapper(command_words[0]):
        return None

    index = 1
    while index < len(command_words):
        arg = command_words[index]
        if arg == "--":
            return None
        if arg == "-c" or (arg.startswith("-") and not arg.startswith("--") and "c" in arg[1:]):
            return command_words[index + 1] if index + 1 < len(command_words) else None
        if arg == "--login":
            index += 1
            continue
        if not arg.startswith("-") or arg == "-":
            return None
        index += 1
    return None


def is_api_field_flag(arg):
    return arg in API_FIELD_FLAGS or any(
        arg.startswith(f"{flag}=") for flag in API_FIELD_FLAGS if flag.startswith("--")
    )


def api_write_requested(args):
    method = None
    has_field_flag = False
    index = 1
    while index < len(args):
        arg = args[index]
        if arg == "--":
            break
        if arg == "-X":
            if index + 1 < len(args):
                method = args[index + 1].upper()
                index += 2
                continue
        elif arg.startswith("-X") and arg != "-X":
            method = arg[2:].lstrip("=").upper()
        elif arg == "--method":
            if index + 1 < len(args):
                method = args[index + 1].upper()
                index += 2
                continue
        elif arg.startswith("--method="):
            method = arg.split("=", 1)[1].upper()
        elif is_api_field_flag(arg):
            has_field_flag = True
        index += 1
    return method in API_WRITE_METHODS or (has_field_flag and method != "GET")


def read_backtick_command(command, start):
    index = start
    while index < len(command):
        char = command[index]
        if char == "\\":
            index += 2
            continue
        if char == "`":
            return command[start:index], index
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
            if char == "'":
                quote = None
            index += 1
            continue
        if quote == '"':
            if char == '"':
                quote = None
                index += 1
                continue
            if char == "`":
                _, end = read_backtick_command(command, index + 1)
                index = end + 1 if end is not None else index + 1
                continue
            if char == "$" and index + 1 < len(command) and command[index + 1] == "(":
                depth += 1
                index += 2
                continue
            index += 1
            continue

        if char == "'":
            quote = "'"
            index += 1
            continue
        if char == '"':
            quote = '"'
            index += 1
            continue
        if char == "`":
            _, end = read_backtick_command(command, index + 1)
            index = end + 1 if end is not None else index + 1
            continue
        if char == "$" and index + 1 < len(command) and command[index + 1] == "(":
            depth += 1
            index += 2
            continue
        if char == "(":
            depth += 1
            index += 1
            continue
        if char == ")":
            depth -= 1
            if depth == 0:
                return command[start:index], index
            index += 1
            continue
        index += 1
    return None, None


def nested_commands(command):
    nested = []
    quote = None
    index = 0
    while index < len(command):
        char = command[index]
        if char == "\\" and quote != "'":
            index += 2
            continue
        if quote == "'":
            if char == "'":
                quote = None
            index += 1
            continue
        if char == "'" and quote is None:
            quote = "'"
            index += 1
            continue
        if char == '"':
            quote = None if quote == '"' else '"'
            index += 1
            continue
        if char == "$" and index + 1 < len(command) and command[index + 1] == "(":
            inner, end = read_dollar_command(command, index + 2)
            if inner is not None:
                nested.append(inner)
                index = end + 1
                continue
        if char == "`":
            inner, end = read_backtick_command(command, index + 1)
            if inner is not None:
                nested.append(inner)
                index = end + 1
                continue
        index += 1
    return nested


def status_from_command_words(command_words, depth):
    if depth >= MAX_NESTING_DEPTH:
        return "parse_error"
    argv = argv_words(command_words)
    index = 0
    ambiguous = False
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
                return "none"
            if wrapper == "env" and token in {"-S", "--split-string"}:
                if index + 1 >= len(argv):
                    return "parse_error"
                try:
                    split_argv = shlex.split(argv[index + 1], posix=True)
                except ValueError:
                    return "parse_error"
                return status_from_command_words(split_argv + argv[index + 2 :], depth + 1)
            if wrapper == "env" and token.startswith("--split-string="):
                try:
                    split_argv = shlex.split(token.split("=", 1)[1], posix=True)
                except ValueError:
                    return "parse_error"
                return status_from_command_words(split_argv + argv[index + 1 :], depth + 1)
            if wrapper == "env" and token.startswith("-S") and token != "-S":
                try:
                    split_argv = shlex.split(token[2:], posix=True)
                except ValueError:
                    return "parse_error"
                return status_from_command_words(split_argv + argv[index + 1 :], depth + 1)
            if not token.startswith("-") or token == "-":
                break
            if token in WRAPPER_OPTIONS_WITH_VALUE.get(wrapper, set()):
                if index + 1 >= len(argv):
                    return "parse_error"
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
        return "parse_error" if ambiguous else "none"

    head = os.path.basename(argv[index])
    if head == "gh":
        args = command_args_after_global_flags(argv[index + 1 :])
        if len(args) >= 2 and args[0] in PUBLIC_GROUPS and args[1] in PUBLIC_ACTIONS:
            return "blocked"
        if args and args[0] == "api" and api_write_requested(args):
            return "blocked"
        return "allowed"
    if head in PLAIN_NON_EXECUTING:
        return "none"
    if head in SHELL_WRAPPERS:
        script = inline_shell_script(argv[index:])
        if script is None:
            return "parse_error" if ambiguous else "none"
        return check_command(script, depth + 1)
    if head == "eval":
        if index + 1 >= len(argv):
            return "none"
        return check_command(" ".join(argv[index + 1 :]), depth + 1)

    found = False
    for candidate_index in range(index + 1, len(argv)):
        if not is_gh_word(argv[candidate_index]):
            continue
        found = True
        args = command_args_after_global_flags(argv[candidate_index + 1 :])
        if len(args) >= 2 and args[0] in PUBLIC_GROUPS and args[1] in PUBLIC_ACTIONS:
            return "blocked"
        if args and args[0] == "api" and api_write_requested(args):
            return "blocked"
    if found:
        return "allowed"
    if ambiguous or GH_WORD.search(" ".join(argv[index + 1 :])):
        return "parse_error"
    return "none"


def raw_parse_error_status(command, depth):
    found = False
    for command_words in simple_commands(loose_shell_tokens(command)):
        status = status_from_command_words(command_words, depth)
        if status in {"blocked", "parse_error"}:
            return status
        if status == "allowed":
            found = True
    for nested in nested_commands(command):
        status = check_command(nested, depth + 1)
        if status in {"blocked", "parse_error"}:
            return status
        if status == "allowed":
            found = True
    return "allowed" if found else "none"


def check_command(command, depth=0):
    if depth >= MAX_NESTING_DEPTH:
        return raw_parse_error_status(command, depth)
    try:
        tokens = shell_tokens(command)
    except ValueError:
        return "parse_error"

    found = False
    for command_words in simple_commands(tokens):
        status = status_from_command_words(command_words, depth)
        if status in {"blocked", "parse_error"}:
            return status
        if status == "allowed":
            found = True

    for nested in nested_commands(command):
        status = check_command(nested, depth + 1)
        if status in {"blocked", "parse_error"}:
            return status
        if status == "allowed":
            found = True

    return "allowed" if found else "none"


print(check_command(os.environ.get("GH_GATE_COMMAND", "")))
PY
}

PUBLIC_ACTION_STATUS="$(public_action_status)"
case "$PUBLIC_ACTION_STATUS" in
    blocked|allowed)
        ;;
    none)
        exit 0
        ;;
    parse_error)
        echo "[gate-gh-public-actions] command parse failed; blocking gh command unchecked." >&2
        exit 2
        ;;
    *)
        echo "[gate-gh-public-actions] parser failed; allowing command unchecked." >&2
        exit 0
        ;;
esac

if [ "$PUBLIC_ACTION_STATUS" = "blocked" ]; then
    echo "BLOCKED: this gh command performs a public-facing or write action (issue/pr/release/repo/gist or a gh api write) and requires explicit user approval. Show the user the exact content you want to post and get confirmation first (no-public-posts rule)." >&2
    exit 2
fi

# --- Layer 2: privacy scrub of publishable content ---
# Collect text that could reach a public surface: --body-file/-F file contents +
# inline --body/-b and --title/-t values. Bare path arguments are deliberately
# NOT scanned, so a clean post written from a private-looking path is allowed.
PUB=""
for bf in $(printf '%s' "$COMMAND" | grep -oE -- '(--body-file|-F)[=[:space:]]+[^[:space:]]+' | sed -E 's/^(--body-file|-F)[=[:space:]]+//'); do
    [ -f "$bf" ] && PUB="$PUB
$(cat "$bf" 2>/dev/null)"
done
PUB="$PUB
$(printf '%s' "$COMMAND" | grep -oiE -- "(--body|-b|--title|-t)[=[:space:]]+(\"[^\"]*\"|'[^']*'|[^[:space:]]+)" || true)"

# Build the denylist from gitignored token files. Format (per the .example.txt):
# one token per line, matched as a fixed string, case-insensitive; lines that
# start with # and blank lines are ignored.
STRATA_HOME="${STRATA_HOME:-$HOME/.strata}"
DENY_TOKENS=""
for tf in "$STRATA_HOME/config/private-tokens.txt" "$STRATA_HOME/.local/private-tokens.txt"; do
    [ -f "$tf" ] || continue
    while IFS= read -r line; do
        line="${line%$'\r'}"
        case "$line" in ''|'#'*) continue ;; esac
        DENY_TOKENS="$DENY_TOKENS$line
"
    done < "$tf"
done

# No denylist configured -> nothing to scrub against; allow.
if [ -n "$DENY_TOKENS" ] && printf '%s' "$PUB" | grep -qiF -f <(printf '%s' "$DENY_TOKENS"); then
    echo "BLOCKED (privacy): the publishable content of this gh command contains a private identifier from your local denylist. Replace it with generic, domain-neutral values and re-confirm before posting (privacy rule)." >&2
    printf '%s' "$PUB" | grep -iniF -f <(printf '%s' "$DENY_TOKENS") 2>/dev/null | head -3 >&2
    exit 2
fi

exit 0
