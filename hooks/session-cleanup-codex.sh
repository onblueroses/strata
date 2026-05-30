#!/usr/bin/env bash
# SessionStart hook: kill orphaned codex review processes from dead sessions.
# Codex review with xhigh reasoning can run 60-120s. If the parent session
# dies or interrupts, the process orphans and eats resources.

# Find codex processes older than 10 minutes (600 seconds)
# xhigh reasoning can legitimately take 2-5 min on large diffs
STALE_PIDS=$(ps aux | grep '[c]odex.*review' | awk '{
    # Get elapsed time
    cmd = "ps -o etimes= -p " $2
    cmd | getline elapsed
    close(cmd)
    if (elapsed+0 > 600) print $2
}')

if [[ -n "$STALE_PIDS" ]]; then
    echo "$STALE_PIDS" | xargs kill 2>/dev/null
    COUNT=$(echo "$STALE_PIDS" | wc -l)
    echo "Cleaned up $COUNT orphaned codex process(es)"
fi
