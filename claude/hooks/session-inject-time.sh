#!/usr/bin/env bash
# SessionStart and UserPromptSubmit: the model's context carries a date but no
# clock and no zone, so any hour it states without shelling out is confabulated,
# and the attractor is UTC; git, docker, server cron, OptMem's gmtime stamps and
# most cloud APIs all report it. Diagnosed 2026-08-05, when a UTC hour was reported
# as the local time.
#
# The durable fact is the zone, not the instant: an offset holds for the whole
# session, a timestamp decays within minutes. So every reading is labeled with
# what it was read at (start, resume, compaction, a prompt), where a stale one
# cannot pass itself off as "now". Offset and delta are computed, never written
# down, so DST and travel stay correct without an edit here.
#
# Two additions on 2026-11-10. The label follows the event's `source`: the hook
# also runs at resume and at every compaction, and said "session started" there,
# hours or days into the session. And on UserPromptSubmit it prints one line when
# the last reading given to this session is more than CLOCK_STALE_MIN old: a
# session open across an afternoon otherwise answers from its start time. A
# prompt inside that window prints nothing.
#
# timedatectl's dbus round trip dominates the start path; the prompt path skips it.
# Codex's start hook runs this with no stdin and gets the plain "session started" form.

set -u

# Sample value in minutes; set CLOCK_STALE_MIN (config/hooks-runtime.env.example) to change it.
CLOCK_STALE_MIN=${CLOCK_STALE_MIN:-30}
stampDir="${CLOCK_STATE_DIR:-${XDG_CACHE_HOME:-${HOME:-}/.cache}/claude-clock}"

event=SessionStart src="" sid=""
if [ ! -t 0 ]; then
    IFS=$'\x1f' read -r -d '' event src sid < <(
        /usr/bin/jq -j '[.hook_event_name // "SessionStart", .source, .session_id]
            | map(. // "" | tostring) | join("\u001f") + "\u0000"' 2>/dev/null) || true
    [ -n "$event" ] || event=SessionStart
fi
stampFile=""
[ -n "$sid" ] && stampFile="$stampDir/${sid:0:8}"

emit_context() {
    /usr/bin/jq -cn --arg event "$event" --arg context "$1" \
        '{hookSpecificOutput:{hookEventName:$event,additionalContext:$context}}'
}

# Remember when this session last got a reading. A failure here only means the
# next prompt repeats the line.
mark() {
    [ -n "$stampFile" ] || return 0
    mkdir -p -- "$stampDir" 2>/dev/null && printf '%s\n' "$EPOCHSECONDS" > "$stampFile" 2>/dev/null
    return 0
}

if [ "$event" = UserPromptSubmit ]; then
    # Fresh enough: say nothing. The stamp holds the epoch of the last reading, so the
    # age test is two builtins and the silent path forks nothing after jq.
    last=""
    [ -n "$stampFile" ] && [ -r "$stampFile" ] && IFS= read -r last < "$stampFile"
    if [[ $last =~ ^[0-9]+$ ]] && (( EPOCHSECONDS - last < CLOCK_STALE_MIN * 60 )); then
        exit 0
    fi
    # No session id means nothing to remember against; stay silent rather than
    # print on every prompt.
    [ -n "$stampFile" ] || exit 0
    if now=$(date '+%Y-%m-%d %H:%M %Z' 2>/dev/null); then
        emit_context "TIME: $now at this prompt."
        mark
    fi
    exit 0
fi

case "$src" in
    resume)  what="session resumed" ;;
    compact) what="context compacted" ;;
    *)       what="session started" ;;
esac

if ! stamp=$(date '+%Y-%m-%d %H:%M %Z|%z' 2>/dev/null); then
    emit_context "TIME: the local clock could not be read, so this session has no time anchor. Run \`date\` before stating any wall-clock time."
    exit 0
fi

now=${stamp%|*}
offset=${stamp##*|}

# IANA name over the abbreviation: PDT is ambiguous across zones, and the
# abbreviation is already carried in $now for readability.
#
# $TZ comes first because `date` obeys it while timedatectl reports the system
# zone regardless; consulting the system zone under an override would print a
# name that contradicts the offset beside it, which is the exact failure this
# hook exists to prevent.
zone=""
if [[ -n "${TZ:-}" ]]; then
    zone=${TZ#:}
    [[ $zone == */zoneinfo/* ]] && zone=${zone##*/zoneinfo/}
else
    zone=$(timedatectl show -p Timezone --value 2>/dev/null) || zone=""
    if [[ -z "$zone" && -L /etc/localtime ]]; then
        target=$(readlink -f /etc/localtime 2>/dev/null) || target=""
        [[ $target == */zoneinfo/* ]] && zone=${target##*/zoneinfo/}
    fi
fi
[[ -n "$zone" ]] && zone="$zone, "

if [[ $offset =~ ^([+-])([0-9]{2})([0-9]{2})$ ]]; then
    sign=${BASH_REMATCH[1]}
    hours=$((10#${BASH_REMATCH[2]}))
    minutes=$((10#${BASH_REMATCH[3]}))
    if (( hours == 0 && minutes == 0 )); then
        delta="report UTC, which is local time here."
    else
        span="${hours}h"
        (( minutes )) && span="${span}${minutes}m"
        if [[ $sign == "-" ]]; then
            delta="report UTC, which runs $span ahead of local time here."
        else
            delta="report UTC, which runs $span behind local time here."
        fi
    fi
else
    delta="report UTC; run \`date -u\` alongside \`date\` to get the offset."
fi

emit_context "TIME: $what $now ($zone$offset).
Stack timestamps (git, docker, VPS cron, OptMem note dates, cloud APIs) $delta
That reading ages; for current wall-clock time, run \`date\`."
mark

exit 0
