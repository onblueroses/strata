#!/usr/bin/env bash
# gate-repo-pair-isolation.sh - PreToolUse(Bash) blocking hook
# Prevents cross-pushing a configured private/public repository pair.
# Config: matcher "Bash". Input: stdin JSON. Deny: exit 2 + stderr. Allow: exit 0.
set -uo pipefail
GATE_STARTED_AT="${EPOCHREALTIME:-}"

INPUT="$(cat)"
if [ -r "${HOME:-$HOME}/.claude/hooks/run-gates.sh" ]; then
    # shellcheck source=run-gates.sh
    . "${HOME:-$HOME}/.claude/hooks/run-gates.sh"
    gate_timing_begin repo-pair-isolation Bash "$INPUT" "$GATE_STARTED_AT"
fi
COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"

# Cheap prefilter: only proceed when a git push appears anywhere. The registration is broad
# so `cd x && git push` and git global options are not hidden by a narrow Bash(if) matcher.
echo "$COMMAND" | grep -qE '\bgit\b([[:space:]]+-[^[:space:]]+([[:space:]]+[^-][^[:space:]]*)?)*[[:space:]]+push\b' || exit 0

# A PreToolUse hook runs before `cd repo && ...` takes effect, and one command line can push
# more than one repo. Resolve the directory that governs EACH push segment: walk the command
# left to right, track cwd across `cd`, and for every `git ... push` emit the cwd in force at
# that segment (a `-C` on that same git invocation wins). tail -1 over the whole string is
# wrong: `cd priv && git push && cd safe` and `git -C priv push && git -C safe status` both
# push the private repo while the last cd/-C names a different one.
PUSH_DIRS="$(COMMAND="$COMMAND" HOOK_PWD="$PWD" /usr/bin/python3 - <<'PY' 2>/dev/null || true
import os, shlex

cmd = os.environ.get("COMMAND", "")
home = os.environ.get("HOME", "")
cwd = os.environ.get("HOOK_PWD", "") or os.getcwd()

def expand(p):
    if p == "~":
        return home
    if p.startswith("~/"):
        return home + "/" + p[2:]
    if p == "$HOME":
        return home
    if p.startswith("$HOME/"):
        return home + "/" + p[6:]
    return p

try:
    lex = shlex.shlex(cmd.replace("\n", ";"), posix=True, punctuation_chars=True)
    lex.whitespace_split = True
    lex.commenters = ""
    toks = list(lex)
except Exception:
    toks = []

segs, cur = [], []
for tok in toks:
    if tok and all(c in ";|&(){}" for c in tok):
        if cur:
            segs.append(cur)
            cur = []
    else:
        cur.append(tok)
if cur:
    segs.append(cur)

for seg in segs:
    i = 0
    while i < len(seg) and (("=" in seg[i] and not seg[i].startswith("=")) or seg[i] in {"sudo", "command", "env", "exec", "nice", "nohup", "time"}):
        i += 1
    seg = seg[i:]
    if not seg:
        continue
    if seg[0] == "cd":
        if len(seg) > 1:
            d = expand(seg[1])
            if not d.startswith("/"):
                d = os.path.normpath(os.path.join(cwd, d))
            cwd = d
        continue
    if seg[0].rsplit("/", 1)[-1] != "git":
        continue
    gdir = None
    sub = None
    j = 1
    while j < len(seg):
        if seg[j] == "-C" and j + 1 < len(seg):
            gdir = seg[j + 1]
            j += 2
            continue
        if seg[j].startswith("-"):
            j += 1
            continue
        sub = seg[j]
        break
    if sub != "push":
        continue
    d = expand(gdir) if gdir else cwd
    if not d.startswith("/"):
        d = os.path.normpath(os.path.join(cwd, d))
    print(d)
PY
)"
[ -n "$PUSH_DIRS" ] || exit 0

emit_block() {
    local reason="$1" message="$2"
    echo "$message" >&2
    # telemetry (additive, fail-open, cold-path only): record the block
    local B S
    B=$(jq -cn --arg h repo-pair-isolation --arg t Bash --arg r "$reason" --arg d deny --arg c "${COMMAND:0:200}" '{hook:$h,tool:$t,reason:$r,decision:$d,cmd:$c}' 2>/dev/null)
    S=$(printf '%s' "$INPUT" | jq -r '.session_id//"unknown"' 2>/dev/null || echo unknown)
    declare -F gate_payload_add_duration >/dev/null && gate_payload_add_duration B
    bash "$HOME/.claude/telemetry/telemetry-emit.sh" hook_block "$S" "$B" 2>/dev/null || true
    exit 2
}

PRIVATE_REPO_MATCH="${PRIVATE_REPO_MATCH:-}"
PUBLIC_REPO_MATCH="${PUBLIC_REPO_MATCH:-}"
if [[ -z "$PRIVATE_REPO_MATCH" || -z "$PUBLIC_REPO_MATCH" ]]; then
    emit_block repo-pair-unconfigured "Cross-push gate blocked: configure both PRIVATE_REPO_MATCH and PUBLIC_REPO_MATCH before pushing."
fi

while IFS= read -r TARGET_DIR; do
    [ -n "$TARGET_DIR" ] || continue
    REPO_GIT=(git)
    [ -d "$TARGET_DIR" ] && REPO_GIT=(git -C "$TARGET_DIR")
    REPO_ROOT="$("${REPO_GIT[@]}" rev-parse --show-toplevel 2>/dev/null)" || continue
    ORIGIN_URL="$("${REPO_GIT[@]}" remote get-url origin 2>/dev/null)" || continue

    IN_PRIVATE=0; IN_PUBLIC=0; PUSH_TO_PRIVATE=0; PUSH_TO_PUBLIC=0
    echo "$REPO_ROOT" | grep -Fq -- "$PRIVATE_REPO_MATCH" && IN_PRIVATE=1
    echo "$REPO_ROOT" | grep -Fq -- "$PUBLIC_REPO_MATCH" && IN_PUBLIC=1
    echo "$ORIGIN_URL" | grep -Fq -- "$PRIVATE_REPO_MATCH" && PUSH_TO_PRIVATE=1
    echo "$ORIGIN_URL" | grep -Fq -- "$PUBLIC_REPO_MATCH" && PUSH_TO_PUBLIC=1

    if [[ $IN_PRIVATE -eq 1 && $PUSH_TO_PUBLIC -eq 1 ]]; then
        emit_block cross-push-priv-to-pub "Cross-push blocked: configured private repository -> public repository. These repos must stay separate. Get explicit approval from the operator before any cross-repo publish."
    fi
    if [[ $IN_PUBLIC -eq 1 && $PUSH_TO_PRIVATE -eq 1 ]]; then
        emit_block cross-push-pub-to-priv "Cross-push blocked: configured public repository -> private repository. These repos must stay separate."
    fi
done <<< "$PUSH_DIRS"

exit 0
