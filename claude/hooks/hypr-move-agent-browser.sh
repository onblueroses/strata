#!/usr/bin/env bash
# PostToolUse hook: moves ONLY newly spawned browser windows to the terminal's workspace.
# Compares current browser windows against the pre-snapshot to find new ones.
# Never touches browser windows that existed before the MCP tool ran.

stdinContent=""
if [ ! -t 0 ]; then
    stdinContent=$(cat)
fi
[ -z "$stdinContent" ] && exit 0

# Bail if Hyprland isn't running
[ -z "$HYPRLAND_INSTANCE_SIGNATURE" ] && exit 0

# Find this terminal's workspace by walking PID tree
target_ws=""
clients=$(hyprctl -j clients 2>/dev/null) || exit 0
pid=$$
while [[ $pid -gt 1 ]]; do
    ws=$(echo "$clients" | jq --argjson p "$pid" '[.[] | select(.pid == $p)][0].workspace.id // empty')
    if [[ -n "$ws" && "$ws" != "null" ]]; then
        target_ws="$ws"
        break
    fi
    pid=$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')
    [[ -z "$pid" ]] && break
done
[ -z "$target_ws" ] && exit 0

snapshot="/tmp/claude-browser-pre-snapshot"

# Get all current browser addresses
current_browsers=$(echo "$clients" | jq -r '[.[] | select(.class | test("chrom|firefox|brave"; "i")) | .address] | .[]')

if [[ -f "$snapshot" ]]; then
    # Find browser addresses that are NEW (not in the pre-snapshot)
    new_browsers=$(comm -23 <(echo "$current_browsers" | sort) <(sort "$snapshot"))
else
    # No snapshot - fall back to only moving browsers already on our workspace
    # (i.e., do nothing, since they're already here)
    new_browsers=""
fi

# Move only new browser windows to our workspace (if they're not already here)
while IFS= read -r addr; do
    [[ -z "$addr" ]] && continue
    # Check if this window is already on our workspace
    on_ws=$(echo "$clients" | jq -r --arg a "$addr" --argjson ws "$target_ws" \
        '[.[] | select(.address == $a) | select(.workspace.id != $ws)] | length')
    if [[ "$on_ws" -gt 0 ]]; then
        hyprctl dispatch movetoworkspacesilent "$target_ws,address:$addr" 2>/dev/null
    fi
done <<< "$new_browsers"

# Clean up snapshot
rm -f "$snapshot"

exit 0
