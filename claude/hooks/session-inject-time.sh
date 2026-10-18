#!/usr/bin/env bash
# SessionStart: the model's context carries a date but no clock and no zone, so
# any hour it states without shelling out is confabulated, and the attractor is
# UTC; git, docker, VPS cron, OptMem's gmtime stamps, and the Vast/Prime APIs
# all report it. Diagnosed 2026-08-05, when 17:57 UTC was reported as the local
# time against an actual 10:57 PDT.
#
# The durable fact is the zone, not the instant: an offset holds for the whole
# session, a timestamp decays within minutes. So the start time is labeled as a
# start time, where a stale reading cannot pass itself off as "now", and the
# last line names the way to get the real one. Offset and delta are computed,
# never written down, so DST and travel stay correct without an edit here.
#
# Measured 10 ms min / 12 ms median / 13 ms max over 10 runs on this laptop,
# timedatectl's dbus round trip dominating. The settings.json timeout is 3,000
# ms, matching the sibling session-* injectors and leaving room for a cold
# systemd bus; the payload is ~230 bytes, far under the 10,000-character
# SessionStart injection budget, so it needs no oversize path.

set -u

emit_context() {
    /usr/bin/jq -cn --arg context "$1" \
        '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$context}}'
}

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

emit_context "TIME: session started $now ($zone$offset).
Stack timestamps (git, docker, VPS cron, OptMem note dates, Vast/Prime) $delta
That start time ages; for current wall-clock time, run \`date\`."

exit 0
