#!/usr/bin/env bash

# Wrapper calls measured below 2s in the 2026-08-11 e2e wave. Three seconds
# leaves 1s of local headroom inside this hook's 4000ms SessionStart budget.
output=$(/usr/bin/timeout --foreground 3s \
  ${ISSUE_TRACKER_CLI:-$HOME/.local/bin/brain-linear} pickup claude --summary \
  2>/dev/null) || exit 0

[[ -z "$output" ]] || printf '%s\n' "$output"
exit 0
