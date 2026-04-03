#!/usr/bin/env bash
# Warn when Write creates a file with CRLF line endings in Linux-deployed extensions.
# Event: PostToolUse (Write)
# Config: {"hooks":{"PostToolUse":[{"matcher":{"tool_name":"Write"},"hooks":[{"type":"command","command":"hooks/quality-crlf-check.sh"}]}]}}

stdinContent=""
if [ ! -t 0 ]; then
    stdinContent=$(cat)
fi
[ -z "$stdinContent" ] && exit 0

data=$(echo "$stdinContent" | jq '.' 2>/dev/null) || exit 0

filePath=$(echo "$data" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$filePath" ] && exit 0

ext="${filePath##*.}"
ext=$(echo ".$ext" | tr '[:upper:]' '[:lower:]')
case "$ext" in
    .sh|.py|.conf|.yml|.yaml|.toml|.service|.env|.nginx) ;;
    *) exit 0 ;;
esac

if [[ "$filePath" != /* ]]; then
    filePath="$(pwd)/$filePath"
fi
[ -f "$filePath" ] || exit 0

if grep -qP '\r\n' "$filePath" 2>/dev/null; then
    fileName=$(basename "$filePath")
    echo "CRLF WARNING: $fileName contains Windows line endings (\\r\\n). Strip with: sed -i 's/\\r\$//' '$filePath'"
fi

exit 0
