#!/usr/bin/env bash
# Contract test for optmem-wake.sh and optmem-core.sh. A stand-in memo drives every branch, so
# each failure text, the nap handover, the session-scope rules and the core dedupe are checked
# without touching the real store; two last cases read the real store (wake and recall only
# read) when OPTMEM_TEST_REAL_STORE=1. Every path must exit 0 with a SessionStart payload.
set -euo pipefail

hooks="$(cd "$(dirname "$0")" && pwd)"
tmp="$(mktemp -d "${TMPDIR:-/tmp}/test-optmem-hooks-XXXXXX")"
trap 'rm -rf "$tmp"' EXIT
export TELEMETRY_SYNTHETIC=1
fail() { echo "FAIL: $*"; exit 1; }

mkdir -p "$tmp/store/TREE"; : > "$tmp/store/LOG.txt"
cat > "$tmp/memo" <<'MEMO'
#!/usr/bin/env bash
case "${FAKE_MODE:-}" in
  timeout) sleep 10 ;;
  nap) printf 'Cannot wake: 12 blocks are unsettled.\nDo the 3 compression(s) first.\nCompress memories #100-131:\n#100 x\n'; exit 1 ;;
  fail) echo "boom" >&2; exit 3 ;;
  empty) exit 0 ;;
  paged) printf 'part one\nNot awake yet. Run: memo wake 2\n' ;;
  unconfirmed) printf 'some output\nwithout the line\n' ;;
  ok) printf '#1 a note\nYou are awake.\n' ;;
  pending) printf '#1 a note\nYou are awake.\n\nCompress memories #200-215:\n#200 y\n4 compressions remain after this one.\n' ;;
  near-budget) python3 - <<'PYMEMO'
# Generic memo output just under the sample budget, ending in a pending compression prompt.
end = "\nYou are awake.\n\nCompress memories #200-215:\n#200 y"
print("x" * (9000 - len(end)) + end, end="")
PYMEMO
    ;;
  big) for i in $(seq 1 300); do printf '#%d 2026-11-10 F @e/x @g @k/core/k%d %s\n' "$i" "$i" pppppppppppppppppppppppppppppppppppppppp; done; echo 'You are awake.' ;;
  nomatch) echo "No match." ;;
  narrow) printf '#1 2026-11-10 F @e/x @g @k/core/a one\nNewest 1 of 900. Narrow the regex.\n' ;;
  dedupe) printf '#1 2026-11-10 F @e/x @g @k/core/a old\n#2 2026-11-10 F @e/y @g @k/core/b keep\n#3 2026-11-11 F @e/x @g @k/core/a new\n#4 2026-11-11 F @e/z @g @k/core/c RETIRED gone\n' ;;
esac
MEMO
chmod +x "$tmp/memo"

payload() {  # payload <hook> <stdin text> [env assignments...]; prints the injected context
    local hook="$1" input="$2" out; shift 2
    out="$(printf '%s' "$input" | env "$@" bash "$hooks/$hook")" || fail "$hook exited nonzero ($*)"
    jq -er '.hookSpecificOutput | select(.hookEventName=="SessionStart") | .additionalContext' <<<"$out" \
        || fail "$hook printed no SessionStart payload ($*): $out"
}
sid='{"session_id":"abcd1234-0000-1111"}'
budget=10000  # sample injection budget for these fixtures
wake() { local mode="$1"; shift; payload optmem-wake.sh "$sid" OPTMEM_MEMO_PATH="$tmp/memo" MEMORY_DIR="$tmp/store" OPTMEM_INJECTION_BUDGET="$budget" FAKE_MODE="$mode" "$@"; }
core() { local mode="$1"; shift; payload optmem-core.sh "" OPTMEM_MEMO_PATH="$tmp/memo" MEMORY_DIR="$tmp/store" OPTMEM_INJECTION_BUDGET="$budget" FAKE_MODE="$mode" "$@"; }
scope() { payload optmem-wake.sh "$1" OPTMEM_MEMO_PATH="$tmp/memo" MEMORY_DIR="$tmp/store" FAKE_MODE=ok | head -1; }

# 1. Session scope: only eight lowercase ASCII alphanumerics from a JSON string become a token.
[[ "$(scope "$sid")" == "SESSION SCOPE: @s/abcd1234" ]] || fail "valid session id not resolved"
for bad in '' '{"session_id":12345678}' '{"session_id":"abc"}' '{"session_id":"ABCD1234-x"}' \
           '{"session_id":"abcdéfgh-x"}' '{"session_id":"abcd1234-x"} junk'; do
    [[ "$(scope "$bad")" == "SESSION SCOPE: unresolved" ]] || fail "scope resolved from: $bad"
done

# 2. Both hooks name what is missing and the command to run by hand.
for hook in optmem-wake.sh optmem-core.sh; do
    label=WAKE; [[ $hook == *core* ]] && label=CORE
    out="$(payload "$hook" "$sid" -u HOME -u MEMORY_DIR)"
    [[ "$out" == *"OPTMEM $label FAILURE: neither MEMORY_DIR nor HOME is set"* ]] || fail "$hook: no-home text"
    out="$(payload "$hook" "$sid" OPTMEM_MEMO_PATH="$tmp/memo" "MEMORY_DIR=$tmp/no such store")"
    [[ "$out" == *"OPTMEM $label FAILURE: the memory store is missing or incomplete at $tmp/no such store"* ]] || fail "$hook: no-store text"
    [[ "$out" == *"Run by hand: env MEMORY_DIR=$tmp/no\\ such\\ store "* ]] || fail "$hook: store path not shell-quoted: $out"
    out="$(payload "$hook" "$sid" OPTMEM_MEMO_PATH="$tmp/absent" MEMORY_DIR="$tmp/store")"
    [[ "$out" == *"OPTMEM $label FAILURE: the memo CLI is missing or not executable at $tmp/absent"* ]] || fail "$hook: no-memo text"
done

# 3. Wake: each way memo can answer.
[[ "$(wake ok)" == "SESSION SCOPE: @s/abcd1234"*$'\n\n#1 a note\nYou are awake.' ]] || fail "plain wake altered"
out="$(wake nap)"
[[ "$out" == *"OPTMEM MEMORY NEEDS A NAP BEFORE IT CAN BE READ."*"nap <lo>-<hi>"*"Compress memories #100-131:"* ]] || fail "nap handover"
[[ "$out" != *"WAKE FAILURE"* ]] || fail "a nap refusal was reported as a failure"
[[ "$(wake fail)" == *"OPTMEM WAKE FAILURE: memo wake exited with status 3."*"Original memo output:"*"boom"* ]] || fail "exit status branch"
[[ "$(wake empty)" == *"exited successfully but returned empty output"* ]] || fail "empty branch"
[[ "$(wake paged)" == *"this is only part 1 of the memory"* ]] || fail "paged branch"
[[ "$(wake unconfirmed)" == *"without the required 'You are awake.' confirmation"* ]] || fail "unconfirmed branch"
[[ "$(wake pending)" == *"You are awake."*"OPTMEM: compressions are pending, shown above."* ]] || fail "pending-compression hint"
# Keep every memo character and the nap instructions inside the sample budget.
out="$(wake near-budget)"
[[ ${#out} -le $budget && "$out" != *"OPTMEM WAKE OVERSIZE"* ]] || fail "near-budget wake exceeds the sample budget"
expected="$(FAKE_MODE=near-budget "$tmp/memo")"
[[ ${#expected} -eq 9000 ]] || fail "near-budget memo fixture length changed"
[[ "$out" == *"$expected"* ]] || fail "near-budget wake lost memo text"
[[ "$out" == *"note limit"*"date range"*"no @ tokens or keyword lists"*"wake refuses"* ]] || fail "near-budget wake lost nap instructions"

out="$(wake big)"
[[ "$out" == "SESSION SCOPE: @s/abcd1234"*"OPTMEM WAKE OVERSIZE"*"#300 "*"You are awake." ]] || fail "oversize wake: warning in front, payload whole"
[[ "$(wake timeout)" == *"OPTMEM WAKE FAILURE: memo wake timed out after 3.867s."* ]] || fail "timeout branch"

# 4. Core: newest version of a key wins, a RETIRED newest drops the key, and the count is true.
[[ "$(core dedupe)" == $'#2 2026-11-10 F @e/y @g @k/core/b keep\n#3 2026-11-11 F @e/x @g @k/core/a new\n2 core notes.' ]] || fail "core dedupe: $(core dedupe)"
[[ "$(core nomatch)" == *"returned 'No match.' for the durable @k/core/ namespace"* ]] || fail "no-match branch"
[[ "$(core narrow)" == *"could not return the whole durable @k/core/ namespace"* ]] || fail "narrow branch"
[[ "$(core fail)" == *"OPTMEM CORE FAILURE: memo recall exited with status 3."* ]] || fail "core exit status branch"
[[ "$(core empty)" == *"exited successfully but returned empty output"* ]] || fail "core empty branch"
[[ "$(core big)" == "OPTMEM CORE OVERSIZE"*"300 core notes." ]] || fail "oversize core"

# 5. Without the shared library each hook still exits 0 and says so.
mkdir "$tmp/alone"; cp "$hooks/optmem-wake.sh" "$hooks/optmem-core.sh" "$tmp/alone/"
for hook in optmem-wake.sh optmem-core.sh; do
    out="$(printf '%s' "$sid" | bash "$tmp/alone/$hook" | jq -r '.hookSpecificOutput.additionalContext')" || fail "$hook without its library exited nonzero"
    [[ "$out" == *"lib/optmem-session.sh could not be loaded"* ]] || fail "$hook without its library: $out"
done

# 6. The real store (opt-in): a wake that ends awake under the scope header, and a counted core set.
if [ "${OPTMEM_TEST_REAL_STORE:-0}" = 1 ]; then
    out="$(payload optmem-wake.sh "$sid")"
    [[ "$out" == "SESSION SCOPE: @s/abcd1234"* && "$out" == *"You are awake."* ]] || fail "real wake: ${out:0:200}"
    [[ "$(payload optmem-core.sh "" | tail -1)" =~ ^[0-9]+\ core\ notes\.$ ]] || fail "real core recall"
fi

printf 'optmem session hooks: scope rules, preflight failures, every wake and core branch, library fallback, real store\n'
