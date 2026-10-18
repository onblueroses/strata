#!/usr/bin/env bash
# Regression case for the 2026-07-27 cross-session reaping audit.
# Drives the kill-selection against a SYNTHETIC process table; no real process is signalled.
set -euo pipefail
script_dir="$(cd "$(dirname "$0")" && pwd)"
source "$script_dir/lib-orphan-scope.sh"

# Synthetic table: pid ppid sid etimes args
#  4001 live sibling session's claude, terminal session leader 4000
#  4002 that session's bash -c wrapper
#  4003 FOREIGN-SESSION codex review, 900s old, owner ALIVE   <- must survive
#  5003 genuine orphan codex review, 900s old, reparented to init, owner DEAD <- must be reaped
#  5004 young orphan codex review, 120s old                   <- must survive (under age floor)
#  5005 setsid-detached codex review, own session leader       <- must survive (deliberate lifetime)
#  4004 codex exec dispatch under the live session, 3000s old  <- must survive (not `review`)
#  4005 codex-strong dispatch whose --file argument is named f8-review.md <- must survive (name collision)
TABLE=$(cat <<'EOF'
1 0 1 999999 /sbin/init
4000 1 4000 5000 -bash
4001 4000 4000 4000 claude
4002 4001 4000 950 bash -c codex review --uncommitted
4003 4002 4000 900 /srv/example-user/.local/bin/codex review --uncommitted
5000 1 5000 8000 /sbin/dead-session-placeholder
5003 1 4999 900 /srv/example-user/.local/bin/codex review --uncommitted
5004 1 4998 120 /srv/example-user/.local/bin/codex review --uncommitted
5005 1 5005 900 /srv/example-user/.local/bin/codex review --uncommitted
4004 4001 4000 3000 codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check resume 019fa4ff
4005 4001 4000 3000 codex exec --dangerously-bypass-approvals-and-sandbox --file /srv/example-user/tmp/f8-review.md
EOF
)

# PRE-fix selection, verbatim from the 2026-07-17 version of session-cleanup-codex.sh:
#   ps aux | grep '[c]odex.*review' | grep -v '[c]odex exec'  + etimes > 600
prefix_select() {
  grep 'codex.*review' | grep -v 'codex exec' | awk '$4+0 > 600 {print $1}'
}

pre="$(printf '%s\n' "$TABLE" | prefix_select | sort -n | tr '\n' ' ')"
post="$(printf '%s\n' "$TABLE" | select_orphaned_codex review 600 | sort -n | tr '\n' ' ')"

echo "PRE-fix  selects: $pre"
echo "POST-fix selects: $post"

# The defect: the foreign live session's codex review (4003) and its bash wrapper (4002)
# were selected, along with the deliberately detached job (5005).
[[ "$pre" == *"4003"* ]] || { echo "FAIL: pre-fix should have selected foreign-session pid 4003"; exit 1; }
[[ "$pre" == *"5005"* ]] || { echo "FAIL: pre-fix should have selected detached pid 5005"; exit 1; }

# The fix: the foreign-session process survives, the genuine orphan is still reaped.
[[ "$post" != *"4003"* ]] || { echo "FAIL: post-fix still selects foreign-session pid 4003"; exit 1; }
[[ "$post" != *"4002"* ]] || { echo "FAIL: post-fix still selects foreign-session wrapper 4002"; exit 1; }
[[ "$post" != *"5004"* ]] || { echo "FAIL: post-fix selects a process under the age floor"; exit 1; }
[[ "$post" != *"5005"* ]] || { echo "FAIL: post-fix selects a deliberately detached session leader"; exit 1; }
[[ "$post" != *"4004"* ]] || { echo "FAIL: post-fix selects a codex exec dispatch"; exit 1; }
[[ "$post" != *"4005"* ]] || { echo "FAIL: post-fix selects on a f8-review.md filename collision"; exit 1; }
[[ "$post" == *"5003"* ]] || { echo "FAIL: post-fix stopped reaping the genuine orphan 5003"; exit 1; }

printf 'session-cleanup-codex: foreign-session codex review survives; genuine orphan still reaped\n'
