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
# Contract: settings.json matcher "Bash" + if "Bash(git *)". Input is the tool
# call JSON on STDIN; the command is read from .tool_input.command. Infra failure
# (no jq) WARNS to stderr and allows (fail open); a confirm gate never hard-blocks
# on its own broken plumbing.
set -uo pipefail

INPUT="$(cat)"

# Fail open if jq is unavailable: warn, allow. (infra error, not a policy hit)
if ! command -v jq >/dev/null 2>&1; then
    echo "[gate-destructive-git] jq not found; allowing command without destructive-git check." >&2
    exit 0
fi

COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"

# Act only on git commands; everything else is allowed untouched.
echo "$COMMAND" | grep -qE '(^|[^[:alnum:]_-])git[[:space:]]' || exit 0

REASON=""
if   echo "$COMMAND" | grep -qE 'git[[:space:]]+reset[[:space:]]+.*--hard'; then
    REASON="git reset --hard discards all uncommitted changes in the worktree"
elif echo "$COMMAND" | grep -qE 'git[[:space:]]+clean[[:space:]]+-[a-zA-Z]*f|git[[:space:]]+clean[[:space:]]+--force'; then
    REASON="git clean -f permanently deletes untracked files"
elif echo "$COMMAND" | grep -qE 'git[[:space:]]+branch[[:space:]]+(-D|.*--delete[[:space:]]+--force|.* -D )'; then
    REASON="git branch -D force-deletes a branch and can drop unmerged commits"
elif echo "$COMMAND" | grep -qE 'git[[:space:]]+(checkout|restore)[[:space:]]+(\.|--($|[[:space:]]))'; then
    REASON="git checkout/restore of paths overwrites uncommitted worktree changes"
elif echo "$COMMAND" | grep -qE 'git[[:space:]]+stash[[:space:]]+(clear|drop)'; then
    REASON="git stash clear/drop discards stashed work"
fi

[ -z "$REASON" ] && exit 0

jq -n --arg r "$REASON. Confirm this is intended before it runs. (git push is not gated here.)" \
  '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$r}}'
exit 0
