#!/usr/bin/env bash
# gate-pre-push.sh - PreToolUse(Bash) gate on `git push`.
#
# ONE rule: the commits a push would send must not carry a secret, and must not carry a
# private identifier to a remote that is not proven private. Nothing else is checked; the
# review gate and the surface-once markers were retired on 2026-09-01 (the operator).
#
# The command is TEXT here, not a parse tree: one command-position regex, no shell analyzer.
# A shape it reads wrongly costs a scan of a range that is normally empty, and then passes.
#
# Every git call is bounded, a stall REFUSES, and the gate holds ONE 17 s deadline of its own:
# PreToolUse runs the command on any status but 0/2, so an overrun of the declared 20 s
# budget pushes unscanned. Each call takes min(its bound, what is left of the deadline).
#
# Input: stdin JSON with .tool_input.command and .cwd. Allow: exit 0. Refuse: exit 2 + stderr.
set -uo pipefail
GATE_STARTED_AT="${EPOCHREALTIME:-}"
HOOK_DIR=$(cd "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)

INPUT="$(cat)"
# Both words must appear for PUSH_RE below to match, so this cannot hide a push; it keeps a
# command that merely fails to tokenize from being refused when it pushes nothing (2026-09-30).
[[ "$INPUT" =~ (^|[^[:alnum:]_-])git([^[:alnum:]_-]|$) ]] || exit 0
[[ "$INPUT" =~ (^|[^[:alnum:]_-])push([^[:alnum:]_-]|$) ]] || exit 0

if [ -r "$HOOK_DIR/run-gates.sh" ]; then
    # shellcheck source=run-gates.sh
    . "$HOOK_DIR/run-gates.sh"
    gate_timing_begin pre-push Bash "$INPUT" "$GATE_STARTED_AT"
fi
if [ -z "${HOME:-}" ]; then
    HOME="$(getent passwd "$(id -u)" 2>/dev/null | cut -d: -f6)"
    export HOME
fi

SESSION_ID=unknown
refuse() {  # refuse <slug> <message> -- stderr first, then best-effort telemetry, then exit 2
    printf '%s\n' "$2" >&2
    local payload
    payload="$(jq -cn --arg r "$1" \
        '{hook:"pre-push",tool:"Bash",reason:$r,decision:"deny"}' 2>/dev/null)"
    declare -F gate_payload_add_duration >/dev/null && gate_payload_add_duration payload
    bash "${GATE_TELEMETRY_EMITTER:-/dev/null}" hook_block "$SESSION_ID" "$payload" \
        2>/dev/null || true
    exit 2
}
[ -n "${HOME:-}" ] && [ -d "$HOME" ] || refuse gate-config \
    "BLOCKED (gate config): HOME is unset and could not be resolved, so this gate cannot reach its private-token inventory. It refuses rather than let a push go unscanned."
# Every tool this gate needs, named before it is used: a missing `timeout` came back through
# `g()` as a git verdict and read as "not a repository" (review, 2026-09-01).
for DEP in timeout jq git /usr/bin/python3; do
    command -v "$DEP" >/dev/null 2>&1 || refuse gate-config \
        "BLOCKED (gate config): $DEP is missing, so this gate cannot scan the push it must judge."
done

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
WORDS=(); WORD_DYNAMIC=(); WORD_OPERATOR=()
for ((i = 5; i < 5 + 2 * TOKEN_COUNT; i += 2)); do
    [[ "${EVENT[i + 1]}" =~ ^[0-3]$ ]] || refuse event-invalid "BLOCKED (privacy decision): invalid token metadata."
    WORDS+=("${EVENT[i]}"); WORD_DYNAMIC+=("$((EVENT[i + 1] & 1))")
    WORD_OPERATOR+=("$((EVENT[i + 1] >> 1))")
done
[ -n "$COMMAND" ] || exit 0
. "${BASH_SOURCE[0]%/*}/lib/privacy-decision.sh" || refuse decision-config \
    "BLOCKED (privacy decision): the generated policy helper could not be loaded."
declare -F privacy_plan privacy_target privacy_finish privacy_verdict >/dev/null || refuse decision-config \
    "BLOCKED (privacy decision): the generated policy helper is incomplete."
# A LEADING env assignment only: as a substring the override fired on any command that merely
# mentioned it, prose in a commit message included.
if [[ "$COMMAND" =~ ^[[:space:]]*PRIVACY_ACK=1[[:space:]] ]]; then
    privacy_plan 1 0 0
    exit 0
fi

# `git` must be in COMMAND POSITION -- the start of the text or the far side of a shell
# operator, past env assignments and the usual wrappers -- and `push` its SUBCOMMAND, reached
# past global flags. Both halves were learned the hard way: `git[[:space:]]+push` missed
# `git -C <repo> push`, the normal way to push a repo you are not standing in (2026-07-23), and
# a match anywhere in the text fired on every command that merely QUOTED a push, a grep pattern
# and a jq fixture included (a ticket, and again on 2026-09-01 while measuring this rewrite).
CMDPOS='(^|[;&|(){}`'$'\n'']|\$\()[[:space:]]*([A-Za-z_][A-Za-z0-9_]*=("[^"]*"|'"'"'[^'"'"']*'"'"'|[^[:space:]]*)[[:space:]]+)*((sudo|env|nice|time|exec|then|do|else|xargs)[[:space:]]+|timeout[[:space:]]+[0-9.]+[[:space:]]+)*'
PUSH_RE="${CMDPOS}git([[:space:]]+-[^[:space:]]+([[:space:]]+[^-][^[:space:]]*)?)*[[:space:]]+push([^[:alnum:]_-]|$)"
[[ "$COMMAND" =~ $PUSH_RE ]] || exit 0
# Count actual decoded command words. Operators inside quoted prose never restart
# command position, including diagnostic heredocs carrying push-chain examples.
PUSH_COUNT=0; PUSH_AT=-1; POSITION=1
for ((i = 0; i < ${#WORDS[@]}; i++)); do
    w="${WORDS[i]}"
    if [ "${WORD_OPERATOR[i]}" -eq 1 ]; then
        [[ "$w" = *[\;\&\|\(\)]* || "$w" = *$'\n'* ]] && POSITION=1
        continue
    fi
    [ "$POSITION" -eq 1 ] || continue
    [[ "$w" =~ ^[A-Za-z_][A-Za-z0-9_]*= ]] && continue
    case "$w" in
        sudo|env|nice|time|exec|then|do|else|xargs) continue ;;
        timeout) i=$((i + 1)); continue ;;
        git)
            j=$((i + 1))
            while [[ "${WORDS[j]:-}" = -* ]]; do
                case "${WORDS[j]}" in -C|-c|--git-dir|--work-tree) j=$((j + 2)) ;; *) j=$((j + 1)) ;; esac
            done
            if [ "${WORDS[j]:-}" = push ]; then
                PUSH_COUNT=$((PUSH_COUNT + 1)); [ "$PUSH_AT" -ge 0 ] || PUSH_AT=$j
                [ "$PUSH_COUNT" -le 1 ] || refuse multiple-pushes \
                    "BLOCKED (privacy scan): run each git push in a separate tool command so every destination/range is scanned."
            fi ;;
    esac
    POSITION=0
done
[ "$PUSH_COUNT" -eq 1 ] || exit 0

# Which repo does the push TARGET? PreToolUse fires before the command, so for
# `cd <repo> && git push` the hook cwd is still the session's; gating that waved the real push
# through whenever the session cwd had nothing outgoing (measured 2026-07-23).
REPO="${CWD:-.}"
# The push is the first `push` after a `git` word, not the last `push` in the text: a command
# that ended in prose (`... echo push cat`) once handed `cat` to `git remote get-url`.
[ "$PUSH_AT" -ge 0 ] || exit 0
# `-C` belongs to the push invocation, not to any git in the line: a diagnostic running
# `git -C <other> log` beside a quoted push scanned the wrong repo entirely.
FOUND_C=0
j=$((PUSH_AT - 1))
while [ "$j" -ge 0 ]; do
    case "${WORDS[j]}" in
        git|*[\<\>\|\;\&\(\)]*) break ;;
        -C) REPO="${WORDS[j + 1]:-$REPO}"; FOUND_C=1; break ;;
    esac
    j=$((j - 1))
done
if [ "$FOUND_C" -eq 0 ]; then
    for i in "${!WORDS[@]}"; do
        [ "${WORDS[i]}" = cd ] && [ "$i" -lt "$PUSH_AT" ] && REPO="${WORDS[i + 1]:-$REPO}"
    done
fi
case "$REPO" in
    '~') REPO="$HOME" ;;
    '~/'*) REPO="$HOME/${REPO#\~/}" ;;
    '$HOME') REPO="$HOME" ;;
    '$HOME/'*) REPO="$HOME/${REPO#\$HOME/}" ;;
esac
[ -d "$REPO" ] || REPO="${CWD:-.}"

GIT_TIMEOUT=3
SCAN_TIMEOUT=12
# ONE deadline for the whole gate, under the 20 s settings.json declares. Per-call bounds
# do not add up on their own: five git calls plus a scan overran the outer budget and came back
# as 124, which PreToolUse reads as a hook error and pushes anyway (21.9 s measured, review
# 2026-09-01). Each bounded call below asks for min(its own bound, what is left of this).
DEADLINE_US=17000000
T0_US="${GATE_STARTED_AT/./}"; [ -n "$T0_US" ] || T0_US=$(( $(date +%s%N) / 1000 ))
BOUND=""
bound() {  # bound <seconds> -> $BOUND; under a second left, the gate refuses instead
    local now="${EPOCHREALTIME:-}"; now="${now/./}"
    [ -n "$now" ] || now=$(( $(date +%s%N) / 1000 ))
    local left=$((T0_US + DEADLINE_US - now)) own=$(($1 * 1000000))
    [ "$left" -gt 1000000 ] || refuse deadline \
        "BLOCKED (privacy scan): this gate's $((DEADLINE_US / 1000000))s deadline ran out, so the outgoing history was NOT scanned. Push a smaller range, or re-run when the repository is quicker to read."
    [ "$left" -lt "$own" ] && own="$left"
    BOUND="$(printf '%d.%03d' $((own / 1000000)) $(((own % 1000000) / 1000)))"
}
G_OUT=""
g() {  # g <git args...> -> rc, output in $G_OUT; a git that does not answer REFUSES
    bound "$GIT_TIMEOUT"
    G_OUT="$(timeout "$BOUND" git -C "$REPO" "$@" 2>/dev/null)"
    local rc=$?
    [ "$rc" -ne 124 ] || refuse git-stalled \
        "BLOCKED (privacy scan): git did not answer within ${BOUND}s, so the outgoing history was NOT scanned. Re-run once git responds."
    # 126/127 is the bounded call failing to START. Read as a git verdict it says "not a
    # repository" and the push leaves unscanned (review, 2026-09-01).
    case "$rc" in 126|127) refuse git-unusable \
        "BLOCKED (privacy scan): the bounded git call could not run (status $rc), so the outgoing history was NOT scanned." ;; esac
    return "$rc"
}
g rev-parse --is-inside-work-tree || exit 0

# Remote and refspecs: the words after `push`, stopping at the first shell operator, since
# `git push 2>&1 | tail -3` would otherwise read `2>&1` as the remote.
REMOTE=""
REFSPECS=()
SKIP=0
BRANCHES=0; TAGS=0; MIRROR=0; MATCHING=0; FOLLOW=0; DEFAULTED=1
for ((i = PUSH_AT + 1; i < ${#WORDS[@]}; i++)); do
    w="${WORDS[i]}"
    case "$w" in *[\<\>\|\;\&\(\)]*) break ;; esac
    [ "${WORD_OPERATOR[i]}" -eq 1 ] && break
    # The tokenizer hands `2>&1` over as the word `2` and the operator `>&`: an fd number is
    # not a remote or a refspec, and read as one it scanned nothing (2026-09-30).
    [[ "$w" =~ ^[0-9]+$ && "${WORD_OPERATOR[i + 1]:-0}" -eq 1 && "${WORDS[i + 1]}" = [\<\>]* ]] && break
    if [ "$SKIP" -eq 1 ]; then SKIP=0; continue; fi
    case "$w" in
        # A delete sends no commits, and a dry run sends nothing at all.
        --delete|-d|--dry-run|-n) exit 0 ;;
        # `--all` and `--mirror` REPLACE the default refspec; `--tags` adds to it. All three
        # were scanned as "whatever HEAD points at", which is not what any of them pushes.
        --all) BRANCHES=1; DEFAULTED=0; continue ;;
        --mirror) MIRROR=1; DEFAULTED=0; continue ;;
        --tags) TAGS=1; continue ;;
        --follow-tags) FOLLOW=1; continue ;;
        -o|--push-option|--receive-pack|--exec|--repo) SKIP=1; continue ;;
        -*) continue ;;
        # The exact matching refspec, which is every branch both sides already hold -- not the
        # `:dst` delete it was being read as.
        :) MATCHING=1; DEFAULTED=0; continue ;;
    esac
    if [ -z "$REMOTE" ]; then REMOTE="$w"; else REFSPECS+=("$w"); DEFAULTED=0; fi
done
[ -n "$REMOTE" ] || REMOTE=origin
MORE=()
if [ "$BRANCHES" -eq 1 ] && g for-each-ref --format='%(refname:short)' refs/heads \
   && [ -n "$G_OUT" ]; then mapfile -t MORE <<<"$G_OUT"; REFSPECS+=("${MORE[@]}"); fi
if [ "$TAGS" -eq 1 ] && g for-each-ref --format='%(refname)' refs/tags \
   && [ -n "$G_OUT" ]; then mapfile -t MORE <<<"$G_OUT"; REFSPECS+=("${MORE[@]}"); fi
# `--mirror` sends EVERY local ref, not only branches and tags: a custom ref went unscanned.
if [ "$MIRROR" -eq 1 ] && g for-each-ref --format='%(refname)' refs/ && [ -n "$G_OUT" ]; then
    while IFS= read -r r; do case "$r" in refs/remotes/*) ;; *) REFSPECS+=("$r") ;; esac; done <<<"$G_OUT"
fi
# The exact `:` refspec sends only branches the remote already holds under the same name.
if [ "$MATCHING" -eq 1 ] && g for-each-ref --format='%(refname:short)' refs/heads && [ -n "$G_OUT" ]; then
    BR="$G_OUT"
    while IFS= read -r b; do g rev-parse --verify --quiet "refs/remotes/$REMOTE/$b" && REFSPECS+=("$b"); done <<<"$BR"
fi
if [ "$DEFAULTED" -eq 1 ] && g rev-parse --abbrev-ref HEAD \
   && [ -n "$G_OUT" ]; then REFSPECS+=("$G_OUT"); fi
# `--follow-tags` sends only annotated tags reachable from the commits pushed; every local
# tag over-refused on a tag that sat on an unrelated side branch (review, 2026-09-01).
if [ "$FOLLOW" -eq 1 ] && g for-each-ref --format='%(objecttype) %(refname)' refs/tags && [ -n "$G_OUT" ]; then
    TAGLIST="$G_OUT"
    while read -r type ref; do
        [ "$type" = tag ] || continue
        for spec in ${REFSPECS+"${REFSPECS[@]}"}; do
            src="${spec#+}"; src="${src%%:*}"
            g merge-base --is-ancestor "$ref^{commit}" "$src" && { REFSPECS+=("$ref"); break; }
        done
    done <<<"$TAGLIST"
fi
[ "${#REFSPECS[@]}" -gt 0 ] || exit 0

# Where the commits actually LAND: the configured push URLs, `remote.<r>.pushurl` when set and
# `remote.<r>.url` otherwise, unexpanded. Classifying the FETCH url let a remote whose fetch
# side is a private box and whose push side is a public forge publish unscanned (review,
# 2026-09-01). Only a proven-private destination skips the identifier scan: `private` from gh
# for a repo on a recognized forge, a local filesystem destination, or an SSH alias whose
# exact Tailscale endpoint is pinned in ignored local state. An unfamiliar host is unproven.
DESTS=()
if g config --get-all "remote.$REMOTE.pushurl" && [ -n "$G_OUT" ]; then
    mapfile -t DESTS <<<"$G_OUT"
elif g config --get-all "remote.$REMOTE.url" && [ -n "$G_OUT" ]; then
    mapfile -t DESTS <<<"$G_OUT"
fi
# Git's own rewriting (`insteadOf`, `pushInsteadOf`) can turn an alias into a forge URL, so
# the expanded destinations are classified as well; an alias never hides a public push.
if g remote get-url --push --all "$REMOTE" && [ -n "$G_OUT" ]; then
    while IFS= read -r u; do DESTS+=("$u"); done <<<"$G_OUT"
fi
# `git push <url> <ref>` names its destination outright; a remote NAME that resolves to
# nothing is unknown, and unknown is not private.
# A remote name cannot hold `:`, so `alias:path` (scp form with no user) is a URL too.
[ "${#DESTS[@]}" -gt 0 ] || case "$REMOTE" in
    *://*|*:*|/*|./*|../*) DESTS=("$REMOTE") ;;
    *) DESTS=("") ;;
esac
WHAT="a secret, or a private identifier the remote is not proven private enough to receive (matchers: the tokens in \$HOME/.claude/config/private-tokens.txt plus the re shape classes in that file)"
PROVEN_PRIVATE=1
PIN_FILE="${PRIVATE_PUSH_DESTINATIONS_FILE:-$HOME/.config/privacy/private-push-destinations.txt}"
NETWORKS_FILE="${PRIVATE_PUSH_NETWORKS_FILE:-$HOME/.config/privacy/private-push-networks.txt}"
ssh_endpoint_private() {
    local alias="$1" pinned="" name address extra key value SSH_CONFIG=""
    [[ "$alias" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || return 1
    [ -z "${GIT_SSH:-}${GIT_SSH_COMMAND:-}${GIT_SSH_VARIANT:-}" ] || return 1
    local token
    for token in "${WORDS[@]}"; do
        case "$token" in core.sshCommand=*|url.*.insteadOf=*|url.*.pushInsteadOf=*|GIT_CONFIG_*=*|GIT_SSH*=*) return 1 ;; esac
    done
    g config --get core.sshCommand && [ -n "$G_OUT" ] && return 1
    [ -r "$PIN_FILE" ] || return 1
    while IFS=$'\t' read -r name address extra; do
        [ "$name" = "$alias" ] && [ -n "$address" ] && [ -z "$extra" ] && { pinned="$address"; break; }
    done < "$PIN_FILE"
    [ -n "$pinned" ] || return 1
    # -G evaluates local SSH configuration without opening a connection. Refuse a proxy,
    # jump, changed mapping, or unexpected endpoint; only an owner-pinned overlay route counts.
    bound 3
    SSH_CONFIG="$(timeout "$BOUND" ssh -G -o BatchMode=yes "$alias" 2>/dev/null)" || return 1
    local hostname="" proxycommand="" proxyjump=""
    while IFS=' ' read -r key value; do
        case "$key" in
            hostname) hostname="$value" ;;
            proxycommand) proxycommand="$value" ;;
            proxyjump) proxyjump="$value" ;;
        esac
    done <<< "$SSH_CONFIG"
    [ "$hostname" = "$pinned" ] || return 1
    [ "${proxycommand:-none}" = none ] && [ "${proxyjump:-none}" = none ] || return 1
    # The overlay networks and DNS suffixes that count as private are the owner's, listed in
    # ignored local state (one CIDR or one leading-dot suffix per line); absent means unproven.
    [ -r "$NETWORKS_FILE" ] || return 1
    /usr/bin/python3 -S - "$hostname" "$NETWORKS_FILE" <<'PY'
import ipaddress
import sys

host, networks_file = sys.argv[1], sys.argv[2]
networks, suffixes = [], []
with open(networks_file, encoding="utf-8") as handle:
    for line in handle:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("."):
            suffixes.append(line)
        else:
            networks.append(ipaddress.ip_network(line, strict=False))
try:
    private = any(ipaddress.ip_address(host) in network for network in networks)
except ValueError:
    parts = host.split(".")
    private = (any(host.endswith(suffix) for suffix in suffixes) and len(parts) >= 3
               and all(part and part.strip("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-") == ""
                       for part in parts))
sys.exit(0 if private else 1)
PY
}
for d in ${DESTS+"${DESTS[@]}"}; do
    TARGET_PRIVATE=0
    HOST=""
    case "$d" in
        /*|./*|../*|file:///*) TARGET_PRIVATE=1 ;;
        *) [ -n "$d" ] && [ -d "$REPO/$d" ] && [[ "$d" != *:* ]] && TARGET_PRIVATE=1 ;;
    esac
    case "$d" in
        *://*) HOST="${d#*://}"; HOST="${HOST%%/*}"; HOST="${HOST##*@}"; HOST="${HOST%%:*}" ;;
        *:*) HOST="${d%%:*}"; HOST="${HOST##*@}" ;;
    esac
    case "$HOST" in
        github.com|gitlab.com|codeberg.org|bitbucket.org|huggingface.co|sr.ht|git.sr.ht)
            # 3 s, not the gh gate's 1.2: this budget is 20 s, and a lookup that times out under
            # load turns a private repo into an identifier scan of its whole outgoing range.
            bound 3
            VIS="$(timeout "$BOUND" gh repo view "$d" --json visibility -q .visibility 2>/dev/null)"
            VIS_RC=$?
            TARGET_PRIVATE=0; [ "$VIS_RC" -eq 0 ] && [ "${VIS,,}" = private ] && TARGET_PRIVATE=1 ;;
        "") ;;
        *)
            case "$d" in ssh://*) ssh_endpoint_private "$HOST" && TARGET_PRIVATE=1 ;;
                         *://*) ;;
                         *:*) ssh_endpoint_private "$HOST" && TARGET_PRIVATE=1 ;; esac ;;
    esac
    privacy_target "$PROVEN_PRIVATE" "$TARGET_PRIVATE"
    [ "$PROVEN_PRIVATE" -eq 1 ] || break
done
privacy_plan 0 1 "$PROVEN_PRIVATE"
# the operator, 2026-10-01: scraped pages under a `raw/` directory carry other sites' embedded keys
# (Google Maps and the like) by the hundred; a proven-private destination may receive them.
# git leaves them out of the diff itself; the messages are read without a pathspec, which would
# also drop every commit that touches only raw/.
DIFF_PATHS=()
if [ "$PROVEN_PRIVATE" -eq 1 ]; then
    WHAT="what looks like a live credential (every push destination is private, so private identifiers were not scanned for, nor files under a raw/ directory)"
    DIFF_PATHS=(-- . ':(exclude,glob)**/raw/**')
fi

SCANNER="${PRIVACY_SCANNER:-$HOOK_DIR/lib/privacy-scan.py}"
[ -r "$SCANNER" ] || refuse scanner-missing \
    "BLOCKED (gate config): the privacy scanner at $SCANNER is missing, so the outgoing history was NOT scanned."

for spec in "${REFSPECS[@]}"; do
    # `+src:dst` forces the same commits through; the leading `+` made the whole refspec
    # unresolvable and the push went unscanned (review, 2026-09-01).
    spec="${spec#+}"
    # A `:dst` delete sends no commits.
    case "$spec" in :*) continue ;; esac
    SRC="${spec%%:*}"; DST="${spec#*:}"; [ "$DST" = "$spec" ] && DST="$SRC"
    DST="${DST#refs/heads/}"
    g rev-parse --verify --quiet "$SRC^{commit}" || continue
    # An annotated tag's MESSAGE lives in the tag object, which `log -p` never walks.
    TAGOBJ=""
    g rev-parse --verify --quiet "$SRC^{tag}" && TAGOBJ="$G_OUT"
    if g rev-parse --verify --quiet "refs/remotes/$REMOTE/$DST"; then
        RANGE=("$REMOTE/$DST..$SRC")
    else
        # No counterpart on that remote yet: everything on the branch that no ref of this
        # remote already holds. `--not --remotes=<r>` keeps a first push from scanning the
        # whole of history when a sibling branch is already published.
        RANGE=("$SRC" --not "--remotes=$REMOTE")
    fi
    bound "$SCAN_TIMEOUT"
    FINDINGS="$( { [ -n "$TAGOBJ" ] && timeout "$BOUND" git -C "$REPO" cat-file -p "$TAGOBJ" 2>/dev/null
                   if [ "${#DIFF_PATHS[@]}" -gt 0 ]; then
                       timeout "$BOUND" git -C "$REPO" log \
                           --format='commit %H%n%s%n%b' "${RANGE[@]}" 2>/dev/null &&
                       timeout "$BOUND" git -C "$REPO" log -p --format='commit %H' \
                           "${RANGE[@]}" "${DIFF_PATHS[@]}" 2>/dev/null
                   else
                       timeout "$BOUND" git -C "$REPO" log -p \
                           --format='commit %H%n%s%n%b' "${RANGE[@]}" 2>/dev/null
                   fi; } \
        | timeout "$BOUND" /usr/bin/python3 -S "$SCANNER" --classes "$CLASSES" --evidence 2>&1)"
    RC=$?
    privacy_finish "$RC" "$FINDINGS"
    FINDINGS="$SCAN_FINDINGS"
    [ "$PRIVACY_VERDICT" = allow ] && continue
    [ "$PRIVACY_VERDICT" = finding ] && refuse privacy \
        "BLOCKED (privacy): the commits this push would send to $REMOTE carry $WHAT.
$FINDINGS
Redact the flagged lines in a new commit, or -- once the operator has ruled -- re-run with PRIVACY_ACK=1 in front of the push."
    refuse scan-failed \
        "BLOCKED (privacy scan): the scan of $REMOTE/$DST exited $RC instead of finishing, so the outgoing history was NOT cleared. $FINDINGS"
done
exit 0
