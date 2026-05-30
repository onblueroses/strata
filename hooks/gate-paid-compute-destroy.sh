#!/usr/bin/env bash
# PreToolUse hook: blocks paid-compute teardown commands until the user has
# confirmed data sync. Matches a family of provider commands wired in
# settings.json under the same PreToolUse matcher:
#
#   vastai destroy *
#   runpodctl stop|remove *
#   prime pods stop|remove *
#   gcloud compute instances stop|delete *
#   aws ec2 stop-instances|terminate-instances *
#
# Speed bump pattern: first invocation prints a sync reminder and blocks. The
# user re-runs after verifying sync, at which point the hook fires again — and
# blocks again. The pause is the point. Add provider-specific sync command
# hints below as you bind new providers.

set -euo pipefail

COMMAND="${TOOL_INPUT:-}"

reminder() {
  local kind="$1" ident="$2" sync_hint="$3"
  echo "BLOCKED: $kind teardown on $ident"
  echo ""
  echo "Have you synced all results, logs, and artifacts from this instance?"
  if [ -n "$sync_hint" ]; then
    echo "Sync command (or similar): $sync_hint"
  fi
  echo ""
  echo "Only destroy AFTER verifying results are saved locally."
  echo "If you have synced, re-run the destroy command (this hook fires once per call)."
  exit 1
}

if echo "$COMMAND" | grep -qE 'vastai[[:space:]]+destroy'; then
  ID=$(echo "$COMMAND" | grep -oE '[0-9]{6,}' | head -1)
  reminder "vastai instance" "${ID:-?}" "vastai copy C.${ID:-INSTANCE_ID}:/workspace/results/ ./findings/"
fi

if echo "$COMMAND" | grep -qE 'runpodctl[[:space:]]+(stop|remove)[[:space:]]+pod'; then
  ID=$(echo "$COMMAND" | grep -oE '[a-z0-9]{10,}' | head -1)
  reminder "runpod pod" "${ID:-?}" "runpodctl cp <pod>:/workspace/results ./findings/"
fi

if echo "$COMMAND" | grep -qE 'prime[[:space:]]+pods[[:space:]]+(stop|remove|delete)'; then
  ID=$(echo "$COMMAND" | grep -oE '[a-z0-9-]{8,}' | head -1)
  reminder "prime intellect pod" "${ID:-?}" "prime --plain pods download <pod> ./findings/"
fi

if echo "$COMMAND" | grep -qE 'gcloud[[:space:]]+compute[[:space:]]+instances[[:space:]]+(stop|delete)'; then
  ID=$(echo "$COMMAND" | grep -oE '[a-z][a-z0-9-]{3,}' | tail -1)
  reminder "gcloud instance" "${ID:-?}" "gcloud compute scp --recurse ${ID:-INSTANCE}:/workspace/results ./findings/"
fi

if echo "$COMMAND" | grep -qE 'aws[[:space:]]+ec2[[:space:]]+(stop|terminate)-instances'; then
  ID=$(echo "$COMMAND" | grep -oE 'i-[0-9a-f]{8,}' | head -1)
  reminder "ec2 instance" "${ID:-?}" "aws s3 sync s3://<bucket>/results ./findings/ # or scp from ${ID:-INSTANCE}"
fi

exit 0
