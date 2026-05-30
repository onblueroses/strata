#!/usr/bin/env bash
# Stop hook: blocks Claude from stopping if files were edited but /verify hasn't passed.
# Must be first Stop hook (before sync-life-repo) so blocked stops don't trigger sync.
# Exit code 2 = block stop, stderr fed back to Claude as system message.
#
# Skip-tier auto-pass: if ALL edited files are safe (knowledge-base .md/.json,
# .claude/ config markdown, specs, memory), the hook writes the marker itself
# so /verify never needs to run.

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

stateDir="$STATE_DIR"
editsFile="$stateDir/.session-edits-$sessionId"
verifyFile="$stateDir/.verify-passed-$sessionId"

# Resolve the actual installed kernel + workspace paths for skip-safe matching.
# These get expanded into the regex below so the gate matches concrete edited paths
# rather than the literal placeholder strings.
strataHome="${STRATA_HOME:-$HOME/.strata}"
kbDir="${KB_DIR:-$HOME/strata-workspace}"
specsDir="${SPECS_DIR:-$stateDir/specs}"

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

    # $KB_DIR/**/*.md, $KB_DIR/**/*.json - knowledge base
    if [[ "$p" == "$kbDir"/*.md || "$p" == "$kbDir"/*.json || "$p" == "$kbDir"/*/*.md || "$p" == "$kbDir"/*/*.json ]]; then
        isSkip=true
    # $SPECS_DIR/** - spec files
    elif [[ "$p" == "$specsDir"/* ]]; then
        isSkip=true
    # $STRATA_HOME/skills/**/*.md or ~/.claude/skills/**/*.md (symlinked) - skill defs
    elif echo "$p" | grep -qE "($strataHome|/\.claude)/skills/.*\.md$"; then
        isSkip=true
    # $STRATA_HOME/commands/**/*.md or ~/.claude/commands/**/*.md - command defs
    elif echo "$p" | grep -qE "($strataHome|/\.claude)/commands/.*\.md$"; then
        isSkip=true
    # $STRATA_HOME/reference/**/*.md or ~/.claude/reference/**/*.md - reference docs
    elif echo "$p" | grep -qE "($strataHome|/\.claude)/reference/.*\.md$"; then
        isSkip=true
    # $STRATA_HOME/memory/** or ~/.claude/memory/** - memory files
    elif echo "$p" | grep -qE "($strataHome|/\.claude)/memory/"; then
        isSkip=true
    # **/CLAUDE.md - project instructions
    elif echo "$p" | grep -qE '(^|/)CLAUDE\.md$'; then
        isSkip=true
    # ~/.*rc, ~/.profile, ~/.bash_profile - shell dotfiles (init script edits)
    elif echo "$p" | grep -qE "^/home/[^/]+/\.(bashrc|zshrc|profile|bash_profile|zshenv|zprofile)$"; then
        isSkip=true
    fi
    # NOTE: hook scripts (.sh, .py) are intentionally NOT skip-safe; they affect runtime
    # and must run through /verify Light or Full tier.

    if ! $isSkip; then
        allSkipSafe=false
        break
    fi
done

if $allSkipSafe; then
    # Auto-write marker - no /verify invocation needed
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
