#!/usr/bin/env bash
# PreToolUse hook (Write only): gates a Write that would clobber a file another session
# recently edited. Write overwrites the entire file, so it's the one operation that can
# silently clobber another session's work (Edit is safe: exact-match fails on stale content).
# Emits the PreToolUse JSON contract permissionDecision:"ask" so the clobber guard actually
# surfaces as a confirm prompt — plain stdout on PreToolUse is invisible to the model.

stdinContent=""
if [ ! -t 0 ]; then
    stdinContent=$(cat)
fi
[ -z "$stdinContent" ] && exit 0

# Single jq call to extract all fields (IFS=tab to handle spaces in paths)
IFS=$'\t' read -r toolName filePath sid < <(echo "$stdinContent" | jq -r '[.tool_name // "", .tool_input.file_path // "", .session_id // ""] | join("\t")' 2>/dev/null) || exit 0

# Only guard Write, not Edit
[ "$toolName" != "Write" ] && exit 0
[ -z "$filePath" ] && exit 0

if [[ "$filePath" != /* ]]; then
    filePath="$(pwd)/$filePath"
fi

ownSessionId=""
[ -n "$sid" ] && ownSessionId="${sid:0:8}"

stateDir="$STATE_DIR"
now=$(date +%s)
owners=""

while IFS= read -r editFile; do
    [ -f "$editFile" ] || continue

    fname=$(basename "$editFile")
    sessionId="${fname#.session-edits-}"
    [ "$sessionId" = "$ownSessionId" ] && continue

    if grep -qxF "$filePath" "$editFile" 2>/dev/null; then
        mtime=$(stat -c %Y "$editFile" 2>/dev/null) || continue
        ageMin=$(( (now - mtime) / 60 ))
        owners+="session $sessionId (${ageMin}m ago), "
    fi
done < <(find "$stateDir" -maxdepth 1 -name '.session-edits-*' -not -name '*.jsonl' -mmin -60 2>/dev/null)

if [ -n "$owners" ]; then
    owners="${owners%, }"
    reason="Write to $filePath overwrites the entire file, which was also edited by: $owners. Confirm this won't clobber their work, or use Edit instead."
    emit=$(jq -n --arg r "$reason" \
        '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"ask",permissionDecisionReason:$r}}')
    printf '%s' "$emit" | bash "$STRATA_HOME/hooks/lib-ledger.sh" warn-file-ownership "$sid" >/dev/null 2>&1 || true
    printf '%s\n' "$emit"
fi

exit 0
