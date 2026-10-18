#!/usr/bin/env bash
# gate-gh-public-actions.sh - PreToolUse(Bash) gate on `gh` writes.
#
# ONE rule: a gh command must not publish a private identifier to a surface that is not proven
# private, nor a secret anywhere. Reads and commands with no publishable content leave before
# any lookup; `--help` is not special, because a BODY that contains it is not a flag. A target
# proven private is not a publication surface, so only secrets are scanned there -- the same
# rule gate-pre-push.sh applies to a push. EVERY target has to answer, not just the first.
#
# The command is TEXT here, not a parse tree. The threat model is an honest caller posting
# without looking, not one who wants around the gate; a shell analyzer bought precision on
# shapes nobody sent and cost 2,700 lines nobody could keep true (the operator, 2026-09-01).
#
# Input: stdin JSON with .tool_input.command and .cwd. Allow: exit 0. Refuse: exit 2 + stderr.
set -uo pipefail
GATE_STARTED_AT="${EPOCHREALTIME:-}"
HOOK_DIR=$(cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)

INPUT="$(cat)"
# Registration is broad: leave before any work on a command that does not mention gh. `-gh-`
# inside a path does not match -- `-` is part of the boundary class.
[[ "$INPUT" =~ (^|[^[:alnum:]_-])gh([^[:alnum:]_-]|$) ]] || exit 0

if [ -r "$HOOK_DIR/run-gates.sh" ]; then
    # Converts a stray exit into a refusal: PreToolUse runs the command on any status but 0/2.
    # shellcheck source=run-gates.sh
    . "$HOOK_DIR/run-gates.sh"
    gate_timing_begin gh-public-actions Bash "$INPUT" "$GATE_STARTED_AT"
fi

# HOME locates the token inventory; unset, `set -u` aborts the hook and it publishes unscanned.
if [ -z "${HOME:-}" ]; then
    HOME="$(getent passwd "$(id -u)" 2>/dev/null | cut -d: -f6)"
    export HOME
fi

refuse() {  # refuse <slug> <message> -- stderr first, then best-effort telemetry, then exit 2
    printf '%s\n' "$2" >&2
    local payload
    payload="$(jq -cn --arg r "$1" \
        '{hook:"gh-public-actions",tool:"Bash",reason:$r,decision:"deny"}' 2>/dev/null)"
    declare -F gate_payload_add_duration >/dev/null && gate_payload_add_duration payload
    bash "${GATE_TELEMETRY_EMITTER:-/dev/null}" hook_block "$SESSION_ID" "$payload" \
        2>/dev/null || true
    exit 2
}

SESSION_ID=unknown
[ -n "${HOME:-}" ] && [ -d "$HOME" ] || refuse gate-config \
    "BLOCKED (gate config): HOME is unset and could not be resolved, so this gate cannot reach its private-token inventory. It refuses rather than let a gh command publish unchecked."
command -v jq >/dev/null 2>&1 || refuse gate-config \
    "BLOCKED (gate config): jq is missing, so this gate cannot read the command it must judge."

EVENT=()
mapfile -d '' -t EVENT < <(
    printf '%s' "$INPUT" | /usr/bin/python3 -S "${BASH_SOURCE[0]%/*}/lib/privacy-event.py"
    printf '%s\0' "$?"
)
[ "${EVENT[0]:-}" = privacy-event-v2 ] && [[ "${EVENT[1]:-}" =~ ^(0|[1-9][0-9]{0,3})$ ]] \
    || refuse event-invalid "BLOCKED (privacy decision): the command event was not decoded."
TOKEN_COUNT="${EVENT[1]}"
[ "${#EVENT[@]}" -eq $((6 + 2 * TOKEN_COUNT)) ] && [ "${EVENT[-1]}" = 0 ] \
    || refuse event-invalid "BLOCKED (privacy decision): incomplete command event or tokenizer failure."
COMMAND="${EVENT[2]}"; CWD="${EVENT[3]}"; SESSION_ID="${EVENT[4]}"
WORDS=(); WORD_DYNAMIC=()
for ((i = 5; i < 5 + 2 * TOKEN_COUNT; i += 2)); do
    [[ "${EVENT[i + 1]}" =~ ^[0-3]$ ]] || refuse event-invalid "BLOCKED (privacy decision): invalid token metadata."
    WORDS+=("${EVENT[i]}"); WORD_DYNAMIC+=("$((EVENT[i + 1] & 1))")
done
[ -n "$COMMAND" ] || exit 0

# The generated finite policy uses only Bash builtins; registrations stay unchanged.
. "${BASH_SOURCE[0]%/*}/lib/privacy-decision.sh" || refuse decision-config \
    "BLOCKED (privacy decision): the generated policy helper could not be loaded."
declare -F privacy_plan privacy_target privacy_finish privacy_verdict >/dev/null || refuse decision-config \
    "BLOCKED (privacy decision): the generated policy helper is incomplete."

# the operator's explicit override, spelled in the command so it stays visible in the transcript.
# A LEADING env assignment only: as a substring it fired on any body that merely discussed the
# override, which turned publishable prose into a way to disable this gate (review, 2026-09-01).
if [[ "$COMMAND" =~ ^[[:space:]]*PRIVACY_ACK=1[[:space:]] ]]; then
    privacy_plan 1 0 0
    exit 0
fi

# --- Is this a gh WRITE? -------------------------------------------------------------------
# `gh` must be in COMMAND POSITION -- the start of the text or the far side of a shell operator,
# past env assignments and the usual wrappers -- so a command that merely QUOTES a gh write, a
# grep pattern or a jq fixture included, is not one. The verb chain then allows plain words
# between `gh` and the verb (`gh issue create`, `gh pr comment`) and breaks on a flag or a
# number, so `gh pr view 123` is not a write.
CMDPOS='(^|[;&|(){}`'$'\n'']|\$\()[[:space:]]*([A-Za-z_][A-Za-z0-9_]*=("[^"]*"|'"'"'[^'"'"']*'"'"'|[^[:space:]]*)[[:space:]]+)*((sudo|env|nice|time|exec|then|do|else|xargs)[[:space:]]+|timeout[[:space:]]+[0-9.]+[[:space:]]+)*'
VERBS='create|edit|comment|merge|review|close|reopen|delete|transfer|rename'
GH_INVOKE='gh[[:space:]]+((--repo(=|[[:space:]]+)[^[:space:]]+|-R([^[:space:]]+|[[:space:]]+[^[:space:]]+))[[:space:]]+)*'
IS_WRITE=0
[[ "$COMMAND" =~ ${CMDPOS}${GH_INVOKE}([a-z][a-z-]*[[:space:]]+)*($VERBS)([^[:alnum:]_-]|$) ]] && IS_WRITE=1
[[ "$COMMAND" =~ ${CMDPOS}${GH_INVOKE}release[[:space:]]+upload([^[:alnum:]_-]|$) ]] && IS_WRITE=1
# `gh api` carries text to GitHub whenever it has a method other than GET or any field flag.
# The flag list is an ALLOWLIST of read shapes turned inside out: the first denylist missed
# `-XPOST`, `-ftitle=t` and `-Fk=v`, so the value may be attached to the short flag.
IS_API=0
IS_GIST=0
[[ "$COMMAND" =~ ${CMDPOS}${GH_INVOKE}gist([^[:alnum:]_-]|$) ]] && IS_GIST=1
if [[ "$COMMAND" =~ ${CMDPOS}${GH_INVOKE}api([^[:alnum:]_-]|$) ]]; then
    IS_API=1
    [[ "$COMMAND" =~ (-X|--method)[[:space:]=]*(POST|PUT|PATCH|DELETE) ]] && IS_WRITE=1
    [[ "$COMMAND" =~ (^|[[:space:]])(-f|-F) ]] && IS_WRITE=1
    [[ "$COMMAND" =~ (^|[[:space:]])(--field|--raw-field|--input)([[:space:]=]|$) ]] && IS_WRITE=1
fi
[ "$IS_WRITE" -eq 1 ] || exit 0

# --- What would it publish? ----------------------------------------------------------------
# The command text itself, plus every file it names as content. `-F` is `--field` on `gh api`
# (`key=@file`) and `--body-file` everywhere else, so both spellings are read.
FILES=()
TEXTS=()
TARGETS=()
want_file() {
    local p="$1" required="${2:-0}"
    case "$p" in -|/dev/stdin) WANTS_STDIN=1; return ;; esac
    if [ "$required" -eq 1 ]; then
        case "$p" in *'$'*|*'`'*) refuse content-dynamic \
            "BLOCKED (privacy scan): use a literal absolute content-file path; expansions cannot be cleared." ;; esac
    fi
    case "$p" in '~') p="$HOME" ;; '~/'*) p="$HOME/${p#\~/}" ;; esac
    case "$p" in /*) ;; *) p="$BASE/$p" ;; esac
    if [ -f "$p" ] && [ -r "$p" ]; then FILES+=("$p")
    elif [ "$required" -eq 1 ]; then refuse content-unresolved \
        "BLOCKED (privacy scan): an explicit content file could not be resolved/read: $p"
    fi
    return 0
}
want_text() {
    [ "${1:-0}" = 0 ] || refuse content-dynamic \
        "BLOCKED (privacy scan): dynamic publication text cannot be cleared; use a literal body-file path."
    [ "$#" -lt 2 ] || TEXTS+=("$2")
    return 0
}
want_field() {
    want_text "$2"
    case "$1" in *=@*) want_file "${1#*=@}" 1 ;; *) want_text "$2" "$1" ;; esac
}
# Relative references resolve against `cd <dir>` when there is one: PreToolUse fires BEFORE the
# command, so for `cd <dir> && gh api -F q=@file` the reported cwd is still the session's, the
# file does not resolve, and the payload publishes unscanned (measured 2026-09-01, real corpus).
BASE="${CWD:-.}"
for i in "${!WORDS[@]}"; do
    [ "${WORDS[i]}" = cd ] || continue
    d="${WORDS[i + 1]:-}"
    case "$d" in '~') d="$HOME" ;; '~/'*) d="$HOME/${d#\~/}" ;; esac
    [ -d "$d" ] && BASE="$d"
done
NEXT=""; GIST=0; REL=0; WANTS_STDIN=0; REDIRECTED=0
for i in "${!WORDS[@]}"; do
    w="${WORDS[i]}"; DYNAMIC="${WORD_DYNAMIC[i]}"
    case "$NEXT" in
        file) NEXT=""; want_file "$w" 1; continue ;;
        redirect) NEXT=""; want_file "$w" 1; REDIRECTED=1; continue ;;
        field) NEXT=""; want_field "$w" "$DYNAMIC"; continue ;;
        text) NEXT=""; want_text "$DYNAMIC" "$w"; continue ;;
        repo) NEXT=""; [ -n "$w" ] && TARGETS+=("$w"); continue ;;
    esac
    case "$w" in
        --body-file|--input|--notes-file) NEXT=file ;;
        --field|-F) NEXT=field ;;
        --raw-field|-f|--body|--title|--notes|--description|-b|-t|-n|-d) NEXT=text ;;
        --repo|-R) NEXT=repo ;;
        --body-file=*|--input=*|--notes-file=*) want_file "${w#*=}" 1 ;;
        --field=*) want_field "${w#*=}" "$DYNAMIC" ;;
        --raw-field=*|--body=*|--title=*|--notes=*|--description=*) want_text "$DYNAMIC" "${w#*=}" ;;
        --repo=*) TARGETS+=("${w#*=}") ;;
        # Attached `-Rowner/repo`: the shape that read visibility off the cwd repo instead.
        -R?*) TARGETS+=("${w#-R}") ;;
        -F?*) want_field "${w#-?}" "$DYNAMIC" ;;
        -f?*) want_text "$DYNAMIC" "${w#-?}" ;;
        # A redirection is content: `--body-file - < notes.md` publishes what it names.
        '<') NEXT=redirect ;;
        '<'?*) refuse content-dynamic "BLOCKED (privacy scan): unsupported content redirection." ;;
        # Only a `gh gist` command has positional sources; the word in a body does not.
        gist) [ "${IS_GIST:-0}" -eq 1 ] && GIST=1 ;;
        release) REL=1 ;;
        create|upload) [ "$REL" -eq 1 ] && REL=2 ;;
        -*) ;;
        # Positionals: a gist source, or an asset of `release create|upload <tag> <files>`,
        # whose first positional is the tag. want_file drops a word that is not a file.
        *)  [ "$GIST" -eq 1 ] && want_file "$w"
            # `path#label` uploads `path` under a display label; the suffix is not the file.
            case "$REL" in 2) REL=3 ;; 3) want_file "${w%%#*}" ;; esac ;;
    esac
    # An api endpoint under `repos/<owner>/<repo>` names its target; nothing else in the
    # line does, and the cwd fallback answered for a different repo entirely.
    if [ "$IS_API" -eq 1 ]; then
        case "$w" in
            repos/*/*|/repos/*/*)
                t="${w#/}"; t="${t#repos/}"; r="${t#*/}"
                TARGETS+=("${t%%/*}/${r%%/*}") ;;
        esac
    fi
done
[ -z "$NEXT" ] || refuse content-unresolved "BLOCKED (privacy scan): a content argument is incomplete."
[ "$WANTS_STDIN" -eq 0 ] || [ "$REDIRECTED" -eq 1 ] || refuse content-unresolved \
    "BLOCKED (privacy scan): publication stdin cannot be cleared; use a literal content-file path."

SCANNER="${PRIVACY_SCANNER:-$HOOK_DIR/lib/privacy-scan.py}"
[ -r "$SCANNER" ] || refuse scanner-missing \
    "BLOCKED (gate config): the privacy scanner at $SCANNER is missing, so the publishable content of this gh command was not checked."
# The scanner reads each file completely within its existing timeout; >1 MiB is an
# incomplete scan/refusal, never a clean prefix. No file bytes enter shell variables.
content() {
    # The home path is a private literal AND the prefix of every local path here, so scanning
    # the command line raw refused 51 of 1385 real gh commands for naming a file. Normalised
    # HERE only: file CONTENTS are scanned raw, so the path still refuses inside a body. Cost
    # of the trade: an inline body that spells the home path out passes.
    printf '%s\n' "${COMMAND//"$HOME"/\~}"
    local text
    for text in ${TEXTS+"${TEXTS[@]}"}; do printf '%s\n' "$text"; done
    return 0
}

# Visibility decides the class, not whether to scan: secrets refuse on any target, because a
# private repo is still the wrong place for a live key. EVERY target the line writes to has to
# answer `private` before the identifier scan is skipped -- a chain that writes to a private
# repo and then to a public one publishes to the public one. A failed lookup, a gist, and an
# api endpoint that names no repo are all "not proven private", not "private".
PROVEN_PRIVATE=1
if [ "$IS_GIST" -eq 1 ] || { [ "$IS_API" -eq 1 ] && [ "${#TARGETS[@]}" -eq 0 ]; }; then
    privacy_target "$PROVEN_PRIVATE" 0
elif [ "${#TARGETS[@]}" -eq 0 ]; then
    # A plain verb with no named target writes to the repo the command runs in.
    VIS="$(cd "$BASE" 2>/dev/null && timeout 1.2 gh repo view --json visibility -q .visibility 2>/dev/null)"
    VIS_RC=$?
    TARGET_PRIVATE=0; [ "$VIS_RC" -eq 0 ] && [ "${VIS,,}" = private ] && TARGET_PRIVATE=1
    privacy_target "$PROVEN_PRIVATE" "$TARGET_PRIVATE"
else
    # One 1200 ms budget SHARED by the named targets: a line naming several must not multiply
    # the 3 s this gate declares. Past six names it stops asking and scans everything.
    [ "${#TARGETS[@]}" -le 6 ] || privacy_target "$PROVEN_PRIVATE" 0
    EACH=$((1200 / (${#TARGETS[@]} > 6 ? 6 : ${#TARGETS[@]})))
    EACH="$(printf '%d.%03d' $((EACH / 1000)) $((EACH % 1000)))"
    for t in "${TARGETS[@]}"; do
        [ "$PROVEN_PRIVATE" -eq 1 ] || break
        VIS="$(timeout "$EACH" gh repo view "$t" --json visibility -q .visibility 2>/dev/null)"
        VIS_RC=$?
        TARGET_PRIVATE=0; [ "$VIS_RC" -eq 0 ] && [ "${VIS,,}" = private ] && TARGET_PRIVATE=1
        privacy_target "$PROVEN_PRIVATE" "$TARGET_PRIVATE"
    done
fi
privacy_plan 0 1 "$PROVEN_PRIVATE"
WHAT="a private identifier, to a target that is not proven private (matchers: the tokens in \$HOME/.claude/config/private-tokens.txt plus the re shape classes in that file)"
if [ "$PROVEN_PRIVATE" -eq 1 ]; then
    WHAT="what looks like a live credential (every target is private, so private identifiers were not scanned for)"
fi

SCAN_FILES=()
for f in ${FILES+"${FILES[@]}"}; do SCAN_FILES+=(--file "$f"); done
FINDINGS="$(content | timeout 1.5 /usr/bin/python3 -S "$SCANNER" --classes "$CLASSES" --evidence "${SCAN_FILES[@]}" 2>&1)"; RC=$?
privacy_finish "$RC" "$FINDINGS"
FINDINGS="$SCAN_FINDINGS"
[ "$PRIVACY_VERDICT" = finding ] && refuse privacy \
    "BLOCKED (privacy): this gh command would publish $WHAT.
$FINDINGS
Fix the content, or -- once the operator has ruled -- re-run the same command with PRIVACY_ACK=1 in front of it."
[ "$PRIVACY_VERDICT" = allow ] || refuse scan-failed \
    "BLOCKED (privacy scan): the scan exited $RC instead of finishing, so the publishable content of this gh command was NOT cleared. $FINDINGS"
exit 0
