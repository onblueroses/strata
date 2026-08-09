#!/usr/bin/env bash
# Shared telemetry emitter — appends one enveloped JSONL event to the opt-in sink.
# Usage: telemetry-emit.sh <kind> <sid> [json_payload]
#   json_payload: a JSON object string of extra fields (default {})
#
# Opt-in: writes nothing unless STRATA_TELEMETRY=1. Fail-open + fast: any error exits 0
# without output, so it never blocks a hook or changes a caller's exit code.
set -uo pipefail

[ "${STRATA_TELEMETRY:-0}" = "1" ] || exit 0   # opt-in; default off, no-op

kind="${1:-unknown}"
sid="${2:-unknown}"
# NB: do NOT write ${3:-{}} — bash parses the literal {} default as `{` + stray `}`, corrupting
# the JSON. Default explicitly instead.
payload="${3:-}"
[ -z "$payload" ] && payload='{}'

# Runtime sink lives under $STATE_DIR, never the tracked install tree.
STRATA_HOME="${STRATA_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
state_dir="${STATE_DIR:-${KB_DIR:-$STRATA_HOME/workspace}/state}"
dir="${STRATA_TELEMETRY_DIR:-$state_dir/telemetry}"
mkdir -p "$dir" 2>/dev/null || exit 0
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo unknown)"
out="$dir/events.jsonl"
err_out="$dir/telemetry-errors.jsonl"

# Record a sink-append failure as a documented telemetry_error row on a side-stream
# (read back by unify.py) instead of silently swallowing it, so a dropping instrument is
# observable. Strictly fail-open: if the side-stream write also fails, give up quietly;
# telemetry never blocks a caller or changes its exit code.
note_telemetry_error() {
  # Encode via jq/python so a sid or kind carrying a quote, backslash, or newline can't
  # write invalid JSON (which unify.py would skip, losing the very failure signal).
  local erow=""
  if command -v jq >/dev/null 2>&1; then
    erow="$(jq -cn --arg ts "$ts" --arg sid "$sid" --arg fk "$kind" \
      '{ts:$ts,sid:$sid,kind:"telemetry_error",source:"live",failed_kind:$fk}' 2>/dev/null || true)"
  elif command -v python3 >/dev/null 2>&1; then
    erow="$(python3 -c 'import json,sys; print(json.dumps({"ts":sys.argv[1],"sid":sys.argv[2],"kind":"telemetry_error","source":"live","failed_kind":sys.argv[3]}))' \
      "$ts" "$sid" "$kind" 2>/dev/null || true)"
  fi
  [ -n "$erow" ] && { { printf '%s\n' "$erow" >> "$err_out"; } 2>/dev/null || true; }
}
write_row() { { printf '%s\n' "$1" >> "$out"; } 2>/dev/null || note_telemetry_error; }

encode_row_with_python() {
  python3 - "$ts" "$sid" "$kind" "$payload" <<'PY' 2>/dev/null
import json
import sys

ts, sid, kind, payload = sys.argv[1:5]
obj = json.loads(payload)
if not isinstance(obj, dict):
    raise SystemExit(1)
obj.update({"ts": ts, "sid": sid, "kind": kind, "source": "live"})
print(json.dumps(obj, separators=(",", ":")))
PY
}

if command -v jq >/dev/null 2>&1; then
  # $p first, fixed envelope second so payload keys can NEVER override ts/sid/kind/source.
  row="$(jq -cn --arg ts "$ts" --arg sid "$sid" --arg kind "$kind" --argjson p "$payload" \
     '$p + {ts:$ts,sid:$sid,kind:$kind,source:"live"}' 2>/dev/null || true)"
  [ -n "$row" ] && write_row "$row"
else
  if command -v python3 >/dev/null 2>&1; then
    row="$(encode_row_with_python || true)"
    [ -n "$row" ] && write_row "$row"
  fi
fi
exit 0
