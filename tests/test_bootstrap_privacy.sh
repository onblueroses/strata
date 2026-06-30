#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BOOTSTRAP="${BOOTSTRAP:-$ROOT_DIR/bin/strata-init}"

fail() {
    printf 'FAIL: %s\n' "$1" >&2
    exit 1
}

grep -Fq '# === Workspace seed ===' "$BOOTSTRAP" ||
    fail 'bootstrap must keep the public workspace seed section label'

if grep -Eq 'Decision[[:space:]]+[0-9]+' "$BOOTSTRAP"; then
    fail 'bootstrap must not expose internal decision references'
fi
