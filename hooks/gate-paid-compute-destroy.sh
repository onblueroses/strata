#!/usr/bin/env bash
# gate-paid-compute-destroy.sh - PreToolUse(Bash) deny gate
# Blocks paid-compute teardown commands until results are confirmed synced.
# Speed-bump pattern: a teardown verb is denied with a sync reminder so the
# operator pulls every artifact locally, verifies it, then re-runs the command.
# The pause is the point.
#
# Config: settings.json matcher "Bash" with NO "if" filter — the script is the
# single source of truth for which commands are teardowns, so it must see every
# Bash command (this is what lets EXTRA_TEARDOWN_PATTERNS additions actually
# fire). Input: the tool call JSON on stdin. Deny: human-readable reason to
# stderr + exit 2 (the PreToolUse deny signal). Infra failure (missing jq) WARNS
# to stderr and allows (exit 0); an infra problem never hard-blocks a command.

set -uo pipefail

# Teardown command patterns to guard (extended-regex fragments matched against
# the Bash command). Built-ins cover the common paid-compute CLIs. Add any other
# provider CLI you use by extending EXTRA_TEARDOWN_PATTERNS, e.g.:
#   EXTRA_TEARDOWN_PATTERNS+=('prime[[:space:]]+pods[[:space:]]+(stop|remove|delete)')
#   EXTRA_TEARDOWN_PATTERNS+=('mycloud[[:space:]]+(destroy|stop)')
TEARDOWN_PATTERNS=(
  'aws[[:space:]]+ec2[[:space:]]+(stop|terminate)-instances'
  'gcloud[[:space:]]+compute[[:space:]]+instances[[:space:]]+(stop|delete)'
  'runpodctl[[:space:]]+(stop|remove)[[:space:]]+pod'
  'vastai[[:space:]]+(destroy|stop)[[:space:]]+instance'
)
EXTRA_TEARDOWN_PATTERNS=()
if [ "${#EXTRA_TEARDOWN_PATTERNS[@]}" -gt 0 ]; then
  TEARDOWN_PATTERNS+=("${EXTRA_TEARDOWN_PATTERNS[@]}")
fi

deny() {
  local cmd="$1"
  {
    echo "BLOCKED: paid-compute teardown command detected."
    echo ""
    echo "Command: $cmd"
    echo ""
    echo "Confirm every result, log, and artifact is pulled to local storage first."
    echo "Pull the data, verify it locally, then re-run the teardown command."
  } >&2
  exit 2
}

INPUT="$(cat)"

# Fail open on infra problems: without jq the command cannot be parsed, so warn
# and allow rather than block on a tooling gap.
if ! command -v jq >/dev/null 2>&1; then
  echo "[paid-compute-destroy] jq not found; teardown gate skipped (fail-open)." >&2
  exit 0
fi

COMMAND="$(printf '%s' "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null || true)"
[ -n "$COMMAND" ] || exit 0

for pat in "${TEARDOWN_PATTERNS[@]}"; do
  if printf '%s' "$COMMAND" | grep -qE "$pat"; then
    deny "$COMMAND"
  fi
done

exit 0
