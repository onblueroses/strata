#!/usr/bin/env bash
# Contract test for codex/hooks/optmem_start.py against a stub memo CLI and a scratch store
# under a scratch HOME, so the record sink is the test's own (offline). Checks the blocks a Codex
# primary must get, the clock label on resume, a delegate's start, and that a missing block is
# recorded as degraded.
set -euo pipefail

hook="$(cd "$(dirname "$0")/../hooks" && pwd)/optmem_start.py"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/test-optmem-start-XXXXXX")"
trap 'rm -rf "$tmp"' EXIT
# A stub memo: `wake` prints a wake document, `recall` one core note.
mkdir -p "$tmp/store/TREE" "$tmp/bin"
: > "$tmp/store/LOG.txt"
printf '%s\n' '#!/bin/sh' 'case "$1" in' \
    'wake) printf "You are awake.\nstub wake document\n" ;;' \
    'recall) echo "#1 2026-11-10 F @e/style @g @k/core/style Short sentences." ;;' \
    '*) exit 2 ;;' 'esac' > "$tmp/bin/memo"
chmod +x "$tmp/bin/memo"
export CODEX_HOOK_SINK="$tmp/sink.jsonl" OPTMEM_MEMORY_DIR="$tmp/store" OPTMEM_MEMO_PATH="$tmp/bin/memo"
fail() { echo "FAIL: $*"; exit 1; }

run() {  # run <source> [env...]; prints the injected context
    local source="$1"; shift
    printf '{"session_id":"abcd1234-0000","source":"%s"}' "$source" \
        | env HOME="$tmp/home" CLOCK_STATE_DIR="$tmp/clock" "$@" python3 "$hook" \
        | jq -r '.hookSpecificOutput.additionalContext'
}
mkdir -p "$tmp/home"

# 1. A primary start: scope, wake, core notes, clock.
out="$(run startup)"
[[ "$out" == "SESSION SCOPE: @s/abcd1234"* ]] || fail "scope header missing"
[[ "$out" == *"You are awake."* ]] || fail "wake missing"
[[ "$out" == *"core notes."* ]] || fail "core notes missing"
[[ "$out" == *"TIME: session started "* ]] || fail "clock missing"

# 2. The clock says what happened.
[[ "$(run resume)" == *"TIME: session resumed "* ]] || fail "resume not labeled"

# 3. A delegate gets the same start.
out="$(run startup OPTMEM_ROLE=delegate)"
[[ "$out" == *"core notes."* ]] || fail "delegate lost the core notes"

# 4. A shared block that cannot run is recorded as a missing block, not as ok.
run startup CODEX_SHARED_HOOKS="$tmp/absent" > /dev/null
last="$(tail -1 "$CODEX_HOOK_SINK")"
[[ "$(jq -r .status <<<"$last")" == degraded && "$(jq -r .detail <<<"$last")" == *"core"* ]] \
    || fail "missing block not recorded: $last"

# 5. And the first run recorded ok.
[[ "$(head -1 "$CODEX_HOOK_SINK" | jq -r '.status')" == ok ]] || fail "healthy run not recorded ok: $(head -1 "$CODEX_HOOK_SINK")"

printf 'optmem_start: wake, core and clock for a primary and a delegate; a missing block is recorded\n'
