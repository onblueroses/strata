#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

tel="$tmpdir/telemetry"
archive="$tel/archive"
mkdir -p "$archive"

make_sink() {
  local path="$1"
  awk 'BEGIN {
    line = sprintf("%1024s", "")
    gsub(/ /, "x", line)
    for (i = 1; i <= 1100; i++) print line
  }' >"$path"
}

make_sink "$tel/events.jsonl"
make_sink "$tel/session-metrics.jsonl"

printf 'old\n' | gzip -c >"$archive/events-20000101T000000Z.jsonl.gz"
printf 'old\n' | gzip -c >"$archive/events-20000102T000000Z.jsonl.gz"
touch -t 200001010000 "$archive/events-20000101T000000Z.jsonl.gz"
touch -t 200001020000 "$archive/events-20000102T000000Z.jsonl.gz"

STRATA_TELEMETRY_DIR="$tel" \
TELEMETRY_EVENTS_MB=1 \
TELEMETRY_EVENTS_KEEP=2 \
TELEMETRY_METRICS_MB=1 \
TELEMETRY_METRICS_KEEP=3 \
TELEMETRY_KEEP_ARCHIVES=1 \
  bash "$ROOT/telemetry/rotate_telemetry.sh"

events_lines="$(wc -l <"$tel/events.jsonl")"
if [ "$events_lines" -ne 2 ]; then
  echo "TELEMETRY_EVENTS_MB/KEEP did not rotate events sink to the documented tail size" >&2
  exit 1
fi

metrics_lines="$(wc -l <"$tel/session-metrics.jsonl")"
if [ "$metrics_lines" -ne 3 ]; then
  echo "TELEMETRY_METRICS_MB/KEEP did not rotate metrics sink to the documented tail size" >&2
  exit 1
fi

events_archives="$(find "$archive" -maxdepth 1 -type f -name 'events-*.jsonl.gz' | wc -l)"
if [ "$events_archives" -ne 1 ]; then
  echo "TELEMETRY_KEEP_ARCHIVES did not prune event archives to the documented count" >&2
  exit 1
fi
