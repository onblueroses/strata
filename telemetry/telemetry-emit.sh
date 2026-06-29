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

write_row() { printf '%s\n' "$1" >> "$out" 2>/dev/null || true; }

if command -v jq >/dev/null 2>&1; then
  # $p first, fixed envelope second so payload keys can NEVER override ts/sid/kind/source.
  row="$(jq -cn --arg ts "$ts" --arg sid "$sid" --arg kind "$kind" --argjson p "$payload" \
     '$p + {ts:$ts,sid:$sid,kind:$kind,source:"live"}' 2>/dev/null || true)"
  [ -n "$row" ] && write_row "$row"
else
  # no jq: splice the payload object's inner fields into the envelope.
  inner="${payload#\{}"; inner="${inner%\}}"
  if [ -n "${inner// /}" ]; then pre="$inner,"; else pre=""; fi
  # inner first, fixed envelope last: on a duplicate key JSON parsers keep the last value, so
  # ts/sid/kind/source can't be overridden by a payload key on this fallback path either.
  row="$(printf '{%s"ts":"%s","sid":"%s","kind":"%s","source":"live"}' "$pre" "$ts" "$sid" "$kind")"
  write_row "$row"
fi
exit 0
