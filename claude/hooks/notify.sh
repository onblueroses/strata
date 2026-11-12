#!/usr/bin/env bash
# Desktop toast for the Notification and Stop hooks.
#
# The summary line names the conversation: with several sessions open, "Turn finished" over a
# directory name did not say which one (every home session read the account name). The name is the
# transcript's newest title row, a /rename title or the generated one.
#
# One jq call reads the event. Every path exits 0: a toast is never worth a hook error.

command -v notify-send >/dev/null 2>&1 || exit 0
data=""
[ -t 0 ] || data=$(cat)

event="" cwd="" message="" kind="" transcript=""
if [ -n "$data" ]; then
    IFS=$'\x1f' read -r -d '' event cwd message kind transcript < <(
        printf '%s' "$data" | jq -j '[.hook_event_name, .cwd, .message, .notification_type, .transcript_path]
            | map(. // "" | tostring) | join("\u001f") + "\u0000"' 2>/dev/null)
fi

case "$kind" in
    permission_prompt) label="Permission required"; urgency=critical ;;
    idle_prompt)       label="Waiting for input";   urgency=normal ;;
    ?*)                label="Claude Code";         urgency=low ;;
    *)  urgency=normal
        if [ "$event" = Stop ]; then label="Turn finished"; else label="Claude Code"; fi ;;
esac

# Title rows recur through a transcript, so the tail nearly always holds one; the head is the
# fallback for a turn that wrote more than the tail window since the last title.
title=""
if [ -n "$transcript" ] && [ -r "$transcript" ]; then
    row=$(tail -c 400000 -- "$transcript" 2>/dev/null | grep -a -E '^\{"type":"(ai|custom)-title"' | tail -1)
    [ -n "$row" ] || row=$(head -c 2000000 -- "$transcript" 2>/dev/null | grep -a -E '^\{"type":"(ai|custom)-title"' | tail -1)
    [ -z "$row" ] || title=$(printf '%s' "$row" | jq -r '.customTitle // .aiTitle // empty' 2>/dev/null)
fi

where=""
if [ -n "$cwd" ]; then
    where=$(basename -- "$cwd")
    branch=$(git -C "$cwd" rev-parse --abbrev-ref HEAD 2>/dev/null)
    [ -z "$branch" ] || where="$where [$branch]"
fi

summary="$label"
[ -z "$title" ] || summary="${title:0:60}: $label"
body="$message"
[ -z "$where" ] || body="${body:+$body
}$where"

notify-send --urgency="$urgency" -- "$summary" "$body" 2>/dev/null
exit 0
