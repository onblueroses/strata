#!/usr/bin/env bash
# gate-pre-push.sh - PreToolUse(Bash) gate on `git push`.
#
# Push-time work has usually already iterated through review. This gate performs two
# focused checks and surfaces either result as a DECISION rather than a hard wall:
#
#   1. PRIVACY SCAN. Scan the outgoing diff for secrets in every repo and, on PUBLIC
#      repos, for private identifiers from the install-local denylist.
#
#   2. REVIEW CHECK. Confirm that the outgoing work carries a fresh `.verify-passed`
#      marker from this session with no later edits.
#
# A clean, reviewed diff proceeds immediately. Otherwise the push stops once per HEAD
# (exit 2) and prints the findings; repeating the SAME push records the decision to
# proceed. Redacting a real hit creates a new commit and triggers a new scan. Running
# /verify writes the marker and clears the review check.
#
# Input: stdin JSON with .tool_input.command and .session_id.
# Allow: exit 0. Surface/stop: exit 2 + stderr (fed back to the calling agent).
set -uo pipefail

STRATA_HOME="${STRATA_HOME:-$HOME/.strata}"
KB_DIR="${KB_DIR:-$STRATA_HOME/workspace}"
STATE_DIR="${STATE_DIR:-$KB_DIR/state}"

INPUT="$(cat)"
COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"
SESSION_ID="$(printf '%s' "$INPUT" | jq -r '.session_id // "unknown"' 2>/dev/null || echo unknown)"
SID8="${SESSION_ID:0:8}"

# Plain data commands cannot launch git. Keep this common path Bash-only while
# sending quoting, substitution, and control syntax to the tokenizer below.
plain_data_command='^[[:space:]]*(echo|printf|grep)([[:space:]]|$)'
# shellcheck disable=SC2016  # Literal shell construction markers are matched here.
if [[ $COMMAND =~ $plain_data_command &&
      $COMMAND != *[';&|()`$\']* && $COMMAND != *$'\n'* ]]; then
    exit 0
fi

emit_block() {  # $1 = reason slug; additive, fail-open telemetry (no command/identifier leak)
    local B S
    B=$(jq -cn --arg h pre-push --arg t Bash --arg r "$1" --arg d deny '{hook:$h,tool:$t,reason:$r,decision:$d}' 2>/dev/null)
    S=$(printf '%s' "$INPUT" | jq -r '.session_id//"unknown"' 2>/dev/null || echo unknown)
    bash "$STRATA_HOME/telemetry/telemetry-emit.sh" hook_block "$S" "$B" 2>/dev/null || true
}

# Shell-tokenize before deciding whether this is a push. The executable may be an absolute
# path or sit behind an ordinary launch wrapper; comparing basenames after wrapper unwrapping
# keeps those forms on the same path as bare git. Unknown launchers and malformed commands
# containing plausible git/push words are treated as ambiguous and scanned conservatively.
plausibly_mentions_git_push() {
    local git_word='(^|[^[:alnum:]_-])([^[:space:];&|()]+/)?git([^[:alnum:]_-]|$)'
    local push_word='(^|[^[:alnum:]_-])push([^[:alnum:]_-]|$)'
    [[ $COMMAND =~ $git_word && $COMMAND =~ $push_word ]]
}

PARSE_RESULT=""
if command -v python3 >/dev/null 2>&1; then
    PARSE_RESULT="$(PUSH_GATE_COMMAND="$COMMAND" python3 - <<'PY' 2>/dev/null || true
import json
import os
import re
import shlex

CONTROL_OPERATORS = {"\n", ";", ";;", ";&", ";;&", "&&", "||", "|", "|&", "&", "(", ")"}
REDIRECT_OPERATORS = {"<", ">", "<<", ">>", "<>", "<<-", "<<<", ">|", "<&", ">&", "&>", "&>>"}
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
    "env": {"-u", "--unset", "-C", "--chdir", "--argv0"},
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
# These commands are explicit negative controls whose operands are data, not an executable.
# Everything else with plausible git/push operands stays ambiguous and therefore gets scanned.
NON_LAUNCHERS = {"echo", "grep", "printf"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
GIT_OPTIONS_WITH_VALUE = {
    "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix",
    "--config-env",
}
GIT_TERMINAL_OPTIONS = {"-h", "--help", "--version", "--exec-path", "--html-path", "--man-path", "--info-path"}
ASSIGNMENT = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", re.DOTALL)
VARIABLE_REFERENCE = re.compile(
    r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}|\$([A-Za-z_][A-Za-z0-9_]*)"
)
GIT_RETARGET_ASSIGNMENT = re.compile(
    r"^(?:GIT_DIR|GIT_WORK_TREE|GIT_COMMON_DIR|GIT_NAMESPACE)="
)
DURATION = re.compile(r"^\d+(?:\.\d+)?[smhd]?$", re.IGNORECASE)


def basename(word):
    return os.path.basename(word)


def shell_tokens(command):
    lexer = shlex.shlex(command, posix=True, punctuation_chars="();<>|&\n")
    lexer.whitespace_split = True
    lexer.whitespace = " \t\r"
    lexer.commenters = ""
    return list(lexer)


def segments(tokens):
    result = []
    separator = ""
    current = []
    for token in tokens:
        if token in CONTROL_OPERATORS:
            if current:
                result.append((separator, current))
                current = []
            separator = token
        else:
            current.append(token)
    if current:
        result.append((separator, current))
    return result


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


def plausible_words(words):
    text = " ".join(words)
    return bool(
        re.search(r"(?<![A-Za-z0-9_-])(?:[^\s;&|()]+/)?git(?![A-Za-z0-9_-])", text)
        and re.search(r"(?<![A-Za-z0-9_-])push(?![A-Za-z0-9_-])", text)
    )


def consume_wrapper(argv, index, wrapper):
    options_with_value = WRAPPER_OPTIONS_WITH_VALUE.get(wrapper, set())
    while index < len(argv):
        token = argv[index]
        if token == "--":
            return index + 1, None, "ok"
        if token in NO_EXEC_WRAPPER_OPTIONS:
            return len(argv), None, "none"
        if wrapper == "command" and token in COMMAND_INSPECTION_OPTIONS:
            return len(argv), None, "none"
        if wrapper == "env" and token in ("-S", "--split-string"):
            if index + 1 >= len(argv):
                return len(argv), None, "ambiguous"
            try:
                embedded = shlex.split(argv[index + 1], posix=True)
            except ValueError:
                return len(argv), None, "ambiguous"
            return index + 2, embedded, "ok"
        if wrapper == "env" and token.startswith("--split-string="):
            try:
                embedded = shlex.split(token.split("=", 1)[1], posix=True)
            except ValueError:
                return len(argv), None, "ambiguous"
            return index + 1, embedded, "ok"
        if wrapper == "env" and token.startswith("-S") and token != "-S":
            try:
                embedded = shlex.split(token[2:], posix=True)
            except ValueError:
                return len(argv), None, "ambiguous"
            return index + 1, embedded, "ok"
        if not token.startswith("-") or token == "-":
            break
        option = token.split("=", 1)[0]
        if token in options_with_value:
            if index + 1 >= len(argv):
                return len(argv), None, "ambiguous"
            index += 2
        elif "=" in token and option in options_with_value:
            index += 1
        else:
            index += 1

    if wrapper == "timeout":
        if index >= len(argv) or not DURATION.fullmatch(argv[index]):
            return len(argv), None, "ambiguous"
        index += 1
    if wrapper == "env":
        while index < len(argv) and ASSIGNMENT.fullmatch(argv[index]):
            index += 1
    return index, None, "ok"


def git_push_target(args):
    target_steps = []
    index = 0
    while index < len(args):
        arg = args[index]
        if arg == "--":
            index += 1
            break
        if arg in GIT_TERMINAL_OPTIONS:
            return "none", []
        if arg in GIT_OPTIONS_WITH_VALUE:
            if index + 1 >= len(args):
                return "ambiguous", target_steps
            if arg == "-C":
                target_steps.append(args[index + 1])
            elif arg in {"--git-dir", "--work-tree", "--namespace"}:
                target_steps.append(None)
            index += 2
            continue
        option = arg.split("=", 1)[0]
        if "=" in arg and option in GIT_OPTIONS_WITH_VALUE:
            if option == "-C":
                target_steps.append(arg.split("=", 1)[1])
            elif option in {"--git-dir", "--work-tree", "--namespace"}:
                target_steps.append(None)
            index += 1
            continue
        if arg.startswith("-C") and arg != "-C":
            target_steps.append(arg[2:])
            index += 1
            continue
        if arg.startswith("-c") and arg != "-c":
            index += 1
            continue
        if arg.startswith("-") and arg != "-":
            index += 1
            continue
        break

    if index < len(args) and args[index] == "push":
        return "match", target_steps
    return "none", []


def resolve_target(target, assignments):
    output = []
    last = 0
    for match in VARIABLE_REFERENCE.finditer(target):
        name = match.group(1) or match.group(2)
        if name not in assignments:
            return None
        output.append(target[last : match.start()])
        output.append(assignments[name])
        last = match.end()
    output.append(target[last:])
    result = "".join(output)
    return None if "$" in result or "`" in result else result


def resolve_directory(base, target, assignments):
    resolved = resolve_target(target, assignments)
    if resolved is None:
        return None
    if not resolved:
        return base
    expanded = os.path.expanduser(resolved)
    return os.path.realpath(
        expanded if os.path.isabs(expanded) else os.path.join(base, expanded)
    )


def literal_assignment(word):
    match = ASSIGNMENT.fullmatch(word)
    if not match:
        return None
    name, value = match.groups()
    if not value or any(character in value for character in "$`\\~"):
        return name, None
    return name, value


def resolve_segment(words, assignments, cwd):
    argv = argv_words(words)
    index = 0
    while index < len(argv) and ASSIGNMENT.fullmatch(argv[index]):
        index += 1

    while index < len(argv):
        executable_word = resolve_target(argv[index], assignments)
        expansion_is_ambiguous = (
            executable_word is None
            or not re.fullmatch(r"[A-Za-z0-9_./+-]+", executable_word)
        )
        if expansion_is_ambiguous:
            if any(argument == "push" for argument in argv[index + 1 :]):
                return "ambiguous", "", True
            executable = basename(argv[index])
        else:
            executable = basename(executable_word)
        if executable == "git":
            status, target_steps = git_push_target(argv[index + 1 :])
            retargeted_by_environment = any(
                GIT_RETARGET_ASSIGNMENT.match(token)
                for token in argv[:index]
            )
            if status != "none" and retargeted_by_environment:
                return "ambiguous", "", True
            target = cwd
            for step in target_steps:
                if step is None:
                    return "ambiguous", "", True
                target = resolve_directory(target, step, assignments)
                if target is None:
                    return "ambiguous", "", True
            return status, target if target_steps else "", False
        if executable == "eval" or executable in SHELLS:
            nested_words = []
            nested_unresolved = False
            for argument in argv[index + 1 :]:
                resolved_argument = resolve_target(argument, assignments)
                if resolved_argument is None:
                    nested_unresolved = True
                    resolved_argument = argument
                nested_words.append(resolved_argument)
            nested_text = " ".join(nested_words)
            mentions_push = bool(
                re.search(r"(?<![A-Za-z0-9_-])push(?![A-Za-z0-9_-])", nested_text)
            )
            mentions_git = bool(
                re.search(
                    r"(?<![A-Za-z0-9_-])(?:[^\s;&|()]+/)?git(?![A-Za-z0-9_-])",
                    nested_text,
                )
            )
            if mentions_push and (mentions_git or nested_unresolved):
                return "ambiguous", "", True
        if executable not in WRAPPERS:
            if executable in NON_LAUNCHERS:
                return "none", "", False
            return (
                ("ambiguous", "", False)
                if plausible_words(argv[index + 1 :])
                else ("none", "", False)
            )

        next_index, embedded, status = consume_wrapper(argv, index + 1, executable)
        if status != "ok":
            return status, "", False
        if embedded is not None:
            argv = embedded + argv[next_index:]
            index = 0
            while index < len(argv) and ASSIGNMENT.fullmatch(argv[index]):
                index += 1
            continue
        index = next_index

    return "none", "", False


def direct_cd_target(words):
    argv = argv_words(words)
    index = 0
    while index < len(argv) and ASSIGNMENT.fullmatch(argv[index]):
        index += 1
    if index >= len(argv) or basename(argv[index]) != "cd":
        return None
    index += 1
    while index < len(argv):
        if argv[index] == "--":
            index += 1
            break
        if argv[index] in ("-L", "-P", "-e"):
            index += 1
            continue
        break
    if index >= len(argv):
        return "$HOME"
    return argv[index] if index + 1 == len(argv) else ""


command = os.environ.get("PUSH_GATE_COMMAND", "")
raw_plausible = bool(
    re.search(r"(?<![A-Za-z0-9_-])(?:[^\s;&|()]+/)?git(?![A-Za-z0-9_-])", command)
    and re.search(r"(?<![A-Za-z0-9_-])push(?![A-Za-z0-9_-])", command)
)
try:
    parsed_segments = segments(shell_tokens(command))
except ValueError:
    print(json.dumps({"status": "ambiguous" if raw_plausible else "none", "target": ""}))
    raise SystemExit

current_cwd = os.getcwd()
match_targets = []
ambiguous_targets = []
# A parenthesized group has subshell-local cwd and assignment state. Do not let
# either escape into a later push unless this parser grows explicit scope tracking.
unresolved_target = any(
    "(" in separator or ")" in separator for separator, _ in parsed_segments
) or any(
    GIT_RETARGET_ASSIGNMENT.match(word)
    for _, words in parsed_segments
    for word in words
) or "`" in command
assignments = {"HOME": os.environ.get("HOME", "")}
for segment_index, (separator, words) in enumerate(parsed_segments):
    outgoing_separator = (
        parsed_segments[segment_index + 1][0]
        if segment_index + 1 < len(parsed_segments)
        else ""
    )
    assignment_values = [literal_assignment(word) for word in words]
    if assignment_values and all(value is not None for value in assignment_values):
        if separator in ("", ";") and outgoing_separator in (";", "&&", "||"):
            for name, value in assignment_values:
                if value is None:
                    assignments.pop(name, None)
                else:
                    assignments[name] = value
        else:
            for name, _ in assignment_values:
                assignments.pop(name, None)
        continue

    cd_target = direct_cd_target(words)
    if cd_target is not None:
        cd_scope_is_safe = (
            separator in ("", ";", "\n")
            and outgoing_separator in (";", "&&", "\n")
        )
        resolved_cd = (
            resolve_directory(current_cwd, cd_target, assignments)
            if cd_target and cd_scope_is_safe
            else None
        )
        if resolved_cd is None:
            unresolved_target = True
        else:
            current_cwd = resolved_cd
        continue

    status, target, target_unresolved = resolve_segment(words, assignments, current_cwd)
    unresolved_target = unresolved_target or target_unresolved
    if status == "match":
        match_targets.append(target or current_cwd)
    if status == "ambiguous":
        ambiguous_targets.append(target or current_cwd)
    if status == "none":
        assignments = {"HOME": assignments.get("HOME", os.environ.get("HOME", ""))}

targets = []
for target in match_targets + ambiguous_targets:
    if target not in targets:
        targets.append(target)

commands = [shlex.join(["git", "-C", target, "push"]) if target else "git push" for target in targets]
if len(targets) > 1:
    status = "multi"
elif match_targets:
    status = "match"
elif ambiguous_targets:
    status = "ambiguous"
else:
    status = "none"
print(json.dumps({
    "status": status,
    "target": targets[0] if targets else "",
    "commands": commands,
    "unresolved_target": unresolved_target,
}))
PY
)"
fi

PARSER_STATUS=""
TARGET_DIR=""
UNRESOLVED_TARGET="false"
if [ -n "$PARSE_RESULT" ]; then
    PARSER_STATUS="$(printf '%s' "$PARSE_RESULT" | jq -r '.status // empty' 2>/dev/null || true)"
    TARGET_DIR="$(printf '%s' "$PARSE_RESULT" | jq -r '.target // empty' 2>/dev/null || true)"
    UNRESOLVED_TARGET="$(printf '%s' "$PARSE_RESULT" | jq -r '.unresolved_target // false' 2>/dev/null || true)"
fi
if [ "$UNRESOLVED_TARGET" = "true" ]; then
    case "$PARSER_STATUS" in
        match|ambiguous|multi) ;;
        *) plausibly_mentions_git_push || exit 0 ;;
    esac
    echo "gate-pre-push: could not resolve the repository target safely; refusing to let a plausible push bypass scanning." >&2
    exit 2
fi
case "$PARSER_STATUS" in
    match|ambiguous|multi) ;;
    none) exit 0 ;;
    *)
        plausibly_mentions_git_push || exit 0
        PARSER_STATUS="ambiguous"
        ;;
esac

# Need git and a work tree.
command -v git &>/dev/null || exit 0

# A compound command can carry pushes to multiple repositories. Run this same gate once for
# each resolved target so every repo gets its own scan and surfaced marker; the generated
# commands are parser input only and are never executed.
if [ "$PARSER_STATUS" = "multi" ]; then
    if ! printf '%s' "$PARSE_RESULT" | jq -e '.commands | length > 1' >/dev/null 2>&1; then
        echo "gate-pre-push: ambiguous multi-repository push could not be split safely." >&2
        exit 2
    fi
    MULTI_STATUS=0
    while IFS= read -r nested_command; do
        if ! NESTED_INPUT="$(printf '%s' "$INPUT" \
            | jq -c --arg command "$nested_command" '.tool_input.command = $command' 2>/dev/null)"; then
            echo "gate-pre-push: ambiguous multi-repository push could not be split safely." >&2
            exit 2
        fi
        printf '%s' "$NESTED_INPUT" | bash "$0"
        nested_status=$?
        case "$nested_status" in
            0) ;;
            2) MULTI_STATUS=2 ;;
            *) MULTI_STATUS=2 ;;
        esac
    done < <(printf '%s' "$PARSE_RESULT" | jq -r '.commands[]')
    exit "$MULTI_STATUS"
fi

# PreToolUse runs before the shell command, so the hook cwd does not reflect `git -C` or a
# preceding `cd`. Resolve those forms from the command and make every repository decision
# below from that target. A missing or inaccessible explicit target cannot be pushed either.
if [ -z "$TARGET_DIR" ] && [ "$PARSER_STATUS" = "ambiguous" ]; then
    TARGET_DIR="$(printf '%s' "$COMMAND" \
        | grep -oE '(^|[[:space:]])-C[[:space:]]+[^[:space:];&|]+' | tail -1 \
        | sed -E 's/.*-C[[:space:]]+//')"
fi
if [ -z "$TARGET_DIR" ] && [ "$PARSER_STATUS" = "ambiguous" ]; then
    TARGET_DIR="$(printf '%s' "$COMMAND" \
        | grep -oE '(^|[;&|(][[:space:]]*)cd[[:space:]]+[^[:space:];&|]+' | tail -1 \
        | sed -E 's/.*cd[[:space:]]+//')"
fi
TARGET_DIR="${TARGET_DIR%\"}"; TARGET_DIR="${TARGET_DIR#\"}"
TARGET_DIR="${TARGET_DIR%\'}"; TARGET_DIR="${TARGET_DIR#\'}"
# shellcheck disable=SC2016,SC2088  # These patterns intentionally match unexpanded shell text.
case "$TARGET_DIR" in
    '~')        TARGET_DIR="$HOME" ;;
    '~/'*)      TARGET_DIR="$HOME/${TARGET_DIR#\~/}" ;;
    '$HOME')    TARGET_DIR="$HOME" ;;
    '$HOME/'*)  TARGET_DIR="$HOME/${TARGET_DIR#\$HOME/}" ;;
esac
if [ -n "$TARGET_DIR" ]; then
    if [ ! -d "$TARGET_DIR" ]; then
        echo "gate-pre-push: could not resolve the repository target '$TARGET_DIR' to an accessible directory; refusing to skip the push scan." >&2
        exit 2
    fi
    if ! cd "$TARGET_DIR" 2>/dev/null; then
        echo "gate-pre-push: could not enter the repository target '$TARGET_DIR'; refusing to skip the push scan." >&2
        exit 2
    fi
fi

if ! git rev-parse --is-inside-work-tree &>/dev/null; then
    echo "gate-pre-push: a plausible push did not resolve to a Git work tree; refusing to skip the push scan." >&2
    exit 2
fi

# The configured runtime workspace is local state, not a public code repository.
ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
case "$ROOT" in
    "$KB_DIR"|"$KB_DIR/"*) exit 0 ;;
esac

# --- What is actually going out? ---
# Prefer the tracked upstream, then origin/main|master, else (first push, no counterpart)
# the whole history from the empty tree.
RANGE=""
if UP="$(git rev-parse --abbrev-ref --symbolic-full-name '@{u}' 2>/dev/null)" && [ -n "$UP" ]; then
    RANGE="${UP}..HEAD"
elif git rev-parse --verify origin/main &>/dev/null; then
    RANGE="origin/main..HEAD"
elif git rev-parse --verify origin/master &>/dev/null; then
    RANGE="origin/master..HEAD"
else
    EMPTY_TREE="$(git hash-object -t tree /dev/null 2>/dev/null || true)"
    [ -n "$EMPTY_TREE" ] && RANGE="${EMPTY_TREE}..HEAD"
fi
[ -z "$RANGE" ] && exit 0

# Nothing to push (e.g. delete/tags-only) -> nothing to gate.
[ -z "$(git log "$RANGE" --oneline 2>/dev/null | head -1)" ] && exit 0

# Keep a location map beside the matcher input so findings can identify a source line
# without repeating the sensitive content that triggered the match.
added_context() {
    awk '
        /^\+\+\+ / {
            path = substr($0, 5)
            sub(/^b\//, "", path)
            next
        }
        /^@@ / {
            if (match($0, /\+[0-9]+(,[0-9]+)?/)) {
                next_line = substr($0, RSTART + 1, RLENGTH - 1)
                sub(/,.*/, "", next_line)
            }
            next
        }
        /^\+/ && $0 !~ /^\+\+\+/ {
            shown_path = (path == "" || path == "/dev/null") ? "<outgoing diff>" : path
            printf "%s:%d\n", shown_path, next_line
            next_line++
            next
        }
        /^\+/ { next_line++; next }
        /^ / { next_line++; next }
    '
}

# The endpoint diff is the fail-open fallback if history enumeration cannot be completed.
CUMULATIVE_PATCH="$(git diff "$RANGE" 2>/dev/null || true)"
CUMULATIVE_ADDED="$(printf '%s\n' "$CUMULATIVE_PATCH" | grep -E '^\+' | grep -vE '^\+\+\+' || true)"
CUMULATIVE_CONTEXT="$(printf '%s\n' "$CUMULATIVE_PATCH" | added_context || true)"
CUMULATIVE_FILES="$(git diff --name-only "$RANGE" 2>/dev/null || true)"
ADDED="$CUMULATIVE_ADDED"
ADDED_CONTEXT="$CUMULATIVE_CONTEXT"
ADDED_FILES="$CUMULATIVE_FILES"

# Endpoint diffs hide content added and removed in separate outgoing commits. Build the
# scan input from every commit, but publish it only when the complete walk succeeds.
if COMMITS="$(git rev-list "$RANGE" 2>/dev/null)" && [ -n "$COMMITS" ]; then
    PER_COMMIT_ADDED=""
    PER_COMMIT_CONTEXT=""
    PER_COMMIT_FILES=""
    per_commit_ok=1
    while IFS= read -r sha; do
        [ -n "$sha" ] || continue
        if ! PATCH="$(git show -U0 --format= "$sha" 2>/dev/null)"; then
            per_commit_ok=0
            break
        fi
        if ! COMMIT_FILES="$(git show --format= --name-only "$sha" 2>/dev/null)"; then
            per_commit_ok=0
            break
        fi

        COMMIT_ADDED="$(printf '%s\n' "$PATCH" | grep -E '^\+' | grep -vE '^\+\+\+' || true)"
        COMMIT_CONTEXT="$(printf '%s\n' "$PATCH" | added_context || true)"
        if [ -n "$COMMIT_ADDED" ]; then
            PER_COMMIT_ADDED+="${PER_COMMIT_ADDED:+$'\n'}$COMMIT_ADDED"
            PER_COMMIT_CONTEXT+="${PER_COMMIT_CONTEXT:+$'\n'}$COMMIT_CONTEXT"
        fi
        [ -n "$COMMIT_FILES" ] && PER_COMMIT_FILES+="${PER_COMMIT_FILES:+$'\n'}$COMMIT_FILES"
    done <<< "$COMMITS"

    if [ "$per_commit_ok" -eq 1 ]; then
        ADDED="$PER_COMMIT_ADDED"
        ADDED_CONTEXT="$PER_COMMIT_CONTEXT"
        ADDED_FILES="$(printf '%s\n' "$PER_COMMIT_FILES" | sed '/^$/d' | sort -u)"
    fi
fi

# Commit messages publish with the push and are permanent, but no diff contains them
# (`git show --format=` strips them by construction), so they need their own scan input.
MESSAGES="$(git log --format=%B "$RANGE" 2>/dev/null || true)"

# ============================================================================
# 1. PRIVACY SAFETY NET
# ============================================================================

# grep helper: case-insensitive ERE, `-e` so a leading '-' in the pattern (PEM headers) is
# never parsed as an option, and grep's no-match (1) never aborts under pipefail.
grepadd() { printf '%s\n' "$ADDED" | grep -inE -e "$1" 2>/dev/null || true; }
grepmsg() { printf '%s\n' "$MESSAGES" | grep -inE -e "$1" 2>/dev/null || true; }
# Filters for the FUZZY matchers only (never applied to strong token formats, to avoid
# false negatives like a real key on a line that happens to contain the word "test").
drop_placeholder() { grep -viE 'example|placeholder|your[_-]|xxxx+|<[^>]+>|dummy|changeme|redacted|sample|fake|env\[|environ|getenv|process\.env|import\.meta\.env|\$\{|os\.getenv|test[_-]?(key|token)|00000|123456|foo:bar' || true; }
drop_url_placeholder() { grep -viE 'example\.(com|org|net)|localhost|127\.0\.0\.1|your[_-]|xxxx+|<[^>]+>|user:(pass|password)@|placeholder' || true; }

# --- Secrets & credentials: blocked on ANY repo (a leaked key is bad everywhere). ---
# (a) Structural token formats. Front boundary (^|[^[:alnum:]]) stops substrings like "risk-".
SECRET_RE='(^|[^[:alnum:]])sk-ant-(api|admin|oat|sid)[0-9A-Za-z_-]{16,}' # Anthropic (key/admin/oauth)
SECRET_RE+='|(^|[^[:alnum:]])sk-(proj-)?[A-Za-z0-9_-]{20,}'        # OpenAI
SECRET_RE+='|(^|[^[:alnum:]])(sk|rk)_(live|test)_[A-Za-z0-9]{16,}' # Stripe secret/restricted
SECRET_RE+='|gh[porsu]_[A-Za-z0-9]{36,}'                           # GitHub token
SECRET_RE+='|github_pat_[A-Za-z0-9_]{40,}'                         # GitHub fine-grained PAT
SECRET_RE+='|glpat-[A-Za-z0-9_-]{20,}'                             # GitLab PAT
SECRET_RE+='|(AKIA|ASIA)[0-9A-Z]{16}'                              # AWS access key id
SECRET_RE+='|AIza[0-9A-Za-z_-]{35}'                                # Google API key
SECRET_RE+='|ya29\.[0-9A-Za-z_-]{20,}'                             # Google OAuth access token
SECRET_RE+='|(^|[^0-9A-Za-z_])1//0[A-Za-z0-9_-]{20,}'             # Google OAuth refresh token
SECRET_RE+='|xox[baprs]-[0-9A-Za-z-]{10,}'                         # Slack token
SECRET_RE+='|npm_[A-Za-z0-9]{36}'                                  # npm token
SECRET_RE+='|dop_v1_[a-f0-9]{64}'                                  # DigitalOcean token
SECRET_RE+='|hf_[A-Za-z0-9]{30,}'                                  # HuggingFace token
SECRET_RE+='|dckr_pat_[A-Za-z0-9_-]{20,}'                          # Docker Hub PAT
SECRET_RE+='|(FlyV1[[:space:]]|fm2_)[A-Za-z0-9+/=_-]{20,}'         # Fly.io token
SECRET_RE+='|tskey-(auth|api|client|reusable)-[A-Za-z0-9_-]{10,}' # Tailscale auth key
SECRET_RE+='|SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}'            # SendGrid
SECRET_RE+='|AC[0-9a-f]{32}'                                       # Twilio account SID
SECRET_RE+='|(^|[^0-9])[0-9]{8,10}:AA[A-Za-z0-9_-]{32,}'          # Telegram bot token
SECRET_RE+='|rpa_[A-Za-z0-9]{20,}'                                 # RunPod API key
SECRET_RE+='|(^|[^[:alnum:]])eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}' # JWT
SECRET_RE+='|-----BEGIN [A-Z ]*PRIVATE KEY-----'                   # PEM private key block

# (b) Credentials carried inside URLs, webhooks, DSNs, and auth headers.
SECRET_URL_RE='[a-z][a-z0-9+.-]*://[^/@:[:space:]]+:[^/@[:space:]]+@[^[:space:]/]'  # scheme://user:pass@host (DB/basic-auth/tokenised remote)
SECRET_URL_RE+='|https://hooks\.slack\.com/services/T[0-9A-Z]+/B[0-9A-Z]+/[0-9A-Za-z]{16,}'  # Slack webhook
SECRET_URL_RE+='|https://(ptb\.|canary\.)?discord(app)?\.com/api/webhooks/[0-9]{15,}/[0-9A-Za-z_-]{40,}'  # Discord webhook
SECRET_URL_RE+='|https://[0-9a-f]{16,}@[a-z0-9.-]*sentry\.io'      # Sentry DSN
SECRET_URL_RE+='|[Aa]uthorization:[[:space:]]*(Bearer|Basic)[[:space:]]+[A-Za-z0-9+/._=-]{20,}'  # auth header

# (c) Secret-named key assigned a long opaque value (catches ad-hoc secrets the formats miss).
GENERIC_SECRET_RE="(secret|token|passwd|password|api[_-]?key|access[_-]?key|client[_-]?secret|auth[_-]?token|private[_-]?key|aws_secret)([\"' ]*[:=]| =>)[[:space:]]*[\"'\`]?[A-Za-z0-9+/_=-]{24,}"

FINDINGS=""
DENYLIST_NOTICE=""

# Render only source context plus a one-way fingerprint of the full matched line. The
# fingerprint distinguishes repeated findings without disclosing usable secret material.
mask_hits() {
    local hits="$1" hit lineno content context fp
    while IFS= read -r hit; do
        [ -n "$hit" ] || continue
        lineno="${hit%%:*}"
        content="${hit#*:}"
        context="$(printf '%s\n' "$ADDED_CONTEXT" | awk -v wanted="$lineno" 'NR == wanted { print; exit }')"
        [ -n "$context" ] || context="<outgoing added line>"
        fp="$(printf '%s' "$content" | git hash-object --stdin 2>/dev/null | cut -c1-8)"
        [ -n "$fp" ] || fp="unavailable"
        printf '%s: %s [redacted: sha8:%s; length:%d]\n' "$lineno" "$context" "$fp" "${#content}"
    done <<< "$hits"
}

# Message hits carry no diff context, and fixing one means rewriting the commit rather
# than adding a redacting commit, so they are labelled separately from diff findings.
mask_msg_hits() {
    local hits="$1" hit lineno content fp
    while IFS= read -r hit; do
        [ -n "$hit" ] || continue
        lineno="${hit%%:*}"
        content="${hit#*:}"
        fp="$(printf '%s' "$content" | git hash-object --stdin 2>/dev/null | cut -c1-8)"
        [ -n "$fp" ] || fp="unavailable"
        printf 'message line %s [redacted: sha8:%s; length:%d]\n' "$lineno" "$fp" "${#content}"
    done <<< "$hits"
}

MSGHITS="$(grepmsg "$SECRET_RE|$SECRET_URL_RE" | head -4 || true)"
[ -n "$MSGHITS" ] && MSGHITS="$(mask_msg_hits "$MSGHITS")"
[ -n "$MSGHITS" ] && FINDINGS+=$'[SECRET] credential-shaped string in an outgoing COMMIT MESSAGE (amend or rebase to fix; a later commit cannot redact it):\n'"$MSGHITS"$'\n'

HITS="$(grepadd "$SECRET_RE" | head -6 || true)"
[ -n "$HITS" ] && HITS="$(mask_hits "$HITS")"
[ -n "$HITS" ] && FINDINGS+=$'[SECRET] credential-shaped string in outgoing diff:\n'"$HITS"$'\n'

UHITS="$(grepadd "$SECRET_URL_RE" | drop_url_placeholder | head -6 || true)"
[ -n "$UHITS" ] && UHITS="$(mask_hits "$UHITS")"
[ -n "$UHITS" ] && FINDINGS+=$'[SECRET] credential inside a URL / webhook / DSN / auth header:\n'"$UHITS"$'\n'

GHITS="$(grepadd "$GENERIC_SECRET_RE" | drop_placeholder | head -6 || true)"
[ -n "$GHITS" ] && GHITS="$(mask_hits "$GHITS")"
[ -n "$GHITS" ] && FINDINGS+=$'[SECRET?] secret-named var assigned an opaque value (confirm not a real key):\n'"$GHITS"$'\n'

# A real .env file being committed (filename-level; .env.example/.sample/.template are safe).
ENVF="$(printf '%s\n' "$ADDED_FILES" | grep -E '(^|/)\.env($|\.[a-z]+$)' | grep -vE '\.(example|sample|template|dist|md|txt)$' | head -4 || true)"
[ -n "$ENVF" ] && FINDINGS+=$'[SECRET?] a real .env file is being committed (use .env.example for shareable keys):\n'"$ENVF"$'\n'

# --- Private identifiers: only meaningful when the destination is a PUBLIC repo. ---
IS_PUBLIC=0
if command -v gh &>/dev/null; then
    PRIV="$( (cd "$ROOT" && gh repo view --json isPrivate --jq '.isPrivate') 2>/dev/null || echo true )"
    [ "$PRIV" = "false" ] && IS_PUBLIC=1
fi

if [ "$IS_PUBLIC" -eq 1 ]; then
    # Load the install-local leak inventory as fixed strings. Comments and blank lines
    # carry no tokens; matching is case-insensitive.
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

    # Missing local policy must not pass silently. It surfaces once as a decision, while
    # universal credential and filename checks above remain active regardless.
    if [ -n "$DENY_TOKENS" ]; then
        PHITS="$(printf '%s\n' "$ADDED" | grep -iniF -f <(printf '%s' "$DENY_TOKENS") 2>/dev/null | head -8 || true)"
        [ -n "$PHITS" ] && PHITS="$(mask_hits "$PHITS")"
        [ -n "$PHITS" ] && FINDINGS+=$'[PRIVATE] private identifier from the local denylist in diff to a PUBLIC repo:\n'"$PHITS"$'\n'

        PMHITS="$(printf '%s\n' "$MESSAGES" | grep -iniF -f <(printf '%s' "$DENY_TOKENS") 2>/dev/null | head -6 || true)"
        [ -n "$PMHITS" ] && PMHITS="$(mask_msg_hits "$PMHITS")"
        [ -n "$PMHITS" ] && FINDINGS+=$'[PRIVATE] private identifier from the local denylist in an outgoing COMMIT MESSAGE to a PUBLIC repo (amend or rebase to fix):\n'"$PMHITS"$'\n'
    else
        DENYLIST_NOTICE='NOTICE (privacy): no denylist configured; private-identifier scanning is off.'
    fi
fi

# ============================================================================
# 2. DECISION: stop and surface once per HEAD (privacy findings and/or unreviewed work).
# ============================================================================

# Fresh verify marker = /verify passed this session with no edits after it.
VERIFY="$STATE_DIR/.verify-passed-$SID8"
EDITS="$STATE_DIR/.session-edits-$SID8"
reviewed=0
if [ -f "$VERIFY" ] && { [ ! -f "$EDITS" ] || [ ! "$EDITS" -nt "$VERIFY" ]; }; then
    reviewed=1
fi

# Clean diff, configured privacy scan, and already reviewed -> push through.
[ -z "$FINDINGS" ] && [ -z "$DENYLIST_NOTICE" ] && [ "$reviewed" -eq 1 ] && exit 0

# Surface once per HEAD: a re-push of the same commits is the decision -> allow.
# Include the canonical repository root in the marker key so one repo cannot inherit
# another repo's same-HEAD decision within the session.
HEAD_SHA="$(git rev-parse HEAD 2>/dev/null || echo none)"
ROOT_KEY="$(printf '%s' "$ROOT" | git hash-object --stdin 2>/dev/null || true)"
SURFACED="$STATE_DIR/.pushgate-surfaced-$SID8-$ROOT_KEY"
[ -f "$SURFACED" ] && [ "$(cat "$SURFACED" 2>/dev/null)" = "$HEAD_SHA" ] && exit 0
printf '%s' "$HEAD_SHA" > "$SURFACED" 2>/dev/null || true

REASON="unreviewed-surface"
{
    if [ -n "$FINDINGS" ]; then
        REASON="privacy-surface"
        echo "PAUSE (privacy): the diff you are about to push contains strings that look sensitive."
        echo "$FINDINGS"
        echo "Decide, then re-run the SAME push to proceed:"
        echo "  - Redact anything that is a real secret or private identifier (a new commit re-scans)."
        echo "  - If you have confirmed these are false positives, the re-push carries them through."
        [ "$reviewed" -eq 0 ] && echo
    fi
    if [ -n "$DENYLIST_NOTICE" ]; then
        [ -z "$FINDINGS" ] && REASON="privacy-config-surface"
        echo "$DENYLIST_NOTICE"
    fi
    if [ "$reviewed" -eq 0 ]; then
        echo "PAUSE (unreviewed push): these commits were not verified this session (no fresh .verify-passed marker)."
        echo "  - Run /verify or /review if this has not been reviewed and iterated."
        echo "  - Otherwise re-run the same push; the re-push is your decision and the gate allows it."
    fi
    echo "Pushing: $RANGE"
} >&2
emit_block "$REASON"
exit 2
