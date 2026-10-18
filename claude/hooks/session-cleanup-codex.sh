#!/usr/bin/env bash
# SessionStart hook: reap codex review processes left behind by DEAD sessions.
#
# Codex review with xhigh reasoning can run 60-120s. If the parent session dies or
# interrupts, the process orphans and eats resources. This hook clears those.
#
# Ownership is the gate, not the name (2026-07-27): SessionStart fires on every new
# session AND on every post-compaction resume, so any sibling session starting up used
# to sweep the whole host. The old selection was `ps aux | grep '[c]odex.*review'` plus
# an age test, which reaps another live session's work and also fires on unrelated
# processes whose command line merely contains the word "review" (a `--file
# f8-review.md` dispatch, a prompt string). A kill now needs positive evidence that
# the owner is gone: no live `claude` anywhere in the ancestor chain, and the process
# is not a deliberately `setsid`-detached session leader.
# Selection logic and its regression test: lib-orphan-scope.sh, test-session-cleanup-codex.sh.
set -uo pipefail

MIN_AGE_SECS=600   # xhigh reasoning legitimately takes 2-5 min on large diffs

source "$(dirname "${BASH_SOURCE[0]}")/lib-orphan-scope.sh"

STALE_PIDS=$(ps -eo pid=,ppid=,sid=,etimes=,args= | select_orphaned_codex review "$MIN_AGE_SECS")

if [[ -n "$STALE_PIDS" ]]; then
    echo "$STALE_PIDS" | xargs -r kill 2>/dev/null
    COUNT=$(echo "$STALE_PIDS" | wc -l)
    echo "Cleaned up $COUNT orphaned codex process(es) from dead sessions"
fi
