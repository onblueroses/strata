#!/usr/bin/env bash
# Bound the unbounded telemetry sinks. events.jsonl (live appends) and session-metrics.jsonl
# (one row per session end) grow forever otherwise. When a file crosses its threshold, archive the
# OLD head to a gzip under archive/ and keep a recent live tail in place, so readers (unify.py,
# cost_rollup.py) keep seeing recent data while deep history compresses away.
#
# Opt-in: the live sink only exists when STRATA_TELEMETRY=1 has emitted at least once. When the
# telemetry dir is absent (telemetry never ran), this exits cleanly without creating anything.
#
# Fail-open + fast: a no-op is one stat per file; every error path exits 0. A flock makes
# concurrent session-end hooks rotate at most once. A rare append during the tail-swap can be lost;
# the whole telemetry layer is best-effort by design, so that is acceptable.
#
# Usage: rotate_telemetry.sh        # rotate if over threshold (called from the session-end hook)
set -uo pipefail

# Runtime sink resolution mirrors telemetry-emit.sh: parent-of-script -> state_dir -> telemetry dir.
STRATA_HOME="${STRATA_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
state_dir="${STATE_DIR:-${KB_DIR:-$STRATA_HOME/workspace}/state}"
TEL="${STRATA_TELEMETRY_DIR:-$state_dir/telemetry}"

# never assume telemetry is enabled: no sink dir means nothing to rotate.
[ -d "$TEL" ] || exit 0

ARCDIR="$TEL/archive"
LOCK="$TEL/.rotate.lock"
# Documented TELEMETRY_* names take precedence; STRATA_* remains a compatibility fallback.
KEEP_ARCHIVES="${TELEMETRY_KEEP_ARCHIVES:-${STRATA_TELEMETRY_KEEP_ARCHIVES:-12}}"  # gzip files retained per base before pruning

mkdir -p "$ARCDIR" 2>/dev/null || exit 0

# single-rotator: if another hook holds the lock, skip silently (its rotation covers us)
exec 9>"$LOCK" 2>/dev/null || exit 0
flock -n 9 2>/dev/null || exit 0

rotate_one() {
  # rotate_one <file> <threshold_mb> <keep_lines>
  local f="$1" thresh_mb="$2" keep="$3"
  [ -f "$f" ] || return 0
  local bytes; bytes=$(stat -c%s "$f" 2>/dev/null || echo 0)
  [ "$bytes" -gt $(( thresh_mb * 1024 * 1024 )) ] || return 0
  local total; total=$(wc -l < "$f" 2>/dev/null || echo 0)
  # Trip on SIZE alone (the MB gate above already fired): a file can cross the byte
  # threshold with fewer lines than `keep` (large enveloped rows), and the old
  # line-count gate then never rotated it. Keep total/2 when below the keep bar; guard
  # the empty-file edge so head/tail math stays valid.
  [ "$total" -gt 0 ] || return 0
  [ "$total" -gt "$keep" ] || keep=$(( total / 2 ))

  local base ts arc
  base=$(basename "$f" .jsonl)
  ts=$(date -u +%Y%m%dT%H%M%SZ 2>/dev/null || echo unknown)
  arc="$ARCDIR/${base}-${ts}.jsonl.gz"

  # archive older lines, keep the recent tail live; mv is the atomic swap
  head -n $(( total - keep )) "$f" | gzip -c > "$arc" 2>/dev/null || return 0
  if tail -n "$keep" "$f" > "$f.tmp" 2>/dev/null; then
    mv "$f.tmp" "$f" 2>/dev/null || rm -f "$f.tmp" 2>/dev/null
  fi

  # prune oldest archives for this base beyond KEEP_ARCHIVES
  find "$ARCDIR" -maxdepth 1 -type f -name "${base}-*.jsonl.gz" -printf '%T@ %p\n' 2>/dev/null \
    | sort -rn | tail -n +$(( KEEP_ARCHIVES + 1 )) | cut -d' ' -f2- \
    | while IFS= read -r old; do rm -f "$old" 2>/dev/null; done
}

# events.jsonl grows fastest (many events/session); keep a large recent window.
rotate_one "$TEL/events.jsonl" "${TELEMETRY_EVENTS_MB:-${STRATA_TELEMETRY_EVENTS_MB:-50}}" "${TELEMETRY_EVENTS_KEEP:-${STRATA_TELEMETRY_EVENTS_KEEP:-150000}}"
# session-metrics.jsonl is one row/session and dedups by sid on read; keep the last N sessions.
rotate_one "$TEL/session-metrics.jsonl" "${TELEMETRY_METRICS_MB:-${STRATA_TELEMETRY_METRICS_MB:-20}}" "${TELEMETRY_METRICS_KEEP:-${STRATA_TELEMETRY_METRICS_KEEP:-5000}}"
# telemetry-errors.jsonl grows only when the live sink fails; a small cap bounds it even if
# events.jsonl is persistently unwritable while the dir stays writable.
rotate_one "$TEL/telemetry-errors.jsonl" "${TELEMETRY_ERRORS_MB:-${STRATA_TELEMETRY_ERRORS_MB:-5}}" "${TELEMETRY_ERRORS_KEEP:-${STRATA_TELEMETRY_ERRORS_KEEP:-2000}}"

exit 0
