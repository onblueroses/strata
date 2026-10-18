#!/usr/bin/env bash
# Prove and compile only when generating/checking the finite shell policy.
set -euo pipefail
ROOT="$(cd "${BASH_SOURCE[0]%/*}/../../.." && pwd)"
SOURCE="$ROOT/claude/hooks/privacy-decision"
OUT="$ROOT/claude/.local/privacy-bend/table-$(date +%Y%m%dT%H%M%S)-$$"
mkdir -p "$OUT"
export BEND_NO_TELEMETRY=1
cd "$ROOT"
mapfile -t FILES < <(cd "$SOURCE" && printf '%s\n' *.bend generate.py check-staged.py)
(cd "$SOURCE" && sha256sum "${FILES[@]}") > "$OUT/sources.sha256"
mkdir "$OUT/source"
for file in "${FILES[@]}"; do cp "$SOURCE/$file" "$OUT/source/$file"; done
(cd "$OUT/source" && sha256sum -c --status "$OUT/sources.sha256")
chmod a-w "$OUT/source/"*
python3 "$OUT/source/check-staged.py" --sources-only "$OUT/source"
bend version > "$OUT/provenance.txt"
clang --version >> "$OUT/provenance.txt"
bend "$OUT/source/PROOF.bend"
bend "$OUT/source/Main.bend" -o "$OUT/decision"
python3 "$OUT/source/generate.py" --binary "$OUT/decision" --output "$OUT/policy.sh"
(cd "$SOURCE" && sha256sum -c --status "$OUT/sources.sha256")
if [ "${1:-}" = --check ]; then
    cmp -s "$OUT/policy.sh" "$ROOT/claude/hooks/lib/privacy-decision.sh" || {
        printf 'generated privacy table is stale; run claude/hooks/privacy-decision/build.sh\n' >&2
        exit 1
    }
elif [ "$#" -eq 0 ]; then
    mv -Tf "$OUT/policy.sh" "$ROOT/claude/hooks/lib/privacy-decision.sh"
else
    printf 'usage: %s [--check]\n' "$0" >&2; exit 64
fi
printf 'privacy table build: %s\n' "$OUT"
