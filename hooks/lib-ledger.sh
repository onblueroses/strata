#!/usr/bin/env bash
# lib-ledger.sh — shared hook-firing ledger (invisible-by-design telemetry).
#
# WHAT: records that a model-visible hook actually emitted output, and how many
# bytes it emitted. A caller pipes its exact emitted payload to this script's
# stdin and passes <hook_name> [session_id]; this script measures the byte
# length, appends one JSONL record, and emits NOTHING (no stdout, no stderr).
# It never alters the caller's own model-visible output.
#
# WHY: gives context-injection audits a measured base — which model-visible hooks
# fire, how often, and how large their footprint is — instead of guesses.
#
# CONTRACT:  printf '%s' "$out" | bash lib-ledger.sh <hook> [sid]
#   arg1  = hook basename (e.g. context-nudge)
#   arg2  = session id (truncated to 8 chars; optional)
#   stdin = the payload the hook is about to emit to the model
#   record: {"ts":...,"hook":...,"bytes":N,"sid":"...."} -> hook-firings.jsonl
#   Every path exits 0; a broken sink can never break a hook (fail-open).
#
# LEDGER CATALOG (all sinks live under $STATE_DIR):
#   hook-firings.jsonl   — this file. Q: which model-visible hooks fire, how
#                          often, and how many bytes does each emit?
#   mcp-tool-calls.jsonl — observe-track-mcp-tools.sh. Q: which MCP servers'
#                          tools actually get called?
# Pre-existing sinks (not owned here): skill-runs.jsonl, session-events-<sid>.jsonl,
#   .session-edits-<sid>.
#
# GROWTH: size-capped at 512 KB with one .1 rollover generation (~1 MB ceiling).

set -uo pipefail

hook="${1:-unknown}"
sid="${2:-}"
sid="${sid:0:8}"

stateDir="${STATE_DIR:-}"
[ -z "$stateDir" ] && exit 0
ledger="$stateDir/hook-firings.jsonl"
maxBytes=524288

payload="$(cat 2>/dev/null || true)"
bytes=$(printf '%s' "$payload" | wc -c | tr -d '[:space:]')
[ -z "$bytes" ] && bytes=0
ts="$(date -u +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo unknown)"

mkdir -p "$stateDir" 2>/dev/null || exit 0

# size-capped rotation: keep one .1 generation, bounded ~1 MB total.
if [ -f "$ledger" ]; then
    sz=$(stat -c%s "$ledger" 2>/dev/null || echo 0)
    [ "$sz" -gt "$maxBytes" ] && mv -f "$ledger" "$ledger.1" 2>/dev/null || true
fi

line=$(jq -nc --arg ts "$ts" --arg hook "$hook" --argjson bytes "$bytes" --arg sid "$sid" \
    '{ts:$ts, hook:$hook, bytes:$bytes, sid:$sid}' 2>/dev/null) \
    || line="{\"ts\":\"$ts\",\"hook\":\"$hook\",\"bytes\":$bytes,\"sid\":\"$sid\"}"
printf '%s\n' "$line" >> "$ledger" 2>/dev/null || true

exit 0
