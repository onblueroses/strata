#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_FILE="${SKILL_FILE:-$ROOT_DIR/skills/setup-pre-commit/SKILL.md}"

fail() {
  printf 'FAIL: %s\n' "$1" >&2
  exit 1
}

contains() {
  local needle="$1"
  grep -Fq "$needle" "$SKILL_FILE"
}

hook_has_full_gate() {
  local hook_file="$1"

  awk '
    /(^|[[:space:]])lint-staged([[:space:]]|$)/ && stage == 0 {
      stage = 1
      next
    }
    /(run[[:space:]]+typecheck)|(^|[[:space:]])typecheck([[:space:]]|$)/ && stage == 1 {
      stage = 2
      next
    }
    /(run[[:space:]]+test)|(^|[[:space:]])test([[:space:]]|$)/ && stage == 2 {
      stage = 3
      next
    }
    END {
      exit(stage == 3 ? 0 : 1)
    }
  ' "$hook_file"
}

contains '.husky/pre-commit contains and runs lint-staged, then typecheck, then test' ||
  fail 'success criteria must require the full hook gate'

contains "the hook body is verified for all three stages before \`./.husky/pre-commit\` or the exact hook commands run clean as the smoke test" ||
  fail 'success criteria must verify the generated hook body before running it'

contains "Treat any missing \`typecheck\` or \`test\` script as a blocking gap" ||
  fail 'missing typecheck/test scripts must block the original setup goal'

contains 'Report the original goal successful only after both scripts exist and both hook commands run' ||
  fail 'success must require both full-project gates'

contains "Report any hook missing typecheck or test as a blocking gap, even when direct hook execution exits 0" ||
  fail 'direct execution success must not hide missing full-project gates'

contains "after the stage-order check passes, run \`./.husky/pre-commit\` from the repo root; when direct hook execution is unavailable, run the exact command lines from \`.husky/pre-commit\` in order and require each to pass" ||
  fail 'verification must run the exact hook commands in order when the hook cannot be executed directly'

if contains 'lines for absent scripts dropped'; then
  fail 'success criteria must not allow dropping typecheck/test gates'
fi

if contains "\`npx lint-staged\` runs clean as a smoke test"; then
  fail 'lint-staged alone must not be accepted as the smoke test'
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

BAD_HOOK="$TMP_DIR/pre-commit.bad"
TYPO_HOOK="$TMP_DIR/pre-commit.typo"
OUT_OF_ORDER_HOOK="$TMP_DIR/pre-commit.out-of-order"
GOOD_HOOK="$TMP_DIR/pre-commit.good"
BIN_DIR="$TMP_DIR/bin"

printf '%s\n' 'npx lint-staged' >"$BAD_HOOK"
printf '%s\n' 'npx lint-staged' 'npm run typechec' 'npm run test' >"$TYPO_HOOK"
printf '%s\n' 'npx lint-staged' 'npm run test' 'npm run typecheck' >"$OUT_OF_ORDER_HOOK"
printf '%s\n' 'npx lint-staged' 'npm run typecheck' 'npm run test' >"$GOOD_HOOK"
chmod +x "$BAD_HOOK" "$TYPO_HOOK" "$OUT_OF_ORDER_HOOK" "$GOOD_HOOK"

mkdir "$BIN_DIR"
printf '%s\n' '#!/usr/bin/env bash' 'exit 0' >"$BIN_DIR/npx"
printf '%s\n' '#!/usr/bin/env bash' 'exit 0' >"$BIN_DIR/npm"
chmod +x "$BIN_DIR/npx" "$BIN_DIR/npm"

PATH="$BIN_DIR:$PATH" "$BAD_HOOK" ||
  fail 'lint-staged-only fixture should reproduce the direct-execution bypass'

if hook_has_full_gate "$BAD_HOOK"; then
  fail 'lint-staged-only hook must be blocked'
fi

if hook_has_full_gate "$TYPO_HOOK"; then
  fail 'typoed typecheck hook must be blocked'
fi

if hook_has_full_gate "$OUT_OF_ORDER_HOOK"; then
  fail 'out-of-order hook must be blocked'
fi

PATH="$BIN_DIR:$PATH" "$GOOD_HOOK" ||
  fail 'full lint-staged/typecheck/test hook must execute cleanly'

hook_has_full_gate "$GOOD_HOOK" ||
  fail 'full lint-staged/typecheck/test hook must be allowed'
