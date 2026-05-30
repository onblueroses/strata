#!/usr/bin/env bash
# PreToolUse hook (Write only): warns if another session recently edited this file.
# Write overwrites the entire file, so it's the one operation that can silently
# clobber another session's work. Edit is safe (exact-match fails on stale content).

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
    echo "WARNING: Write to $filePath will overwrite the entire file. Also edited by: $owners. Consider using Edit instead to avoid clobbering their changes."
fi

exit 0
