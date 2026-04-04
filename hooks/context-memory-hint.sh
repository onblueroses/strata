#!/usr/bin/env bash
# Surface relevant memory files based on prompt matching.
# Matches prompt against memory file descriptions and keywords (YAML frontmatter).
# Outputs matching filenames only (~20 tokens) - Claude reads full files if needed.
# Supports scope: (directory-scoped) and keywords: (short-term matching) fields.
# Uses turn-based cooldown: memories re-fire after COOLDOWN_TURNS if still relevant.
# Caches frontmatter per session with mtime validation.
# Event: UserPromptSubmit
# Config: {"hooks":{"UserPromptSubmit":[{"hooks":[{"type":"command","command":"hooks/context-memory-hint.sh","timeout":5000}]}]}}

STRATA_MEMORY_DIR="${STRATA_MEMORY_DIR:-$HOME/.claude/projects/*/memory}"
CWD=$(pwd)
COOLDOWN_TURNS=10
RS=$'\x1e'

hookData=""
if [ ! -t 0 ]; then
    hookData=$(cat)
fi

prompt=$(echo "$hookData" | jq -r '.prompt // empty' 2>/dev/null)
[ -z "$prompt" ] && exit 0
prompt_lower="${prompt,,}"

# Session state + cache files
sessionId="default"
sid=$(echo "$hookData" | jq -r '.session_id // empty' 2>/dev/null)
[ -n "$sid" ] && sessionId="${sid:0:8}"
stateFile="/tmp/claude-memory-hint-$sessionId.state"
cacheFile="/tmp/claude-memory-hint-$sessionId.cache"

# Increment turn counter (first line of state file)
if [ -f "$stateFile" ]; then
    turn=$(head -1 "$stateFile")
    turn=$((turn + 1))
    sed -i "1s/.*/$turn/" "$stateFile"
else
    turn=1
    echo "$turn" > "$stateFile"
fi

# Tokenize prompt into associative array (bash builtins, no subshells)
prompt_normalized="${prompt_lower//[^a-z0-9]/ }"
declare -A prompt_words
has_short=0
for pw in $prompt_normalized; do
    if [ ${#pw} -ge 4 ]; then
        prompt_words[$pw]=1
    elif [ ${#pw} -ge 3 ]; then
        has_short=1
    fi
done
[ ${#prompt_words[@]} -eq 0 ] && [ "$has_short" -eq 0 ] && exit 0

STOPWORDS=":always:before:between:during:handle:itself:really:return:should:within:already:another:because:however:nothing:through:without:"

# Load frontmatter cache into associative arrays
declare -A cached_desc cached_scope cached_kw cached_mtime
if [ -f "$cacheFile" ]; then
    while IFS="$RS" read -r name desc scope kw mtime; do
        cached_desc[$name]="$desc"
        cached_scope[$name]="$scope"
        cached_kw[$name]="$kw"
        cached_mtime[$name]="$mtime"
    done < "$cacheFile"
fi

# Load cooldown state into associative array (avoid per-file grep)
declare -A cooldown_turn
while IFS=: read -r name fired; do
    [ -n "$fired" ] && cooldown_turn[$name]="$fired"
done < <(tail -n +2 "$stateFile" 2>/dev/null)

cache_dirty=0
matches=()

# Expand STRATA_MEMORY_DIR glob and iterate
for memDir in $STRATA_MEMORY_DIR; do
    [ -d "$memDir" ] || continue

    for memFile in "$memDir"/*.md; do
        [ -f "$memFile" ] || continue
        memName="${memFile##*/}"
        [[ "$memName" == "MEMORY.md" ]] && continue

        # Cooldown check (from preloaded array, no subshell)
        lastFired="${cooldown_turn[$memName]}"
        if [ -n "$lastFired" ] && [ $((turn - lastFired)) -lt "$COOLDOWN_TURNS" ]; then
            continue
        fi

        # Frontmatter: use cache if mtime matches, else extract via awk
        fileMtime=$(stat -c %Y "$memFile" 2>/dev/null || stat -f %m "$memFile" 2>/dev/null)
        if [ -n "${cached_mtime[$memName]}" ] && [ "${cached_mtime[$memName]}" = "$fileMtime" ]; then
            desc="${cached_desc[$memName]}"
            scope="${cached_scope[$memName]}"
            keywords="${cached_kw[$memName]}"
        else
            IFS="$RS" read -r desc scope keywords < <(awk '
                { gsub(/\r/, "") }
                /^---$/ { n++; next }
                n==1 && /^description:/ { sub(/^description: */, ""); gsub(/^["'"'"'"]|["'"'"'"]$/, ""); desc=$0 }
                n==1 && /^scope:/ { sub(/^scope: */, ""); gsub(/^["'"'"'"]|["'"'"'"]$/, ""); scope=$0 }
                n==1 && /^keywords:/ { sub(/^keywords: */, ""); gsub(/^["'"'"'"]|["'"'"'"]$/, ""); kw=$0 }
                n>=2 { printf "%s\x1e%s\x1e%s", desc, scope, kw; exit }
                END { if (n<2) printf "%s\x1e%s\x1e%s", desc, scope, kw }
            ' "$memFile")
            cached_desc[$memName]="$desc"
            cached_scope[$memName]="$scope"
            cached_kw[$memName]="$keywords"
            cached_mtime[$memName]="$fileMtime"
            cache_dirty=1
        fi

        [ -z "$desc" ] && continue

        # Scope check
        if [ -n "$scope" ]; then
            [[ "$scope" != */ ]] && scope="$scope/"
            [[ "$CWD/" != "$scope"* ]] && continue
        fi

        matched=0

        # Keyword matching (3+ chars, exact word boundary)
        if [ -n "$keywords" ]; then
            kw_lower="${keywords,,}"
            kw_normalized="${kw_lower//[^a-z0-9]/ }"
            for kw in $kw_normalized; do
                [ ${#kw} -lt 3 ] && continue
                if [[ " $prompt_normalized " == *" $kw "* ]]; then
                    matched=1; break
                fi
            done
        fi

        # Description matching (bidirectional substring, 6+ char gate)
        if [ "$matched" -eq 0 ]; then
            desc_lower="${desc,,}"
            desc_normalized="${desc_lower//[^a-z0-9]/ }"
            for dw in $desc_normalized; do
                [ ${#dw} -lt 4 ] && continue
                [[ "$STOPWORDS" == *":$dw:"* ]] && continue

                for pw in "${!prompt_words[@]}"; do
                    if { [[ "$dw" == *"$pw"* ]] || [[ "$pw" == *"$dw"* ]]; } && \
                       { [ ${#dw} -ge 6 ] || [ ${#pw} -ge 6 ]; }; then
                        matched=1
                        break 2
                    fi
                done
            done
        fi

        [ "$matched" -eq 1 ] && matches+=("$memName")
    done
done

# Write cache if anything changed
if [ "$cache_dirty" -eq 1 ]; then
    : > "$cacheFile"
    for name in "${!cached_desc[@]}"; do
        printf '%s\x1e%s\x1e%s\x1e%s\x1e%s\n' \
            "$name" "${cached_desc[$name]}" "${cached_scope[$name]}" "${cached_kw[$name]}" "${cached_mtime[$name]}" \
            >> "$cacheFile"
    done
fi

[ ${#matches[@]} -eq 0 ] && exit 0

# Record fired turn
for m in "${matches[@]}"; do
    sed -i "/^${m}:/d" "$stateFile" 2>/dev/null
    echo "$m:$turn" >> "$stateFile"
done

echo "MEMORY HINT: Possibly relevant memories: ${matches[*]}"
exit 0
