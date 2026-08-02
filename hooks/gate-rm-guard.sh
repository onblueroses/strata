#!/usr/bin/env bash
# gate-rm-guard.sh - PreToolUse(Bash) blocking hook
# Threat model: catches accidental destructive commands and agent slips that match the bounded shell forms below.
# It is not a security boundary against an adversary or compromised agent; Python or Perl
# one-liners, script files, Makefile targets, and unrecognized shell forms can bypass it.
#
# Blocks destructive operations on protected or ambiguous targets. Allows an operation only
# when every target is a known temp or build artifact: strict children of /tmp or /var/tmp,
# /dev/null, *.pyc, *.o, *.class, __pycache__, node_modules, .cache, build, dist, or target.
#
# Trigger = a destructive command in command position, including sudo/xargs/timeout-style
# wrappers, git rm, find -exec rm, find -delete, sh -c, eval, and backtick substitution.
# Flag, argument, and prose occurrences such as docker run --rm do not count as commands.
# Same-command literal assignments can resolve a target; dynamic or ambiguous expansion blocks.
# Recursion is capped at depth 3 by the acceptance requirement. Empty, malformed, or
# command-free input passes silently; missing analyzer dependencies use the fallback below.
# Config: matcher "Bash". Input: hook JSON on stdin. Deny: exit 2 + stderr.
set -uo pipefail

INPUT=""
IFS= read -r -d '' INPUT || true

# No input means there is no command to judge. This must stay silent because the hook runs on
# every Bash tool call and has no grounds to deny a command it cannot see.
if [[ -z $INPUT ]]; then
    exit 0
fi

raw_input_looks_destructive() {
    local raw_input="$1"

    if [[ $raw_input =~ (^|[^[:alnum:]_])(rm|shred|truncate|unlink|rmdir)([^[:alnum:]_]|$) ]]; then
        return 0
    fi
    if [[ $raw_input =~ (^|[^[:alnum:]_])find([^[:alnum:]_]|$) && $raw_input == *"-delete"* ]]; then
        return 0
    fi
    return 1
}

fallback_for_missing_dependency() {
    local dependency="$1"

    # Without the parser the guard cannot distinguish `rm -rf ~/project` from
    # `echo "rm -rf"`. The fallback therefore blocks either string and names the missing
    # dependency, while raw input with no plausible destructive form passes silently.
    if raw_input_looks_destructive "$INPUT"; then
        printf "gate-rm-guard: BLOCKED because required dependency '%s' is unavailable; the conservative raw-input fallback found a destructive command string. Install the dependency to restore shell-aware analysis.\n" \
            "$dependency" >&2
        exit 2
    fi
    exit 0
}

if ! command -v jq >/dev/null 2>&1; then
    fallback_for_missing_dependency jq
fi

if ! COMMAND="$(
    printf '%s' "$INPUT" \
        | jq -er 'if (.tool_input.command | type) == "string" then .tool_input.command else error("missing command") end' \
            2>/dev/null
)"; then
    exit 0
fi

if ! command -v python3 >/dev/null 2>&1; then
    fallback_for_missing_dependency python3
fi

trash_dir() {
    if [[ -n ${STRATA_TRASH_DIR:-} ]]; then
        printf '%s' "$STRATA_TRASH_DIR"
    elif [[ -n ${HOME:-} ]]; then
        printf '%s/.trash-agent' "$HOME"
    else
        printf '%s' '$HOME/.trash-agent'
    fi
}

deny() {
    local reason="$1"
    local recovery_dir
    recovery_dir="$(trash_dir)"

    printf 'gate-rm-guard: BLOCKED: %s\n' "$reason" >&2
    printf 'Move recoverable paths to the configured trash directory instead:\n' >&2
    printf '  mv -- <path> "%s/"\n' "$recovery_dir" >&2
    printf 'Set STRATA_TRASH_DIR to change this location.\n' >&2
    exit 2
}

# Avoid starting Python for commands with no deletion-capable word or ANSI-C quoted text.
# ANSI-C text may hide such a word behind an escape, so the recursive parser must inspect it.
# A match only starts analysis; the parser decides whether it is an operation or inert data.
if [[ ! $COMMAND =~ (^|[^[:alnum:]_])(rm|find|shred|truncate|unlink|rmdir)([^[:alnum:]_]|$) \
    && $COMMAND != *"\$'"* ]]; then
    exit 0
fi

# Shell-aware command-position and per-target safety analysis. It prints exactly one verdict:
#   OK   - no destructive invocation in command position
#   SAFE - every destructive invocation has only known-safe targets
#   RM   - at least one target is protected, unknown, or ambiguously parsed
if ! VERDICT="$(RMGUARD_CMD="$COMMAND" python3 - <<'PYEOF'
import os
import re
import shlex

MAX_SCAN_DEPTH = 3  # Acceptance requirement: nested eval and shell recursion is bounded here.
WRAPPERS = {
    "sudo",
    "doas",
    "command",
    "exec",
    "env",
    "nice",
    "ionice",
    "nohup",
    "stdbuf",
    "time",
    "builtin",
    "timeout",
    "xargs",
    "setsid",
    "chronic",
}
WRAPPER_OPTIONS_WITH_VALUE = {
    "sudo": {
        "-u", "--user", "-g", "--group", "-h", "--host", "-p", "--prompt",
        "-C", "--close-from", "-T", "--command-timeout", "-R", "--chroot",
        "-D", "--chdir",
    },
    "doas": {"-C", "-u"},
    "exec": {"-a"},
    "env": {
        "-u", "--unset", "-C", "--chdir", "-S", "--split-string", "--argv0",
    },
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
KEYWORDS = {"do", "then", "else", "elif", "if", "while", "until", "!"}
SHELLS = {"bash", "sh", "zsh", "dash", "ksh"}
DESTRUCTIVE = {"shred", "truncate", "unlink", "rmdir"}
DESTRUCTIVE_OPTIONS_WITH_VALUE = {
    "shred": {"-n", "--iterations", "-s", "--size", "--random-source"},
    "truncate": {"-r", "--reference", "-s", "--size"},
}
GIT_OPTIONS_WITH_VALUE = {
    "-C", "-c", "--git-dir", "--work-tree", "--namespace", "--super-prefix",
    "--config-env",
}
FIND_EXEC_TERMINATOR = "__STRATA_FIND_EXEC_TERMINATOR__"

# Group 2 records decorated assignments such as T[0]= and T+=. Literal [0] is scalar-
# equivalent; every other subscript or append remains unresolved.
ASSIGN = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)((?:\[[^\]]*\])?\+?)=")
DURATION = re.compile(r"^\d+(?:\.\d+)?[smhd]?$")
REDIRECT = re.compile(r"^\d*[<>]{1,2}(?:&\d*)?$")
SEPARATOR_CHARS = set(";|&(){}")
SAFE_DIRS = {"__pycache__", "node_modules", ".cache", "build", "dist", "target"}
SAFE_SUFFIXES = (".pyc", ".o", ".class")
SAFE_ABSOLUTE_ROOTS = ("/tmp", "/var/tmp")
ANSI_C_UNRESOLVED = "__STRATA_ANSI_C_UNRESOLVED__"


def command_basename(token):
    return token.rsplit("/", 1)[-1]


def normalize_ansi_c_quotes(command):
    """Make literal ANSI-C strings visible to shlex; preserve escapes as unresolved."""
    output = []
    index = 0
    quote = None

    while index < len(command):
        character = command[index]

        if quote == "'":
            output.append(character)
            if character == "'":
                quote = None
            index += 1
            continue

        if quote == '"':
            output.append(character)
            if character == "\\" and index + 1 < len(command):
                output.append(command[index + 1])
                index += 2
                continue
            if character == '"':
                quote = None
            index += 1
            continue

        if character == "\\" and index + 1 < len(command):
            output.extend(command[index : index + 2])
            index += 2
            continue

        if command.startswith("$'", index):
            cursor = index + 2
            content = []
            unresolved = False
            while cursor < len(command):
                ansi_character = command[cursor]
                if ansi_character == "\\":
                    unresolved = True
                    if cursor + 1 >= len(command):
                        return None
                    cursor += 2
                    continue
                if ansi_character == "'":
                    break
                content.append(ansi_character)
                cursor += 1
            else:
                return None

            replacement = ANSI_C_UNRESOLVED if unresolved else "".join(content)
            output.append(shlex.quote(replacement))
            index = cursor + 1
            continue

        if character in ("'", '"'):
            quote = character
        output.append(character)
        index += 1

    return "".join(output)


def is_rm(token):
    return command_basename(token) == "rm"


def is_separator(token):
    # Process substitutions open a command context; ordinary shell separators split one.
    # Find's conventional {} placeholder is an operand even though both characters are
    # shell punctuation to shlex.
    return token in ("<(", ">(") or (
        token != "{}"
        and token != ""
        and all(character in SEPARATOR_CHARS for character in token)
    )


# --- literal same-command variable resolution ---------------------------------
# A variable target is unknown in general. A literal value assigned unconditionally at this
# scan level is knowable; conditional, nested, deferred, aliased, or mutated values are not.
VARIABLE_REFERENCE = re.compile(
    r"\$\{([A-Za-z_][A-Za-z0-9_]*)(?:\[([^\]]*)\])?\}"
    r"|\$([A-Za-z_][A-Za-z0-9_]*)"
)
EXPANSION_CHARS = set("$`\\*?[]{}")
CONTROL_OPEN = {"if", "while", "until", "for", "case", "select", "function"}
CONTROL_CLOSE = {"fi", "done", "esac"}
MUTATORS = {
    "unset",
    "read",
    "let",
    "declare",
    "typeset",
    "export",
    "local",
    "mapfile",
    "readarray",
    "getopts",
    "printf",
}
WIPERS = {"eval", "source", ".", "trap", "alias", "unalias", "shopt"}
NAMEREF = {"declare", "typeset", "local"}
NAMEREF_FLAG = re.compile(r"^-[A-Za-z]*n")
NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SUBSCRIPTED_NAME = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)\[([^\]]*)\]$")
SEPARATORS_BEFORE_ASSIGNMENT = ("", ";", "&")
SEPARATORS_AFTER_ASSIGNMENT = ("", ";", "&&", "||")


def literal_value(value):
    """Return a literal assignment value, or None when the shell would expand it."""
    if not value:
        return None
    if any(character in EXPANSION_CHARS or character.isspace() for character in value):
        return None
    return value


def normalized_subscripted_target(token):
    """Return (base name, subscript) for a subscripted variable target."""
    match = SUBSCRIPTED_NAME.match(token)
    if not match:
        return None
    return match.group(1), match.group(2)


READ_OPTIONS_WITH_VALUE = {"-d", "-i", "-n", "-N", "-p", "-t", "-u"}
MAPFILE_OPTIONS_WITH_VALUE = {"-d", "-n", "-O", "-s", "-u", "-C", "-c"}


def read_target_indexes(segment):
    """Return the indexes Bash read treats as assignment targets."""
    targets = []
    index = 1
    while index < len(segment):
        token = segment[index]
        if token in ("<", "<<", "<<<", "<&"):
            break
        if token == "--":
            index += 1
            continue
        if token == "-a" and index + 1 < len(segment):
            targets.append(index + 1)
            index += 2
            continue
        if token in READ_OPTIONS_WITH_VALUE:
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        targets.append(index)
        index += 1
    return targets


def mapfile_target_indexes(segment):
    """Return the optional array-name operand written by mapfile/readarray."""
    targets = []
    index = 1
    while index < len(segment):
        token = segment[index]
        if token in ("<", "<<", "<<<", "<&"):
            break
        if token == "--":
            index += 1
            continue
        if token in MAPFILE_OPTIONS_WITH_VALUE:
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        targets.append(index)
        index += 1
    return targets[-1:]


def is_subscripted_mutator_target(segment, token_index):
    """Whether a subscript-shaped token names state written by this mutator."""
    head = segment[0]
    if head == "read":
        return token_index in read_target_indexes(segment)
    if head == "printf":
        return token_index > 1 and segment[token_index - 1] == "-v"
    if head in {"mapfile", "readarray"}:
        return token_index in mapfile_target_indexes(segment)
    if head in {"declare", "typeset", "local", "export", "unset"}:
        return True
    return False


def literal_subscript_read_value(segment, target_index, subscript):
    """Resolve the narrow scalar-equivalent `read T[0] <<< literal` form."""
    if target_index != 1 or subscript != "0" or read_target_indexes(segment) != [target_index]:
        return None
    if target_index + 2 >= len(segment) or segment[target_index + 1] != "<<<":
        return None
    if target_index + 3 != len(segment):
        return None
    return literal_value(segment[target_index + 2])


def assignment_states(segments, raw_command):
    """Return names certainly holding literal values before each segment runs."""
    blank = [{} for _ in segments]
    if any(token.startswith("IFS=") for _, segment in segments for token in segment):
        return blank

    # shlex erases the distinction between T=~/x and T="~/x". The quoted form assigns
    # a literal tilde, so raw text is used only to withhold resolution for that name.
    quoted_tildes = {
        match.group(1)
        for match in re.finditer(r"([A-Za-z_][A-Za-z0-9_]*)=[\"']~", raw_command)
    }
    values = {}
    poisoned = set(quoted_tildes)
    states = []
    nesting_depth = 0
    control_depth = 0
    resolution_wiped = False

    for index, (separator, segment) in enumerate(segments):
        nesting_depth += sum(character in "({" for character in separator)
        nesting_depth -= sum(character in ")}" for character in separator)
        if nesting_depth < 0:
            return blank

        nested = nesting_depth > 0 or control_depth > 0
        states.append({} if nested or resolution_wiped else dict(values))

        if segment[0] in CONTROL_OPEN:
            control_depth += 1
        elif segment[0] in CONTROL_CLOSE:
            control_depth = max(control_depth - 1, 0)

        mutator = segment[0] in MUTATORS
        spaced_options = all(
            len(token) == 2 for token in segment[1:] if token.startswith("-")
        )
        if (
            segment[0] in WIPERS
            or (mutator and not spaced_options)
            or (
                segment[0] in NAMEREF
                and any(NAMEREF_FLAG.match(token) for token in segment[1:])
            )
        ):
            resolution_wiped = True
            values.clear()
        elif mutator:
            for token_index, token in enumerate(segment[1:], start=1):
                if NAME.match(token):
                    poisoned.add(token)
                    values.pop(token, None)
                    continue
                normalized = normalized_subscripted_target(token)
                if normalized and is_subscripted_mutator_target(segment, token_index):
                    name, subscript = normalized
                    read_value = (
                        literal_subscript_read_value(segment, token_index, subscript)
                        if segment[0] == "read"
                        else None
                    )
                    if read_value is not None and name not in poisoned:
                        values[name] = read_value
                    else:
                        poisoned.add(name)
                        values.pop(name, None)

        assignments = [token for token in segment if ASSIGN.match(token)]
        if not assignments:
            continue

        next_separator = segments[index + 1][0] if index + 1 < len(segments) else ""
        eligible = (
            not nested
            and not resolution_wiped
            and len(assignments) == len(segment)
            and separator in SEPARATORS_BEFORE_ASSIGNMENT
            and next_separator in SEPARATORS_AFTER_ASSIGNMENT
        )
        for token in assignments:
            match = ASSIGN.match(token)
            name, decorated = match.group(1), match.group(2)
            scalar_equivalent = decorated in ("", "[0]")
            value = literal_value(token[match.end() :]) if eligible and scalar_equivalent else None
            if value is None or name in poisoned:
                poisoned.add(name)
                values.pop(name, None)
            else:
                values[name] = value

    return states


def resolve(token, assignments):
    """Substitute known literals; return None when any expansion remains unknown."""
    output = []
    last = 0
    for match in VARIABLE_REFERENCE.finditer(token):
        braced_name, subscript, plain_name = match.groups()
        if subscript is not None and subscript != "0":
            return None
        name = braced_name or plain_name
        if name not in assignments:
            return None
        output.append(token[last : match.start()])
        output.append(assignments[name])
        last = match.end()
    output.append(token[last:])
    result = "".join(output)
    return None if "$" in result or "`" in result else result


def known_safe(path):
    normalized = os.path.normpath(path)
    raw_parts = [part for part in path.split("/") if part]
    parts = [part for part in normalized.split("/") if part]
    if not path or ".." in raw_parts:
        return False
    return (
        normalized == "/dev/null"
        or any(normalized.startswith(root + "/") for root in SAFE_ABSOLUTE_ROOTS)
        or os.path.basename(normalized).endswith(SAFE_SUFFIXES)
        or any(part in SAFE_DIRS for part in parts)
    )


def safe_target(token, assignments):
    resolved = resolve(token, assignments)
    if resolved is None:
        return False
    return known_safe(resolved)


def collect_targets(segment, start):
    """Collect operands, excluding options and redirection syntax."""
    targets = []
    index = start
    options_finished = False
    while index < len(segment):
        token = segment[index]
        if REDIRECT.match(token):
            index += 2
            continue
        if token.isdigit() and index + 1 < len(segment) and REDIRECT.match(segment[index + 1]):
            index += 3
            continue
        if not options_finished and token == "--":
            options_finished = True
            index += 1
            continue
        if not options_finished and token.startswith("-"):
            index += 1
            continue
        options_finished = True
        targets.append(token)
        index += 1
    return targets


def strip_inert_backticks(command):
    """Remove single-quoted spans and escaped characters before scanning backticks."""
    output = []
    index = 0
    in_single_quote = False
    while index < len(command):
        character = command[index]
        if in_single_quote:
            in_single_quote = character != "'"
            index += 1
            continue
        if character == "'":
            in_single_quote = True
            index += 1
            continue
        if character == "\\" and index + 1 < len(command):
            index += 2
            continue
        output.append(character)
        index += 1
    return "".join(output)


HEREDOC = re.compile(
    r"(?<![<>])<<(?!<)(-?)\s*(?:'([^']+)'|\"([^\"]+)\"|([^\s;|&<>()]+))"
)


def strip_heredocs(command):
    """Remove heredoc bodies because their contents are data, not shell operations."""
    output = []
    lines = command.split("\n")
    index = 0
    while index < len(lines):
        line = lines[index]
        output.append(line)
        pending = [
            (match.group(1) == "-", match.group(2) or match.group(3) or match.group(4))
            for match in HEREDOC.finditer(line)
        ]
        index += 1
        for strip_tabs, delimiter in pending:
            found_delimiter = False
            while index < len(lines):
                body_line = lines[index]
                index += 1
                comparable = body_line.lstrip("\t") if strip_tabs else body_line
                if comparable == delimiter:
                    found_delimiter = True
                    break
            if not found_delimiter:
                raise ValueError("unterminated heredoc")
    return "\n".join(output)


def destructive_targets(segment, start, kind):
    """Return operands for destructive verbs, excluding known option values."""
    targets = []
    index = start
    options_with_value = DESTRUCTIVE_OPTIONS_WITH_VALUE.get(kind, set())
    while index < len(segment):
        token = segment[index]
        if token in options_with_value:
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        targets.append(token)
        index += 1
    return targets


def find_roots(segment, command_index):
    """Return Find starting points and whether its traversal mode is safe to infer."""
    roots = []
    index = command_index + 1
    follows_symlinks = False
    while index < len(segment):
        token = segment[index]
        if token in ("-H", "-L"):
            follows_symlinks = True
            index += 1
            continue
        if token == "-P":
            index += 1
            continue
        if token == "-D":
            index += 2
            continue
        if token.startswith("-O"):
            index += 1
            continue
        if token.startswith("-") or token in ("!", "("):
            break
        roots.append(token)
        index += 1
    return roots or ["."], not follows_symlinks


def skip_wrapper_arguments(segment, index, wrapper):
    """Return the wrapped-command index and command strings embedded in options."""
    options_with_value = WRAPPER_OPTIONS_WITH_VALUE.get(wrapper, set())
    embedded_commands = []
    while index < len(segment):
        token = segment[index]
        if token == "--":
            index += 1
            break
        if token in NO_EXEC_WRAPPER_OPTIONS:
            return len(segment), embedded_commands
        if wrapper == "command" and token in COMMAND_INSPECTION_OPTIONS:
            return len(segment), embedded_commands
        if not token.startswith("-") or token == "-":
            break
        if wrapper == "env" and token in ("-S", "--split-string"):
            if index + 1 < len(segment):
                embedded_commands.append(segment[index + 1])
            index += 2
            continue
        if wrapper == "env" and token.startswith("--split-string="):
            embedded_commands.append(token.split("=", 1)[1])
            index += 1
            continue
        if wrapper == "env" and token.startswith("-S") and token != "-S":
            embedded_commands.append(token[2:])
            index += 1
            continue
        if token in options_with_value:
            index += 2
        else:
            index += 1

    if wrapper == "timeout" and index < len(segment) and DURATION.match(segment[index]):
        index += 1
    if wrapper == "env":
        while index < len(segment) and ASSIGN.match(segment[index]):
            index += 1
    return index, embedded_commands


def git_rm_targets(segment, command_index):
    """Return git-rm targets, or None when Git is invoking another subcommand."""
    index = command_index + 1
    while index < len(segment):
        token = segment[index]
        if token == "--":
            index += 1
            break
        if token in NO_EXEC_WRAPPER_OPTIONS:
            return None
        if not token.startswith("-") or token == "-":
            break
        if token in GIT_OPTIONS_WITH_VALUE:
            index += 2
        else:
            index += 1

    if index >= len(segment) or segment[index] != "rm":
        return None
    return collect_targets(segment, index + 1)


def scan(command, depth=0, placeholder_safe=None):
    """Return one boolean per destructive invocation: True means every target is safe."""
    if depth > MAX_SCAN_DEPTH:
        return [False]

    found = []
    command = strip_heredocs(command)
    command = normalize_ansi_c_quotes(command)
    if command is None:
        return [False]

    # shlex does not segment legacy backtick substitutions, so recursively scan every live
    # pair. Results are merged with the outer parse so one safe substitution cannot mask one.
    live_backticks = strip_inert_backticks(command)
    for match in re.finditer(r"`([^`]*)`", live_backticks):
        found.extend(scan(match.group(1), depth + 1, placeholder_safe))

    lex_command = command.replace("\\;", f" {FIND_EXEC_TERMINATOR} ")
    lexer = shlex.shlex(lex_command.replace("\n", ";"), posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens = list(lexer)

    segments = []
    current = []
    separator = ""
    for token in tokens:
        if is_separator(token):
            if current:
                segments.append((separator, current))
                current = []
                separator = token
            else:
                separator += token
        else:
            current.append(token)
    if current:
        segments.append((separator, current))

    states = assignment_states(segments, command)
    for segment_index, (_, segment) in enumerate(segments):
        assignments = states[segment_index]

        def target_is_safe(target):
            if target == "{}" and placeholder_safe is not None:
                return placeholder_safe
            return safe_target(target, assignments)

        index = 0
        while index < len(segment):
            token = segment[index]
            if token in KEYWORDS or ASSIGN.match(token) or token.startswith("$") or token.isdigit():
                index += 1
                continue
            if REDIRECT.match(token):
                index += 2
                continue
            wrapper = command_basename(token)
            if wrapper in WRAPPERS:
                index, embedded_commands = skip_wrapper_arguments(segment, index + 1, wrapper)
                for embedded_command in embedded_commands:
                    found.extend(scan(embedded_command, depth + 1, placeholder_safe))
                continue
            break

        if index >= len(segment):
            continue

        head = command_basename(segment[index])
        if head == "rm":
            targets = collect_targets(segment, index + 1)
            found.append(bool(targets) and all(target_is_safe(target) for target in targets))
            continue

        if head == "git":
            targets = git_rm_targets(segment, index)
            if targets is not None:
                found.append(
                    bool(targets)
                    and all(target_is_safe(target) for target in targets)
                )
            continue

        if head == "find":
            roots, traversal_is_safe = find_roots(segment, index)
            roots_are_safe = traversal_is_safe and all(
                safe_target(root, assignments) for root in roots
            )
            if "-delete" in segment[index + 1 :]:
                found.append(roots_are_safe)

            for exec_index in range(index + 1, len(segment) - 1):
                if segment[exec_index] not in ("-exec", "-execdir"):
                    continue
                command_end = exec_index + 1
                while (
                    command_end < len(segment)
                    and segment[command_end] not in (FIND_EXEC_TERMINATOR, "+")
                ):
                    command_end += 1
                exec_command = segment[exec_index + 1 : command_end]
                if exec_command:
                    found.extend(
                        scan(shlex.join(exec_command), depth + 1, roots_are_safe)
                    )
            continue

        if head in DESTRUCTIVE:
            targets = destructive_targets(segment, index + 1, head)
            found.append(
                bool(targets) and all(target_is_safe(target) for target in targets)
            )
            continue

        if head in SHELLS:
            for option_index in range(index + 1, len(segment) - 1):
                if segment[option_index] == "-c":
                    nested_command = segment[option_index + 1]
                    if ANSI_C_UNRESOLVED in nested_command:
                        found.append(False)
                    else:
                        found.extend(scan(nested_command, depth + 1, placeholder_safe))
                    break

        if head == "eval" and segment[index + 1 :]:
            # eval concatenates operands before execution, so quoted and unquoted forms agree.
            nested_command = " ".join(segment[index + 1 :])
            if ANSI_C_UNRESOLVED in nested_command:
                found.append(False)
            else:
                found.extend(scan(nested_command, depth + 1, placeholder_safe))

    return found


try:
    results = scan(os.environ.get("RMGUARD_CMD", ""))
    if not results:
        print("OK")
    elif all(results):
        print("SAFE")
    else:
        print("RM")
except Exception:
    print("RM")
PYEOF
)"; then
    VERDICT="RM"
fi

case "$VERDICT" in
    OK | SAFE)
        exit 0
        ;;
    RM)
        deny 'the command contains a destructive operation with a protected or ambiguous target.'
        ;;
    *)
        deny 'the command analyzer returned an invalid verdict.'
        ;;
esac
