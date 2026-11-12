#!/usr/bin/env bash
# SessionStart, compaction only. The harness already writes its own compaction
# summary and reloads the CLAUDE.md chain; this hook adds the two things it
# cannot know: where the working tree stands, and what /context-save wrote for
# this session. Everything else the old layer carried (read-gate, sentinels,
# spec scanning, session events, transcript backups) was cut 2026-09-01: it
# rarely changed an outcome and cost context at every boundary. Judgment over
# enforcement.
#
# A save is inlined ONCE per version: every later compaction of a
# session repeated a brief that was by then older than the summary beside it.
# After the first inline its content is in context and rides the next summary; later
# boundaries get one line naming the file and its age. A rewritten save (new
# mtime or size) is inlined again.
#
# The save is bounded by characters, not lines, because a harness bounds a SessionStart
# payload by characters and a long save can pass that bound in few lines. SAVE_CHARS is a
# sample value; set COMPACTION_SAVE_CHARS (config/hooks-runtime.env.example) to fit your harness.
#
# Every path exits 0 and prints nothing on failure: a hook error costs the
# session more than a missing hint does.

set -u
SAVE_CHARS=${COMPACTION_SAVE_CHARS:-7000}

data=""
[ -t 0 ] || data=$(cat)
[ -n "$data" ] || exit 0

src="" cwd="" sid=""
IFS=$'\x1f' read -r -d '' src cwd sid < <(
    printf '%s' "$data" | jq -j '[.source, .cwd, .session_id] | map(. // "" | tostring)
        | join("\u001f") + "\u0000"' 2>/dev/null)
[ "$src" = compact ] || exit 0

short=${sid:0:8}
# The brief lives in BRIEF_DIR since 2026-11-10 (`<date>-<agent>-<sid8>-brief.md`, written by
# /context-save); the newest match wins. A session saved before that still has its save in the
# read-only archive (STATE_DIR), which stays readable.
save=""
if [ -n "$short" ]; then
    for candidate in "${BRIEF_DIR:-${NOTES_ROOT:-${HOME:-}/notes}/briefs}"/*-"$short"-brief.md; do
        [ -f "$candidate" ] && save=$candidate
    done
    [ -n "$save" ] || save="${STATE_DIR:-${NOTES_ARCHIVE:-${HOME:-}/notes-archive}/state}/auto-context-save-$short.md"
fi
seenDir="${COMPACTION_STATE_DIR:-${XDG_CACHE_HOME:-${HOME:-}/.cache}/claude-compaction}"
mode=none chars=0 age=""

{
    printf 'POST-COMPACTION\n'

    if [ -n "$cwd" ] && git -C "$cwd" rev-parse --git-dir >/dev/null 2>&1; then
        printf '\nGit state of %s:\n' "$cwd"
        git -C "$cwd" status -sb 2>/dev/null | head -12
        git -C "$cwd" log --oneline -3 2>/dev/null
    fi

    if [ -n "$short" ] && [ -f "$save" ]; then
        version=$(stat -c '%Y %s' -- "$save" 2>/dev/null) || version=""
        written=$(date -r "$save" '+%Y-%m-%d %H:%M' 2>/dev/null)
        [ -z "$version" ] || age=$(( ($(date +%s) - ${version%% *}) / 60 ))
        seen=""
        [ -r "$seenDir/$short" ] && IFS= read -r seen < "$seenDir/$short"
        if [ -n "$version" ] && [ "$seen" = "$version" ]; then
            mode=pointed
            printf '\nSession save %s (written %s) was inlined after an earlier compaction and has not changed since. Read it if the summary lacks something it holds.\n' \
                "$save" "$written"
        else
            mode=inlined
            content=$(<"$save")
            chars=${#content}
            printf '\nSession save %s (written %s):\n\n' "$save" "$written"
            if [ "$chars" -gt "$SAVE_CHARS" ]; then
                head=${content:0:SAVE_CHARS}
                # End on a whole line when there is one to end on.
                case "$head" in *$'\n'*) head=${head%$'\n'*} ;; esac
                printf '%s\n' "$head"
                # Report the rest rather than hiding it; the model can read the file.
                printf '\n(+%s more characters in the file)\n' "$((chars - ${#head}))"
            else
                printf '%s\n' "$content"
            fi
            if [ -n "$version" ] && mkdir -p -- "$seenDir" 2>/dev/null; then
                printf '%s\n' "$version" > "$seenDir/$short"
            fi
        fi
    fi
} 2>/dev/null

# One row per boundary, written after the payload is out and bounded, so the sink can never
# be why a session loses its restore. TELEMETRY_TIMEOUT is a sample value.
emitter="${HOME:-}/.claude/telemetry/telemetry-emit.sh"
if [ -f "$emitter" ] && [ -n "$short" ]; then
    /usr/bin/timeout "${TELEMETRY_TIMEOUT:-1s}" bash "$emitter" compaction_restore "$short" \
        "{\"save\":\"$mode\",\"chars\":$chars${age:+,\"age_min\":$age}}" >/dev/null 2>&1 || true
fi

exit 0
