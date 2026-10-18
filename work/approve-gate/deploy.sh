#!/usr/bin/env bash
# Example installer. Requires an explicit SSH target and pre-provisioned service config.
set -euo pipefail
: "${APPROVE_GATE_SSH_HOST:?set APPROVE_GATE_SSH_HOST to the target host}"
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source_module=$(readlink -f -- "$here/../dispatcher/task_approval.py")
expected=$(cat "$here/task_approval.sha256")
[[ $expected =~ ^[0-9a-f]{64}$ ]] || { echo 'invalid reviewed task-policy hash' >&2; exit 1; }
actual=$(sha256sum "$source_module" | cut -d ' ' -f 1)
[[ $actual == "$expected" ]] || { echo 'task_approval.py changed; review and repin it first' >&2; exit 1; }
[[ $(sha256sum "$here/task_approval.py" | cut -d ' ' -f 1) == "$expected" ]] || {
  echo 'approval page task policy differs from the reviewed dispatcher source' >&2; exit 1;
}
python3 -m unittest discover -s "$here" -p 'test_*.py'
stage=$(ssh "$APPROVE_GATE_SSH_HOST" 'mktemp -d /tmp/approve-gate-stage.XXXXXXXX')
scp -q "$here/approve-gate" "$source_module" "$APPROVE_GATE_SSH_HOST:$stage/"
ssh "$APPROVE_GATE_SSH_HOST" "mkdir -m 700 '$stage/dashboard'"
scp -q "$here/dashboard/index.html" "$here/dashboard/app.js" "$here/dashboard/style.css" \
  "$APPROVE_GATE_SSH_HOST:$stage/dashboard/"
ssh "$APPROVE_GATE_SSH_HOST" bash -s -- "$stage" "$expected" <<'REMOTE'
set -euo pipefail
stage=$1
expected=$2
target=/usr/local/lib/approve-gate
[[ -d $stage && -f $stage/approve-gate && -d $stage/dashboard ]]
[[ $(sha256sum "$stage/task_approval.py" | cut -d ' ' -f 1) == "$expected" ]]
python3 -m py_compile "$stage/approve-gate" "$stage/task_approval.py"
python3 - <<'PY'
import json
from pathlib import Path
config = json.loads(Path('/etc/approve-gate/config.json').read_text())
assert not config.get('task_scopes'), 'task mode must remain disabled'
policy = json.loads(Path('/etc/dispatcher/worker-identities.json').read_text())
assert policy['version'] == 1 and policy['signatures']
PY
runuser -u approve-gate -- test -r /etc/dispatcher/worker-identities.json
backup=$(mktemp -d /tmp/approve-gate-backup.XXXXXXXX)
chmod 700 "$backup"
cp -a "$target/approve-gate" "$target/task_approval.py" "$backup/"
cp -a "$target/dashboard" "$backup/"
restore() {
  status=$?
  trap - ERR
  echo "Approval rollout failed; restoring $backup" >&2
  cp -a "$backup/approve-gate" "$backup/task_approval.py" "$target/" || echo 'Executable or policy restore failed' >&2
  cp -a "$backup/dashboard/." "$target/dashboard/" || echo 'Dashboard restore failed' >&2
  systemctl restart approve-gate || echo 'Service restart after restore failed' >&2
  exit "$status"
}
trap restore ERR
install -o root -g root -m 755 "$stage/approve-gate" "$target/approve-gate"
install -o root -g root -m 644 "$stage/task_approval.py" "$target/task_approval.py"
for asset in index.html app.js style.css; do
  install -o root -g root -m 644 "$stage/dashboard/$asset" "$target/dashboard/$asset"
done
systemctl restart approve-gate
systemctl is-active --quiet approve-gate
sleep 2
systemctl is-active --quiet approve-gate
runuser -u approve-gate -- test -r /etc/dispatcher/worker-identities.json
[[ $(sha256sum "$target/task_approval.py" | cut -d ' ' -f 1) == "$expected" ]]
cmp -s "$stage/approve-gate" "$target/approve-gate"
for asset in index.html app.js style.css; do
  cmp -s "$stage/dashboard/$asset" "$target/dashboard/$asset"
done
trap - ERR
echo "Approval package installed; rollback copy retained at $backup"
REMOTE
