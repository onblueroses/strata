#!/usr/bin/env bash
# Regression case for the ownership guards added to ~/.local/bin/codex-broker-reap
# (2026-07-27 cross-session reaping audit). Synthetic table only; nothing is signalled.
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
source "$script_dir/lib-orphan-scope.sh"

MAX_AGE=259200   # 3 days, the reaper's threshold

TABLE="$(mktemp)"
trap 'rm -f "$TABLE"' EXIT
# pid ppid sid etimes args
cat > "$TABLE" <<'EOF'
1 0 1 999999 /sbin/init
4000 1 4000 900000 -bash
4001 4000 4000 800000 claude
7001 4001 4000 400000 node /srv/example-user/.claude/plugins/codex/app-server-broker.mjs serve
7002 7001 4000 400000 node /srv/example-user/.claude/plugins/codex/node_modules/.bin/codex app-server
8001 1 8000 400000 node /srv/example-user/.claude/plugins/codex/app-server-broker.mjs serve
8002 8001 8000 400000 node /srv/example-user/.claude/plugins/codex/node_modules/.bin/codex app-server
9001 1 9000 400000 node /srv/example-user/.claude/plugins/codex/app-server-broker.mjs serve
9002 9001 9000 900 /srv/example-user/vendor/bin/codex exec --skip-git-repo-check
EOF

# 7001: broker still parented to a LIVE claude session -> owned, must survive
has_live_ancestor 7001 claude "$TABLE" || { echo "FAIL: 7001 should show a live claude ancestor"; exit 1; }
# 8001: fully detached, whole subtree as old as the broker -> genuine orphan, must be reaped
has_live_ancestor 8001 claude "$TABLE" && { echo "FAIL: 8001 must not show a live claude ancestor"; exit 1; }
has_recent_descendant 8001 "$MAX_AGE" "$TABLE" && { echo "FAIL: 8001 has no recent descendant"; exit 1; }
# 9001: detached but running a 15-minute-old codex request -> in use, must survive
has_recent_descendant 9001 "$MAX_AGE" "$TABLE" || { echo "FAIL: 9001 should show a recent descendant"; exit 1; }

printf 'codex-broker-reap: owned and in-use brokers survive; the abandoned broker is still reaped\n'
