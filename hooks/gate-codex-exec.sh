#!/usr/bin/env bash
# gate-codex-exec.sh - PreToolUse(Bash) deny gate
# Denies bare `codex exec` calls and redirects to the lane wrappers (fast / strong)
# or the /codex-review skill, which encode the canonical flag set and handle quota
# fallback. See reference/codex-invocation.md and reference/model-delegation.md.
#
# Config: matcher "Bash" + per-hook filter `Bash(codex *)`. Input: stdin JSON.
# Deny: exit 2 + a human-readable reason on stderr (the PreToolUse deny signal).
# Fails OPEN (exit 0) on infrastructure errors unless the raw command still
# plausibly invokes the guarded tool and flags cannot be verified.
#
# Allows: `codex exec` invocations that carry the full sandbox flag set
# (--dangerously-bypass-approvals-and-sandbox + --skip-git-repo-check), the canonical
# form used by the /codex-review skill per reference/codex-invocation.md.
set -uo pipefail

# Fail open when jq is missing: an infra gap should warn, never block a tool call.
if ! command -v jq >/dev/null 2>&1; then
    echo "[gate-codex-exec] jq not found; allowing command unchecked." >&2
    exit 0
fi

INPUT="$(cat)"
COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"

# This gate is best-effort; the sandbox is the real boundary, and deeply
# obfuscated shell forms are out of scope when parsing is unavailable.
plausibly_invokes_codex_exec() {
    local command="$1"
    local codex_exec_re

    codex_exec_re='(^|[^[:alnum:]_/-])["'\'']?([^"'\''[:space:];|&()<>]+/)?codex["'\'']?[[:space:]]+["'\'']?exec($|[^[:alnum:]_-])'
    printf '%s\n' "$command" | grep -Eq "$codex_exec_re"
}

if ! command -v python3 >/dev/null 2>&1; then
    if plausibly_invokes_codex_exec "$COMMAND"; then
        echo "[gate-codex-exec] python3 not found; blocking plausible codex exec unchecked." >&2
        POLICY_STATUS="blocked"
    else
        echo "[gate-codex-exec] python3 not found; allowing command unchecked." >&2
        exit 0
    fi
else
# Act only on `codex exec`; leave fast/strong, codex review, codex login, etc. alone.
POLICY_STATUS="$(
    CODEX_GATE_COMMAND="$COMMAND" python3 - <<'PY'
import os
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


def has_active_backtick_substitution(command):
    quote = None
    word_start = True
    i = 0

    while i < len(command):
        char = command[i]

        if quote == "'":
            if char == quote:
                quote = None
            i += 1
            continue

        if char == "\\" and i + 1 < len(command):
            word_start = command[i + 1] == "\n"
            i += 2
            continue

        if quote == '"':
            if char == quote:
                quote = None
            elif char == "`":
                return True
            i += 1
            continue

        if char == "#" and word_start:
            while i < len(command) and command[i] != "\n":
                i += 1
            word_start = True
            continue

        if char in "'\"":
            quote = char
            word_start = False
        elif char == "`":
            return True
        else:
            word_start = char.isspace() or char in ";|&()<>"
        i += 1

    return False


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


def exec_flags(args):
    flags = set()
    for arg in args:
        if arg == "--":
            break
        if arg in {FLAG_APPROVALS, FLAG_REPO}:
            flags.add(arg)
    return flags


if has_active_backtick_substitution(os.environ.get("CODEX_GATE_COMMAND", "")):
    print("blocked")
    raise SystemExit

try:
    tokens = shell_tokens(os.environ.get("CODEX_GATE_COMMAND", ""))
except ValueError:
    print("parse_error")
    raise SystemExit

found = False
for command_words in simple_commands(tokens):
    argv = argv_words(command_words)
    for index, token in enumerate(argv[:-1]):
        if is_codex_word(token) and argv[index + 1] == "exec":
            found = True
            if {FLAG_APPROVALS, FLAG_REPO} - exec_flags(argv[index + 2 :]):
                print("blocked")
                raise SystemExit

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
