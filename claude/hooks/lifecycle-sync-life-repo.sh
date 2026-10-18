#!/usr/bin/env bash
# Synchronize only life-repo paths owned by one Claude session.
set -uo pipefail

hookDir=$(cd "$(dirname -- "${BASH_SOURCE[0]}")" 2>/dev/null && pwd) || exit 0
lifeDir="${LIFE_SYNC_REPO:-$HOME/life}"
if [ "${LIFE_SYNC_SYNTHETIC:-0}" = 1 ] && [ -n "${LIFE_SYNC_REPO:-}" ]; then
    lifeDir=$LIFE_SYNC_REPO
fi
lifeDir=$(realpath -e -- "$lifeDir" 2>/dev/null) || exit 0
stateDir="$lifeDir/areas/claude-code-setup/state"
gitDir=$(git -C "$lifeDir" rev-parse --absolute-git-dir 2>/dev/null) || exit 0
markerDir="$gitDir/life-sync-sessions"
lockFile="$gitDir/life-sync.lock"

jsonInput=""
if [ ! -t 0 ]; then
    jsonInput=$(cat)
fi
[ -n "$jsonInput" ] || exit 0

eventName=$(printf '%s' "$jsonInput" | jq -r '.hook_event_name // empty' 2>/dev/null) || exit 0
case "$eventName" in
    SessionStart|SessionEnd) ;;
    *) exit 0 ;;
esac

sessionId=$(printf '%s' "$jsonInput" | jq -r '.session_id // empty' 2>/dev/null) || exit 0
sessionShort=${sessionId:0:8}
[[ $sessionShort =~ ^[[:alnum:]]{8}$ ]] || exit 0

mkdir -p -- "$markerDir" 2>/dev/null || exit 0

process_starttime() {
    local pid=$1 stat rest
    local -a fields=()
    [[ $pid =~ ^[0-9]+$ ]] || return 1
    [ -r "/proc/$pid/stat" ] || return 1
    IFS= read -r stat < "/proc/$pid/stat" || return 1
    rest=${stat##*) }
    read -r -a fields <<< "$rest"
    [ "${#fields[@]}" -ge 20 ] || return 1
    printf '%s\n' "${fields[19]}"
}

find_session_process() {
    local pid=$PPID comm cmdline parent
    if [ "${LIFE_SYNC_SYNTHETIC:-0}" = 1 ] && [ -n "${LIFE_SYNC_PROCESS_PID:-}" ]; then
        printf '%s\n' "$LIFE_SYNC_PROCESS_PID"
        return 0
    fi

    while [[ $pid =~ ^[0-9]+$ ]] && [ "$pid" -gt 1 ]; do
        comm=""
        cmdline=""
        [ -r "/proc/$pid/comm" ] && IFS= read -r comm < "/proc/$pid/comm"
        [ -r "/proc/$pid/cmdline" ] && cmdline=$(tr '\0' ' ' < "/proc/$pid/cmdline")
        if [[ $comm == claude || $comm == claude-* || " $cmdline " == *"/claude "* ]]; then
            printf '%s\n' "$pid"
            return 0
        fi
        parent=$(awk '/^PPid:/ {print $2}' "/proc/$pid/status" 2>/dev/null)
        [ -n "$parent" ] || break
        pid=$parent
    done
    return 1
}

markerPid=""
markerStart=""
markerState=""
markerSessionId=""

read_marker() {
    local marker=$1
    markerPid=""
    markerStart=""
    markerState=""
    markerSessionId=""
    [ -f "$marker" ] || return 1
    IFS=$'\t' read -r markerPid markerStart markerState markerSessionId < "$marker" || return 1
    [[ $markerPid =~ ^[0-9]+$ && $markerStart =~ ^[0-9]+$ ]] || return 1
    case "$markerState" in
        active|recorded|syncing|pending) ;;
        *) return 1 ;;
    esac
    [ -n "$markerSessionId" ] || return 1
}

marker_is_live() {
    local marker=$1 actualStart
    read_marker "$marker" || return 1
    actualStart=$(process_starttime "$markerPid") || return 1
    [ "$actualStart" = "$markerStart" ]
}

write_marker() {
    local sid=$1 fullId=$2 pid=$3 start=$4 state=$5
    local marker="$markerDir/$sid" temporary="$markerDir/.$sid.$$"
    (umask 077; printf '%s\t%s\t%s\t%s\n' "$pid" "$start" "$state" "$fullId" > "$temporary") || return 1
    mv -f -- "$temporary" "$marker"
}

set_marker_state() {
    local sid=$1 state=$2 marker="$markerDir/$1"
    read_marker "$marker" || return 1
    write_marker "$sid" "$markerSessionId" "$markerPid" "$markerStart" "$state"
}

register_current_session() {
    local marker="$markerDir/$sessionShort" priorState=active pid start
    recoverCurrent=false
    if read_marker "$marker"; then
        priorState=$markerState
        marker_is_live "$marker" || recoverCurrent=true
    fi

    pid=$(find_session_process) || {
        printf 'life sync: could not identify the Claude session process; crash recovery is unavailable\n' >&2
        return 1
    }
    start=$(process_starttime "$pid") || return 1
    write_marker "$sessionShort" "$sessionId" "$pid" "$start" "$priorState"
}

normalizedPath=""
normalize_life_path() {
    local raw=$1 absolute
    normalizedPath=""
    [[ $raw == /* ]] || return 1
    absolute=$(realpath -m -s -- "$raw" 2>/dev/null) || return 1
    case "$absolute" in
        "$lifeDir"/.git|"$lifeDir"/.git/*) return 1 ;;
        "$lifeDir"/*) normalizedPath=${absolute#"$lifeDir"/} ;;
        *) return 1 ;;
    esac
    [ -n "$normalizedPath" ]
}

ensure_session_record() {
    local sid=$1 fullId=$2 marker="$markerDir/$1" payload
    local state=active hasMarker=false
    if read_marker "$marker"; then
        state=$markerState
        hasMarker=true
    fi
    [ "$state" = active ] || return 0

    # Session-record witness retired 2026-09-01 (lean-out): an active session transitions to
    # recorded directly; the sync no longer waits on a gate that no longer exists.
    if $hasMarker; then
        set_marker_state "$sid" recorded || return 1
    fi
    return 0
}

sync_session() {
    local sid=$1 mode=$2 marker="$markerDir/$1" ledger="$stateDir/.session-edits-$1"
    local state=recorded raw otherMarker otherSid otherLedger stagedPath message statusOutput statusRc stagedOutput
    local unresolved=false needsPush=false
    local -a ownedPaths=() stagedPaths=()
    local -A activePaths=() ownedSet=()

    if read_marker "$marker"; then
        state=$markerState
    fi

    shopt -s nullglob
    for otherMarker in "$markerDir"/*; do
        otherSid=$(basename -- "$otherMarker")
        [[ $otherSid =~ ^[[:alnum:]]{8}$ ]] || continue
        [ "$otherSid" != "$sid" ] || continue
        marker_is_live "$otherMarker" || continue
        otherLedger="$stateDir/.session-edits-$otherSid"
        [ -f "$otherLedger" ] || continue
        while IFS= read -r raw || [ -n "$raw" ]; do
            normalize_life_path "$raw" || continue
            activePaths["$normalizedPath"]=1
        done < "$otherLedger"
    done
    shopt -u nullglob

    if [ -f "$ledger" ]; then
        while IFS= read -r raw || [ -n "$raw" ]; do
            normalize_life_path "$raw" || continue
            if [ -n "${activePaths[$normalizedPath]+x}" ]; then
                unresolved=true
                continue
            fi
            if [ -z "${ownedSet[$normalizedPath]+x}" ]; then
                ownedSet["$normalizedPath"]=1
                ownedPaths+=("$normalizedPath")
            fi
        done < "$ledger"
    fi

    if [ "$state" != active ]; then
        normalize_life_path "$stateDir/end-debt.jsonl" || true
        if [ -n "$normalizedPath" ] && \
            { [ -e "$lifeDir/$normalizedPath" ] || git -C "$lifeDir" ls-files --error-unmatch -- "$normalizedPath" >/dev/null 2>&1; } && \
            [ -z "${ownedSet[$normalizedPath]+x}" ]; then
            ownedSet["$normalizedPath"]=1
            ownedPaths+=("$normalizedPath")
        fi
    fi

    if [ "${#ownedPaths[@]}" -gt 0 ]; then
        statusOutput=$(git -C "$lifeDir" status --porcelain=v1 -- "${ownedPaths[@]}" 2>/dev/null)
        statusRc=$?
        if [ "$statusRc" -ne 0 ]; then
            printf 'life sync: Git status failed; session %s remains pending\n' "$sid" >&2
            return 1
        fi
        if [ -n "$statusOutput" ]; then
            if ! git -C "$lifeDir" diff --cached --quiet --exit-code; then
                printf 'life sync: preserving a non-empty index; session %s remains pending\n' "$sid" >&2
                return 1
            fi

            if [ -f "$marker" ]; then
                set_marker_state "$sid" syncing || return 1
            fi
            git -C "$lifeDir" add -A -- "${ownedPaths[@]}" || return 1
            stagedOutput=$(git -C "$lifeDir" diff --cached --name-only)
            statusRc=$?
            if [ "$statusRc" -ne 0 ]; then
                git -C "$lifeDir" reset --quiet HEAD -- "${ownedPaths[@]}" 2>/dev/null || true
                return 1
            fi
            if [ -n "$stagedOutput" ]; then
                mapfile -t stagedPaths <<< "$stagedOutput"
            fi
            for stagedPath in "${stagedPaths[@]}"; do
                if [ -z "${ownedSet[$stagedPath]+x}" ]; then
                    printf 'life sync: index changed concurrently; session %s remains pending\n' "$sid" >&2
                    git -C "$lifeDir" reset --quiet HEAD -- "${ownedPaths[@]}" 2>/dev/null || true
                    return 1
                fi
            done

            if [ "$mode" = recovery ]; then
                message="Recover interrupted life session changes"
            else
                message="Synchronize life session changes"
            fi
            if ! git -C "$lifeDir" commit --quiet --only -m "$message" -- "${ownedPaths[@]}"; then
                git -C "$lifeDir" reset --quiet HEAD -- "${ownedPaths[@]}" 2>/dev/null || true
                return 1
            fi
            needsPush=true
            set_marker_state "$sid" pending || true
            if [ "${LIFE_SYNC_SYNTHETIC:-0}" = 1 ] && [ "${LIFE_SYNC_FAIL_AFTER_COMMIT:-0}" = 1 ]; then
                return 91
            fi
        fi
    fi

    case "$state" in
        syncing|pending) needsPush=true ;;
    esac
    if $needsPush; then
        git -C "$lifeDir" push --quiet || return 1
    fi

    if $unresolved; then
        set_marker_state "$sid" recorded || true
        return 1
    fi

    rm -f -- "$marker" 2>/dev/null || true
    return 0
}

recoverCurrent=false
register_current_session || true

exec 9> "$lockFile" || exit 0
flock -n 9 || exit 0

prepare_and_sync() {
    local sid=$1 fullId=$2 mode=$3 rc
    ensure_session_record "$sid" "$fullId" || return 1
    sync_session "$sid" "$mode"
    rc=$?
    [ "$rc" -ne 91 ] || return 91
    return "$rc"
}

if [ "$eventName" = SessionEnd ]; then
    prepare_and_sync "$sessionShort" "$sessionId" normal
    rc=$?
    [ "$rc" -ne 91 ] || exit 91
    exit 0
fi

if $recoverCurrent && [ -f "$markerDir/$sessionShort" ]; then
    if read_marker "$markerDir/$sessionShort"; then
        priorFullId=$markerSessionId
        prepare_and_sync "$sessionShort" "$priorFullId" recovery
        rc=$?
        [ "$rc" -ne 91 ] || exit 91
        if [ "$rc" -eq 0 ]; then
            pid=$(find_session_process) || pid=""
            if [ -n "$pid" ]; then
                start=$(process_starttime "$pid") || start=""
                [ -n "$start" ] && write_marker "$sessionShort" "$sessionId" "$pid" "$start" recorded
            fi
        fi
    fi
fi

shopt -s nullglob
for marker in "$markerDir"/*; do
    sid=$(basename -- "$marker")
    [[ $sid =~ ^[[:alnum:]]{8}$ ]] || continue
    [ "$sid" != "$sessionShort" ] || continue
    marker_is_live "$marker" && continue
    read_marker "$marker" || continue
    fullId=$markerSessionId
    prepare_and_sync "$sid" "$fullId" recovery
    rc=$?
    [ "$rc" -ne 91 ] || exit 91
done
shopt -u nullglob

exit 0
