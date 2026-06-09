#!/usr/bin/env bash
# gate-resume-read.sh - PreToolUse blocking hook (post-compaction read-gate).
#
# Steady state (the overwhelmingly common case): no sentinel for this session,
# so this is a single bash regex + stat and an exit 0 -- no python spawned. The
# python body runs ONLY in the brief window after a compaction while the
# read-gate is armed. Fails OPEN on any error (only the python's deliberate
# exit 2 blocks; everything else lets the tool proceed).
hookData=$(cat)

# Key the sentinel on the FULL session id (not a truncated prefix) so two sessions
# sharing an 8-char prefix can never share one gate. Must match the restore hook,
# which arms the sentinel under the same full id.
sid="default"
if [[ "$hookData" =~ \"session_id\"[[:space:]]*:[[:space:]]*\"([a-zA-Z0-9_-]+)\" ]]; then
    sid="${BASH_REMATCH[1]}"
fi
sentinel="/tmp/claude-needs-resume-read-${sid}"

# Cheap path: gate not armed -> allow immediately.
[ -f "$sentinel" ] || exit 0

# Armed: hand the same hookData to the python body for the real decision.
printf '%s' "$hookData" | python3 "$(dirname "$0")/gate-resume-read.py" "$sentinel"
exit $?
