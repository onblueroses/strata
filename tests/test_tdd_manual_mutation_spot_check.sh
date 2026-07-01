#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SKILL_FILE="${SKILL_FILE:-$ROOT_DIR/skills/tdd/SKILL.md}"

fail() {
    printf 'FAIL: %s\n' "$1" >&2
    exit 1
}

contains() {
    local needle="$1"
    grep -Fq "$needle" "$SKILL_FILE"
}

contains 'testing or a manual mutation spot-check shows the tests bite.' ||
    fail 'stop condition must require mutation testing or a manual mutation spot-check'

contains 'temporarily break the implementation in a plausible way for the behavior under test' ||
    fail 'manual fallback must require a plausible temporary implementation break'

contains 'run the relevant test, and confirm it fails before restoring the implementation' ||
    fail 'manual fallback must require proving the relevant test fails'

if contains 'or reason honestly about whether each test would fail given a plausible bug'; then
    fail 'self-reasoned test-strength certification must not be accepted'
fi
