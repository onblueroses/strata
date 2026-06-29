#!/usr/bin/env bash
# gate-codex-exec.sh - PreToolUse(Bash) deny gate
# Denies bare `codex exec` calls and redirects to the lane wrappers (fast / strong)
# or the /codex-review skill, which encode the canonical flag set and handle quota
# fallback. See reference/codex-invocation.md and reference/model-delegation.md.
#
# Config: matcher "Bash" + per-hook filter `Bash(codex *)`. Input: stdin JSON.
# Deny: exit 2 + a human-readable reason on stderr (the PreToolUse deny signal).
# Fails OPEN (exit 0) on infrastructure errors so a tooling gap never hard-blocks.
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

# Strip shell line-comments so 'echo foo # codex exec bar' is not flagged.
# sed runs per line, so `$` is the line end, matching a MULTILINE comment strip.
COMMAND="$(printf '%s' "$COMMAND" | sed -E 's/(^|[ \t])#.*$//')"

# Act only on `codex exec`; leave fast/strong, codex review, codex login, etc. alone.
echo "$COMMAND" | grep -qE '(^|[^[:alnum:]_-])codex[[:space:]]+exec\b' || exit 0

# Allow the canonical full-flag invocation used by the /codex-review skill.
# Require BOTH core sandbox flags so a single-flag manual call cannot slip through.
if echo "$COMMAND" | grep -q -- '--dangerously-bypass-approvals-and-sandbox' \
   && echo "$COMMAND" | grep -q -- '--skip-git-repo-check'; then
    exit 0
fi

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
