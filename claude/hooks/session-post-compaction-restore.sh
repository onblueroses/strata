#!/usr/bin/env bash
# SessionStart, compaction only. The harness already writes its own compaction
# summary and reloads the CLAUDE.md chain; this hook adds the two things it
# cannot know: where the working tree stands, and what /context-save wrote for
# this session. Everything else the old layer carried (read-gate, sentinels,
# spec scanning, session events, transcript backups) was cut 2026-09-01 —
# measured over 30 days it gated two tool calls and spent a median 9,640
# characters per boundary. Judgment over enforcement.
#
# Every path exits 0 and prints nothing on failure: a hook error costs the
# session more than a missing hint does.

set -u

data=""
[ -t 0 ] || data=$(cat)
[ -n "$data" ] || exit 0

src=$(printf '%s' "$data" | jq -r '.source // empty' 2>/dev/null) || exit 0
[ "$src" = "compact" ] || exit 0

cwd=$(printf '%s' "$data" | jq -r '.cwd // empty' 2>/dev/null)
sid=$(printf '%s' "$data" | jq -r '.session_id // empty' 2>/dev/null)
save="${STATE_DIR:-${HOME:-}/life/areas/claude-code-setup/state}/auto-context-save-${sid:0:8}.md"

{
    printf 'POST-COMPACTION\n'

    if [ -n "$cwd" ] && git -C "$cwd" rev-parse --git-dir >/dev/null 2>&1; then
        printf '\nGit state of %s:\n' "$cwd"
        git -C "$cwd" status -sb 2>/dev/null | head -12
        git -C "$cwd" log --oneline -3 2>/dev/null
    fi

    if [ -n "$sid" ] && [ -f "$save" ]; then
        printf '\nSession save %s (written %s):\n\n' \
            "$save" "$(date -r "$save" '+%Y-%m-%d %H:%M' 2>/dev/null)"
        head -150 "$save"
        # Report the tail rather than hiding it; the model can read the file.
        total=$(wc -l < "$save" 2>/dev/null | tr -d ' ')
        [ "${total:-0}" -gt 150 ] && printf '\n(+%s more lines in the file)\n' "$((total - 150))"
    fi
} 2>/dev/null

exit 0
