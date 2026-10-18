#!/usr/bin/env bash
# The remote half of deploy.sh must restore the previous executable, policy and dashboard
# when the service restart fails. Runs the heredoc block under stubs, no root, no network.
set -euo pipefail
here=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
root=$tmp/root; stage=$tmp/stage; bin=$tmp/bin
mkdir -p "$root/usr/local/lib/approve-gate/dashboard" "$root/etc/approve-gate" "$root/etc/dispatcher" "$stage/dashboard" "$bin"
# previous installation
for f in approve-gate task_approval.py; do printf 'old %s\n' "$f" > "$root/usr/local/lib/approve-gate/$f"; done
for a in index.html app.js style.css; do printf 'old %s\n' "$a" > "$root/usr/local/lib/approve-gate/dashboard/$a"; done
# staged package: a valid policy whose hash is pinned, plus a new executable and dashboard
printf 'print("new")\n' > "$stage/task_approval.py"; printf 'print("new exe")\n' > "$stage/approve-gate"
for a in index.html app.js style.css; do printf 'new %s\n' "$a" > "$stage/dashboard/$a"; done
expected=$(sha256sum "$stage/task_approval.py" | cut -d ' ' -f 1)
printf '{"task_scopes": []}\n' > "$root/etc/approve-gate/config.json"
printf '{"version": 1, "signatures": ["x"]}\n' > "$root/etc/dispatcher/worker-identities.json"
# stubs: install copies; runuser runs the command; systemctl fails the restart
cat > "$bin/install" <<'STUB'
#!/usr/bin/env bash
while [[ $1 == -* ]]; do shift 2; done; cp -- "$1" "$2"
STUB
cat > "$bin/runuser" <<'STUB'
#!/usr/bin/env bash
shift 3; exec "$@"
STUB
cat > "$bin/systemctl" <<'STUB'
#!/usr/bin/env bash
echo "systemctl $*" >> "$SYSTEMCTL_LOG"; [[ $1 == restart ]] && exit 1; exit 0
STUB
chmod +x "$bin"/*
# extract the remote block and point its absolute paths into the temp root
sed -n "/^ssh .* bash -s -- .* <<'REMOTE'$/,/^REMOTE$/p" "$here/deploy.sh" | sed '1d;$d' \
  | sed "s#/usr/local/lib/approve-gate#$root/usr/local/lib/approve-gate#g; s#/etc/approve-gate#$root/etc/approve-gate#g; s#/etc/dispatcher#$root/etc/dispatcher#g" > "$tmp/remote.sh"
grep -q 'trap restore ERR' "$tmp/remote.sh"
set +e
SYSTEMCTL_LOG=$tmp/systemctl.log PATH="$bin:$PATH" bash "$tmp/remote.sh" "$stage" "$expected" > "$tmp/out" 2> "$tmp/err"
rc=$?
set -e
[[ $rc -ne 0 ]] || { echo 'FAIL: a failed restart must fail the rollout' >&2; exit 1; }
grep -q 'Approval rollout failed; restoring' "$tmp/err" || { echo 'FAIL: no restore message' >&2; cat "$tmp/err" >&2; exit 1; }
for f in approve-gate task_approval.py; do
  [[ $(cat "$root/usr/local/lib/approve-gate/$f") == "old $f" ]] || { echo "FAIL: $f not restored" >&2; exit 1; }
done
for a in index.html app.js style.css; do
  [[ $(cat "$root/usr/local/lib/approve-gate/dashboard/$a") == "old $a" ]] || { echo "FAIL: dashboard $a not restored" >&2; exit 1; }
done
grep -c 'systemctl restart approve-gate' "$tmp/systemctl.log" | grep -qx 2 || { echo 'FAIL: expected the failed restart and the post-restore restart' >&2; cat "$tmp/systemctl.log" >&2; exit 1; }
echo "test_deploy.sh: ok"
