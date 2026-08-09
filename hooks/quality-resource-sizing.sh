#!/usr/bin/env bash
# quality-resource-sizing.sh - PostToolUse(Edit|Write) advisory hook.
# Detects the *silence* in performance choices; never blocks (always exit 0).
#
# It does NOT judge whether a number is optimal (impossible per-case). It detects
# floor values of throughput scalars (num_workers/batch/concurrency = 0|1, etc.),
# the fingerprint of an unmade decision: nobody reasons their way to num_workers=0
# on a 16-core box; you get there by accepting the library default. It also flags
# DataLoader() calls with no num_workers and swallowed exceptions (same
# loud-over-silent family; ruff catches some of the latter too).
#
# Scope: flags only tells in *newly written / changed* content (Edit -> the edit's
# new_string; Write -> the whole file), so unrelated edits do not re-flag old lines.
# An inline comment that *names the basis* (e.g. `batch_size=1  # VRAM-bound, 4k docs`)
# silences the line; a bare `# ok` does not. Skips vendored/generated/test paths.
# Output: JSON hookSpecificOutput.additionalContext (non-blocking, model sees it).
# Rationale: reference/resource-sizing.md.
#
# Config: PostToolUse matcher "Edit|Write". Input: hook JSON on stdin
# (tool_input.file_path, tool_name, tool_input.new_string / .edits[].new_string).
# Advisory only: fails OPEN on any infra error (warn to stderr, exit 0).
set -uo pipefail

stdinContent=""
if [ ! -t 0 ]; then
    stdinContent=$(cat)
fi
[ -z "$stdinContent" ] && exit 0

# Fail open on infra problems: without jq we cannot parse, so stay silent rather than block.
if ! command -v jq >/dev/null 2>&1; then
    echo "quality-resource-sizing: jq unavailable, skipping advisory" >&2
    exit 0
fi

data=$(echo "$stdinContent" | jq '.' 2>/dev/null) || exit 0
filePath=$(echo "$data" | jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "$filePath" ] && exit 0
[[ "$filePath" != /* ]] && filePath="$(pwd)/$filePath"
[ -f "$filePath" ] || exit 0

# skip vendored / generated / test paths (noise the directive owns, not the hook)
case "$filePath" in
    */node_modules/*|*/dist/*|*/build/*|*/.next/*|*/.venv/*|*/venv/*|*/site-packages/*|*/vendor/*|*/__pycache__/*) exit 0 ;;
    *.min.js|*.min.ts|*.bundle.js) exit 0 ;;
    */tests/*|*/test/*|*_test.*|*/test_*|*.test.*|*.spec.*) exit 0 ;;
esac

ext="${filePath##*.}"
ext=$(echo "$ext" | tr '[:upper:]' '[:lower:]')

# changed-content scope: for Edit/MultiEdit only the new text is "new"; Write = whole file.
toolName=$(echo "$data" | jq -r '.tool_name // empty' 2>/dev/null)
case "$toolName" in
    Edit)      NEWCONTENT=$(echo "$data" | jq -r '.tool_input.new_string // ""' 2>/dev/null) ;;
    MultiEdit) NEWCONTENT=$(echo "$data" | jq -r '[.tool_input.edits[]?.new_string] | join("\n")' 2>/dev/null) ;;
    *)         NEWCONTENT="__ALL__" ;;
esac

hits=()

# A line counts as justified only if its inline comment names a real basis:
# non-empty, >= 12 chars, and not a vacuous token (ok/todo/fixme/noqa/...).
justified() {
    local code="$1" marker="$2" comment lc
    [[ "$code" != *"$marker"* ]] && return 1
    comment="${code#*$marker}"
    comment="$(echo "$comment" | sed 's/^[^[:alnum:]]*//;s/[[:space:]]*$//')"
    [ ${#comment} -lt 12 ] && return 1
    lc="$(echo "$comment" | tr '[:upper:]' '[:lower:]')"
    echo "$lc" | grep -qE '^(ok|okay|todo|fixme|hack|temp|tmp|wip|noqa|fine|ignore|skip|nvm|n/?a|x+|\?+)\b' && return 1
    return 0
}

is_new() {
    [ "$NEWCONTENT" = "__ALL__" ] && return 0
    [[ "$NEWCONTENT" == *"$1"* ]] && return 0
    return 1
}

# grep-based tell collector (floor scalars, swallowed excepts)
collect() {
    local pattern="$1" marker="$2" lineno code
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        lineno="${line%%:*}"
        code="${line#*:}"
        code="$(echo "$code" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
        justified "$code" "$marker" && continue
        is_new "$code" || continue
        hits+=("  L${lineno}: ${code}")
    done < <(grep -nE "$pattern" "$filePath" 2>/dev/null)
}

case ".$ext" in
    .py)
        collect '\b(num_workers|max_workers|n_jobs|workers|concurrency|max_concurrency|parallelism|n_parallel|max_parallel)\s*=\s*[01]\b' '#'
        collect '\bbatch_size\s*=\s*1\b' '#'
        # DataLoader() with no num_workers anywhere in the (possibly multi-line, nested-paren) call
        while IFS=$'\t' read -r ln code; do
            [ -z "$ln" ] && continue
            code="$(echo "$code" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
            justified "$code" '#' && continue
            is_new "$code" || continue
            hits+=("  L${ln}: ${code} (DataLoader without num_workers -> single process)")
        done < <(awk '
            function cntopen(s,  t){ t=s; return gsub(/\(/,"(",t) }
            function cntclose(s,  t){ t=s; return gsub(/\)/,")",t) }
            { lines[NR]=$0 }
            END {
                for (i=1;i<=NR;i++){
                    p=index(lines[i],"DataLoader(")
                    if (p>0){
                        span=substr(lines[i],p); j=i
                        while (cntclose(span) < cntopen(span) && j<NR){ j++; span=span " " lines[j] }
                        if (span !~ /num_workers/) print i"\t"lines[i]
                    }
                }
            }' "$filePath" 2>/dev/null)
        # swallowed exceptions on a BROAD catch only: bare `except:`, `except Exception:`,
        # `except BaseException:` (with optional `as e`). A specific exception class with
        # pass/continue (e.g. `except json.JSONDecodeError: continue`) is an intentional skip
        # and stays silent. (ruff E722/S110/SIM105 overlap; backstop only.)
        collect 'except\s*:\s*pass\s*$' '#'
        collect 'except\s*:\s*continue\s*$' '#'
        collect 'except\s+(Exception|BaseException)\b[^:]*:\s*pass\s*$' '#'
        collect 'except\s+(Exception|BaseException)\b[^:]*:\s*continue\s*$' '#'
        # multi-line: broad `except:` / `except Exception:` / `except BaseException:` whose
        # next non-blank line is exactly pass/continue/...
        while IFS= read -r line; do
            [ -z "$line" ] && continue
            code="$(echo "${line#*:}" | sed 's/^[[:space:]]*//')"
            is_new "$code" || continue
            hits+=("  L${line%%:*}: ${code}")
        done < <(awk '
            { lines[NR]=$0 }
            END {
                for (i=1;i<=NR;i++){
                    if (lines[i] ~ /^[[:space:]]*except[[:space:]]*:[[:space:]]*$/ ||
                        lines[i] ~ /^[[:space:]]*except[[:space:]]+(Exception|BaseException)([[:space:]]+as[[:space:]]+[A-Za-z_][A-Za-z0-9_]*)?[[:space:]]*:[[:space:]]*$/){
                        j=i+1
                        while (j<=NR && lines[j] ~ /^[[:space:]]*$/) j++
                        s=lines[j]; gsub(/^[[:space:]]+/,"",s); gsub(/[[:space:]]+$/,"",s)
                        if (s=="pass" || s=="continue" || s=="...") print i":"lines[i]
                    }
                }
            }' "$filePath" 2>/dev/null)
        ;;
    .ts|.tsx|.js|.jsx|.mjs|.cjs)
        collect '\b(concurrency|maxConcurrency|max_concurrency|parallelism)\s*[:=]\s*1\b' '//'
        collect 'pLimit\(\s*1\s*\)' '//'
        collect 'catch\s*\([^)]*\)\s*\{\s*\}' '//'
        ;;
    *)
        exit 0
        ;;
esac

[ ${#hits[@]} -eq 0 ] && exit 0

maxHits=12
shown=("${hits[@]:0:$maxHits}")
extra=$(( ${#hits[@]} - ${#shown[@]} ))
body=$(printf '%s\n' "${shown[@]}")
[ "$extra" -gt 0 ] && body="${body}"$'\n'"  ... and ${extra} more"

fileName=$(basename "$filePath")
msg="⚠ resource-sizing advisory (${fileName}): floor-value / silent-default tells

${body}

Right-size to the substrate or state the basis inline to silence -> reference/resource-sizing.md"

emit=$(jq -n --arg msg "$msg" \
    '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:$msg}}' 2>/dev/null \
    || printf '%s' "$msg")
sid=$(echo "$data" | jq -r '.session_id // empty' 2>/dev/null)
printf '%s' "$emit" | bash "$STRATA_HOME/hooks/lib-ledger.sh" quality-resource-sizing "$sid" >/dev/null 2>&1 || true
printf '%s\n' "$emit"

exit 0
