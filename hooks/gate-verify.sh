#!/usr/bin/env bash
# Block stop if files were edited but /verify not run. Skip-tier auto-passes safe files.
# Event: Stop
# Config: {"hooks":{"Stop":[{"hooks":[{"type":"command","command":"hooks/gate-verify.sh"}]}]}}
#
# Skip-tier auto-pass: if ALL edited files are safe (documentation, config,
# specs, memory), the hook writes the marker itself so /verify never needs to run.

STRATA_STATE_DIR="${STRATA_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/strata}"

# Read session info from stdin
sessionId="default"
jsonInput=""
if [ ! -t 0 ]; then
    jsonInput=$(cat)
fi
if [ -n "$jsonInput" ]; then
    sid=$(echo "$jsonInput" | jq -r '.session_id // empty' 2>/dev/null)
    if [ -n "$sid" ]; then
        sessionId="${sid:0:8}"
    fi
fi

editsFile="$STRATA_STATE_DIR/.session-edits-$sessionId"
verifyFile="$STRATA_STATE_DIR/.verify-passed-$sessionId"

# No edits this session? Pass through silently.
[ -f "$editsFile" ] || exit 0

# Read non-empty lines
mapfile -t editLines < <(grep -v '^\s*$' "$editsFile" 2>/dev/null)
editCount=${#editLines[@]}
[ "$editCount" -eq 0 ] && exit 0

# Skip-tier auto-pass: check if ALL edited files are safe (no code, no runtime config).
allSkipSafe=true
for line in "${editLines[@]}"; do
    p=$(echo "$line" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    isSkip=false

    # .claude/commands/**/*.md - skill definitions
    if echo "$p" | grep -qE '/\.claude/commands/.*\.md$'; then
        isSkip=true
    # .claude/hooks/** - hook scripts
    elif echo "$p" | grep -qE '/\.claude/hooks/'; then
        isSkip=true
    # .claude/memory/** - memory files
    elif echo "$p" | grep -qE '/\.claude/memory/'; then
        isSkip=true
    # .claude/reference/**/*.md - reference docs
    elif echo "$p" | grep -qE '/\.claude/reference/.*\.md$'; then
        isSkip=true
    # **/CLAUDE.md - project instructions
    elif echo "$p" | grep -qE '(^|/)CLAUDE\.md$'; then
        isSkip=true
    # **/*.md in common doc directories (docs/, doc/, wiki/, notes/)
    elif echo "$p" | grep -qE '/(docs|doc|wiki|notes)/.*\.md$'; then
        isSkip=true
    # README, CHANGELOG, LICENSE at any level
    elif echo "$p" | grep -qE '(^|/)(README|CHANGELOG|LICENSE|CONTRIBUTING)\.(md|txt)$'; then
        isSkip=true
    # Shell dotfiles in home dir
    elif echo "$p" | grep -qE "^$HOME/\.(bashrc|zshrc|profile|bash_profile|zshenv|zprofile)$"; then
        isSkip=true
    # State dir files (specs, save files, event logs)
    elif [[ "$p" == "$STRATA_STATE_DIR"/* ]]; then
        isSkip=true
    fi

    if ! $isSkip; then
        allSkipSafe=false
        break
    fi
done

if $allSkipSafe; then
    # Auto-write marker - no /verify invocation needed
    mkdir -p "$STRATA_STATE_DIR"
    printf '%s' "$(date +%Y-%m-%dT%H:%M:%S)" > "$verifyFile"
    exit 0
fi

# Non-skip edits: check for verification marker
if [ ! -f "$verifyFile" ]; then
    echo "VERIFICATION REQUIRED: You edited $editCount files this session but /verify has not passed. Run /verify before completing your response." >&2
    exit 2
fi

# Check timestamp: if edits file is newer than verify marker, re-verify needed
if [ "$editsFile" -nt "$verifyFile" ]; then
    echo "FILES EDITED AFTER VERIFICATION: The session edits file was modified after /verify last passed. Re-run /verify." >&2
    exit 2
fi

# Verification passed and is current
exit 0
