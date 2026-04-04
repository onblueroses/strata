#!/usr/bin/env bash
# Route reference docs into context based on prompt keyword matching.
# Scans reference docs for <!-- keywords: ... --> comments, matches against
# the user's prompt, and injects Quick Nav sections of matched docs.
# Fires once per doc per session (deduplication via session flag file).
# Event: UserPromptSubmit
# Config: {"hooks":{"UserPromptSubmit":[{"hooks":[{"type":"command","command":"hooks/context-doc-router.sh","timeout":5000}]}]}}

STRATA_STATE_DIR="${STRATA_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/strata}"
STRATA_REFS_DIR="${STRATA_REFS_DIR:-$STRATA_STATE_DIR/reference}"

# To mark specific docs as mandatory (always shown with a warning banner),
# uncomment and edit the following line:
# MANDATORY_DOCS=("your-critical-doc.md" "another-important-doc.md")
MANDATORY_DOCS=()

hookData=""
if [ ! -t 0 ]; then
    hookData=$(cat)
fi

# Extract prompt and session ID
prompt=$(echo "$hookData" | jq -r '.prompt // empty' 2>/dev/null)
if [ -z "$prompt" ]; then
    exit 0
fi
prompt_lower=$(echo "$prompt" | tr '[:upper:]' '[:lower:]')

sessionId="default"
sid=$(echo "$hookData" | jq -r '.session_id // empty' 2>/dev/null)
if [ -n "$sid" ]; then
    sessionId="${sid:0:8}"
fi

flagFile="/tmp/claude-doc-router-$sessionId.txt"
touch "$flagFile" 2>/dev/null

# Exit early if no reference docs directory
if [ ! -d "$STRATA_REFS_DIR" ]; then
    exit 0
fi

# Scan reference docs for keyword matches
new_matches=()
for docFile in "$STRATA_REFS_DIR"/*.md; do
    [ -f "$docFile" ] || continue
    docName=$(basename "$docFile")
    [[ "$docName" == "INDEX.md" ]] && continue

    # Already suggested this session?
    if grep -qF "$docName" "$flagFile" 2>/dev/null; then
        continue
    fi

    # Extract keywords comment (must be on one of the first 5 lines)
    keywords_line=$(head -5 "$docFile" | grep '<!-- keywords:' | head -1)
    if [ -z "$keywords_line" ]; then
        continue
    fi

    # Parse: <!-- keywords: foo, bar, baz --> -> "foo, bar, baz"
    keywords=$(echo "$keywords_line" | sed 's/<!--[[:space:]]*keywords:[[:space:]]*//' | sed 's/[[:space:]]*-->//')

    # Check each keyword against the prompt
    matched=0
    IFS=',' read -ra kw_array <<< "$keywords"
    for kw in "${kw_array[@]}"; do
        kw_trimmed=$(echo "$kw" | sed 's/^[[:space:]]*//' | sed 's/[[:space:]]*$//')
        if [ -z "$kw_trimmed" ]; then
            continue
        fi
        # Skip keywords shorter than 6 chars to avoid false positives
        if [ ${#kw_trimmed} -lt 6 ]; then
            continue
        fi
        if echo "$prompt_lower" | grep -qiF "$kw_trimmed"; then
            matched=1
            break
        fi
    done

    if [ "$matched" -eq 1 ]; then
        new_matches+=("$docName")
    fi
done

# No new matches - exit silently
if [ ${#new_matches[@]} -eq 0 ]; then
    exit 0
fi

# Append new matches to flag file
for doc in "${new_matches[@]}"; do
    echo "$doc" >> "$flagFile"
done

# Extract Quick Nav section from a doc file (stdout)
extract_quick_nav() {
    local docFile="$1"
    awk '
        /^## Quick Nav/ { found=1; next }
        found && /^## / { exit }
        found { print }
    ' "$docFile" | head -40 | sed -e '/^[[:space:]]*$/{ /./!d }' | head -40
}

# Check if doc is in mandatory list
is_mandatory() {
    local docName="$1"
    for m in "${MANDATORY_DOCS[@]}"; do
        [[ "$m" == "$docName" ]] && return 0
    done
    return 1
}

# Build output
output="REFERENCE DOCS: The following docs are relevant to this task. Read Quick Nav, then load relevant sections.\n"

for doc in "${new_matches[@]}"; do
    docFile="$STRATA_REFS_DIR/$doc"
    if is_mandatory "$doc"; then
        output+="\n=== $doc === [MANDATORY - read before writing any code]\n"
    else
        output+="\n=== $doc ===\n"
    fi

    nav=$(extract_quick_nav "$docFile")
    if [ -n "$nav" ]; then
        output+="$nav\n"
    else
        output+="(no Quick Nav - read full doc)\n"
    fi
done

printf '%b' "$output"
exit 0
