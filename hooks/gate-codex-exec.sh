#!/usr/bin/env bash
# gate-codex-exec.sh - PreToolUse(Bash) blocking hook
# Blocks bare `codex exec` calls and redirects to the documented wrappers
# (fast / strong) or the /codex-review skill.
#
# Allows: `codex exec` invocations that include the full sandbox flag set
# (--dangerously-bypass-approvals-and-sandbox), which is the canonical form
# used by the /codex-review skill per CLAUDE.md "Codex Invocation Standard".

TOOL_INPUT="${CLAUDE_TOOL_INPUT:-}"

COMMAND=$(echo "$TOOL_INPUT" | python3 -c "
import sys, json, re
try:
    data = json.load(sys.stdin)
    cmd = data.get('command', '')
except Exception:
    cmd = ''
# Strip shell line-comments so 'echo foo # codex exec bar' is not flagged.
# Conservative: drop everything from the first ' #' or '\t#' (or '#' at start
# of a line). Doesn't try to parse strings; corner cases with '#' inside
# quotes are rare and the prior behavior was no better.
lines = []
for line in cmd.split('\n'):
    line = re.sub(r'(^|[ \t])#.*$', '', line)
    lines.append(line)
print('\n'.join(lines))
" 2>/dev/null)

# Only fire on `codex exec` (not fast, strong, codex review, codex login, etc.)
if ! echo "$COMMAND" | grep -qE '(^|[^[:alnum:]_-])codex[[:space:]]+exec\b'; then
    exit 0
fi

# Allow the canonical full-flag invocation used by /codex-review skill.
# Require BOTH core sandbox flags so a single-flag manual call can't slip through.
if echo "$COMMAND" | grep -q -- '--dangerously-bypass-approvals-and-sandbox' \
   && echo "$COMMAND" | grep -q -- '--skip-git-repo-check'; then
    exit 0
fi

cat <<'EOF'
{"result": "block", "reason": "Bare `codex exec` is blocked. Use a wrapper instead:\n  - fast \"prompt\"     # default for code tasks (gpt-5.3-codex-spark)\n  - strong \"prompt\"   # load-bearing/architecture/security (gpt-5.5 xhigh)\n  - fast --file PATH  # for prompts >1KB\n  - /codex-review --plan|--hypothesis|--arch  # adversarial review\n\nWrappers encode the canonical flag set, handle quota fallback, and respect Spark credits.\nIf you genuinely need raw `codex exec` (e.g., reproducing the /codex-review invocation), include the full flag set per CLAUDE.md `Codex Invocation Standard`: --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check ..."}
EOF
exit 2
