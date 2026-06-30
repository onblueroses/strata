#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

fakebin="$tmpdir/bin"
home="$tmpdir/home"
tel="$tmpdir/telemetry"
mkdir -p "$fakebin" "$home"

python_bin=/usr/bin/python3
if [ ! -x "$python_bin" ]; then
  python_bin="$(command -v python3)"
fi

ln -s "$(command -v date)" "$fakebin/date"
ln -s "$(command -v mkdir)" "$fakebin/mkdir"
ln -s "$python_bin" "$fakebin/python3"

if PATH="$fakebin" command -v jq >/dev/null 2>&1; then
  echo "test setup exposed jq" >&2
  exit 1
fi

run_emit() {
  PATH="$fakebin" STRATA_HOME="$home" STRATA_TELEMETRY=1 STRATA_TELEMETRY_DIR="$tel" \
    /usr/bin/bash "$ROOT/telemetry/telemetry-emit.sh" "$@"
}

run_emit delegation 'abc"def' '{"lane":"fast"}'
run_emit benign plain '{"count":1}'

event_file="$tel/events.jsonl"
if [ ! -s "$event_file" ]; then
  echo "telemetry emitter did not write events" >&2
  exit 1
fi

"$python_bin" - "$event_file" <<'PY'
import json
import sys
from pathlib import Path

rows = [json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines()]
if len(rows) != 2:
    raise SystemExit(f"expected 2 events, got {len(rows)}")

quoted, benign = rows
if quoted["sid"] != 'abc"def':
    raise SystemExit(f"quoted sid was not preserved: {quoted!r}")
if quoted["kind"] != "delegation" or quoted["source"] != "live" or quoted["lane"] != "fast":
    raise SystemExit(f"quoted event envelope/payload mismatch: {quoted!r}")
if benign["sid"] != "plain" or benign["kind"] != "benign" or benign["count"] != 1:
    raise SystemExit(f"benign event mismatch: {benign!r}")
PY
