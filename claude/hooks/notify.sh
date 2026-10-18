#!/usr/bin/env bash
# Claude Code Notification Script
# Parses hook JSON input for rich notifications via notify-send

# Parse arguments
title="Claude Code"
message=""
context=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        --title|-t) title="$2"; shift 2 ;;
        --message|-m) message="$2"; shift 2 ;;
        --context|-c) context="$2"; shift 2 ;;
        *) shift ;;
    esac
done

# Try to read JSON from stdin (hook data)
hookData=""
if [ ! -t 0 ]; then
    hookData=$(cat)
fi

# Extract information from hook data
displayTitle="$title"
displayMessage="$message"
urgency="normal"
projectName=""
gitBranch=""
workingDir="$context"
hookEvent=""

if [ -n "$hookData" ]; then
    hookEvent=$(echo "$hookData" | jq -r '.hook_event_name // empty' 2>/dev/null)
    # Get working directory
    cwdVal=$(echo "$hookData" | jq -r '.cwd // empty' 2>/dev/null)
    [ -n "$cwdVal" ] && workingDir="$cwdVal"

    # Get the actual message from hook
    msgVal=$(echo "$hookData" | jq -r '.message // empty' 2>/dev/null)
    [ -n "$msgVal" ] && displayMessage="$msgVal"

    # Route based on notification type (urgency + title)
    # Maps to Claude Code's typed notification system
    notifType=$(echo "$hookData" | jq -r '.notification_type // empty' 2>/dev/null)
    case "$notifType" in
        permission_prompt)
            displayTitle="Permission Required"
            urgency="critical"
            ;;
        idle_prompt)
            displayTitle="Waiting for Input"
            urgency="normal"
            ;;
        ?*)
            displayTitle="Claude Code"
            urgency="low"
            ;;
    esac
fi

# Get project/folder name
if [ -n "$workingDir" ]; then
    projectName=$(basename "$workingDir")

    # Try to get git branch
    gitBranch=$(git -C "$workingDir" rev-parse --abbrev-ref HEAD 2>/dev/null)
fi

# Build the notification text
# Default message when body would be empty (e.g., Stop hook with no .message field)
if [ -z "$displayMessage" ]; then
    if [ "$hookEvent" = "Stop" ]; then
        displayMessage="Turn finished"
    else
        displayMessage="Session activity"
    fi
fi
notificationBody="$displayMessage"

contextLine=""
[ -n "$projectName" ] && contextLine="$projectName"
[ -n "$gitBranch" ] && contextLine="$contextLine [$gitBranch]"
contextLine=$(echo "$contextLine" | sed 's/^[[:space:]]*//')

if [ -n "$contextLine" ]; then
    notificationBody="$notificationBody
$contextLine"
fi

# Show notification via notify-send
if command -v notify-send &>/dev/null; then
    notify-send --urgency="$urgency" "$displayTitle" "$notificationBody" 2>/dev/null
fi

exit 0
