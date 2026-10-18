#!/usr/bin/env bash
# Copy the dispatcher to the VPS (service + briefs, as root) and the runner to a worker account.
#   deploy/deploy.sh vps      -> /usr/local/lib/dispatcher/ on vps, restart dispatcher.service
#   deploy/deploy.sh laptop   -> ~/.local/lib/dispatcher/worker-run on this laptop
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
: "${DISPATCHER_DEPLOY_HOST:=vps}"
case "${1:-}" in
  vps)
    ssh "$DISPATCHER_DEPLOY_HOST" 'mkdir -p /usr/local/lib/dispatcher'
    scp -q "$here"/dispatcher.py "$here"/task_approval.py "$here"/approval_guard.py "$here"/worker-run "$here"/BRIEF*.md "$here"/code-writing-style.md "$DISPATCHER_DEPLOY_HOST":/usr/local/lib/dispatcher/
    scp -q "$here"/deploy/dispatcher.service "$DISPATCHER_DEPLOY_HOST":/etc/systemd/system/dispatcher.service
    ssh "$DISPATCHER_DEPLOY_HOST" 'chmod 755 /usr/local/lib/dispatcher/dispatcher.py /usr/local/lib/dispatcher/worker-run; systemctl daemon-reload; systemctl restart dispatcher; sleep 2; systemctl is-active dispatcher'
    ;;
  laptop)
    mkdir -p ~/.local/lib/dispatcher
    install -m 755 "$here"/worker-run ~/.local/lib/dispatcher/worker-run
    install -m 644 "$here"/code-writing-style.md ~/.local/lib/dispatcher/code-writing-style.md
    ;;
  *) echo "usage: deploy.sh vps|laptop"; exit 64 ;;
esac
