#!/usr/bin/env bash
# PreToolUse hook: snapshot current browser window addresses before MCP browser tool runs.
# The PostToolUse hook (hypr-move-agent-browser.sh) compares against this to only move
# genuinely NEW browser windows, leaving existing ones on their workspaces.

[ -z "$HYPRLAND_INSTANCE_SIGNATURE" ] && exit 0
if [ ! -t 0 ]; then cat > /dev/null; fi

hyprctl -j clients 2>/dev/null \
  | jq -r '[.[] | select(.class | test("chrom|firefox|brave"; "i")) | .address] | .[]' \
  > /tmp/claude-browser-pre-snapshot 2>/dev/null

exit 0
