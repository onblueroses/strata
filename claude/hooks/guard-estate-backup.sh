#!/usr/bin/env bash
# Snapshot selected local data to a remote restic repository.
#
# Rulings: the 2026-08-13 backup destination; the 2026-09-27 estate and code scope.
# Connection, credentials and exact source paths live in a mode-600 local env file.
#
# Modes:
#   --run [estate|code]  estate (hourly): OptMem, secrets, agent config.
#                        code (daily): working trees without an off-machine copy, minus caches
#                        and files over 50 MB. Alerts on failure or staleness.
#   --prune              weekly: forget per retention policy and prune (no --append-only).
#   --report             SessionStart hook: print the cached ALERT if present. No network.
#   --drill              restore drill (design §8a, part A): byte-identical OptMem round trip.
set -uo pipefail

ENV_FILE="${ESTATE_BACKUP_ENV:-$HOME/.config/estate-backup/env}"
STATE_DIR="${ESTATE_BACKUP_STATE_DIR:-$HOME/.cache/estate-backup}"
ALERT_FILE="$STATE_DIR/ALERT"
STATE_FILE="$STATE_DIR/state.txt"
LAST_CHECK_FILE="$STATE_DIR/last-check"
RUN_LOCK="$STATE_DIR/run.lock"
CHECK_INTERVAL_SECONDS=$((7 * 24 * 3600))

mkdir -p "$STATE_DIR"

# The local env file supplies exact arrays; see guard-estate-backup.env.example.
ESTATE_PATHS=()
CODE_PATHS=()

# Regenerable or bulky: dependency trees, build output, caches, weights and array dumps.
CODE_EXCLUDES=(
  node_modules .venv venv __pycache__ .cache target .next .astro wandb checkpoints
  .mypy_cache .pytest_cache .ruff_cache
  '*.safetensors' '*.bin' '*.pt' '*.pth' '*.ckpt' '*.gguf' '*.onnx' '*.npy' '*.npz' '*.parquet'
)

now_iso() { date -Is; }
log() { echo "$(now_iso) $*" >&2; }

load_env() {
  [ -r "$ENV_FILE" ] || { log "backup configuration unavailable"; return 2; }
  set -a
  source "$ENV_FILE" || { set +a; return 2; }
  set +a
}

r() { restic -r "$RESTIC_REPOSITORY" -o rclone.program="$RCLONE_PROGRAM" -o rclone.args="$RCLONE_ARGS" "$@"; }

notify_failure() {
  command -v notify-send >/dev/null 2>&1 && \
    notify-send -u critical "Laptop backup alert" "$1" 2>/dev/null || true
}

alert() {
  { echo "$(now_iso) ALERT: $1"; [ -n "${2:-}" ] && echo "$2" | tail -30; } > "$ALERT_FILE"
  notify_failure "$1"
}

seconds_since_file() {
  local ts
  [ -f "$1" ] || { echo "-1"; return; }
  ts=$(date -d "$(cat "$1")" +%s 2>/dev/null) || { echo "-1"; return; }
  echo $(( $(date +%s) - ts ))
}

probe_box() {
  # The path restic uses: laptop -> VPS (Tailscale) -> box. Bounded.
  timeout 30 ssh -o BatchMode=yes -o ConnectTimeout=10 "$STORAGEBOX_JUMP" \
    "timeout 10 bash -c 'cat </dev/null >/dev/tcp/${STORAGEBOX_HOST}/${STORAGEBOX_PORT}'" 2>/dev/null
}

do_run() {
  local tier="${1:-estate}" tag stale paths=() extra=()
  load_env || exit 2
  case "$tier" in
    estate) tag=hourly; stale=$((26 * 3600)); paths=("${ESTATE_PATHS[@]}") ;;
    code)   tag=daily;  stale=$((3 * 24 * 3600)); paths=("${CODE_PATHS[@]}")
            extra=(--exclude-caches --exclude-larger-than 50M)
            for x in "${CODE_EXCLUDES[@]}"; do extra+=(--exclude "$x"); done ;;
    *) echo "unknown tier: $tier" >&2; exit 2 ;;
  esac
  [ "${#paths[@]}" -gt 0 ] || { log "no configured $tier source paths"; exit 2; }
  local last_success="$STATE_DIR/last-success-$tier"

  exec 9>"$RUN_LOCK"
  # Shared: restic runs concurrent backups safely; only prune needs the repo alone.
  flock -s -w 600 9 || { log "prune holds the lock; skipping $tier"; exit 0; }
  now_iso > "$STATE_FILE"

  if ! probe_box; then
    log "storage box unreachable via $STORAGEBOX_JUMP, skipping $tier"
    local age; age=$(seconds_since_file "$last_success")
    if [ "$age" -gt "$stale" ]; then
      alert "no successful $tier backup since $(cat "$last_success" 2>/dev/null), and the box is unreachable"
    fi
    exit 0
  fi

  local existing=() p out rc
  for p in "${paths[@]}"; do [ -e "$p" ] && existing+=("$p"); done
  out=$(r backup --tag "$tier" --tag "$tag" "${extra[@]}" "${existing[@]}" 2>&1)
  rc=$?
  # Exit 3: snapshot written but some files were unreadable. Keep it, but say so.
  if [ $rc -eq 0 ] || [ $rc -eq 3 ]; then
    now_iso > "$last_success"
    rm -f "$ALERT_FILE"
    log "$tier backup ok (exit $rc)"
    echo "$out" | tail -12 >&2
    [ $rc -eq 3 ] && alert "$tier backup finished with unreadable files" "$out"
  else
    alert "$tier backup FAILED (exit $rc)" "$out"
    exit 1
  fi

  if [ "$(seconds_since_file "$LAST_CHECK_FILE")" -lt 0 ] || \
     [ "$(seconds_since_file "$LAST_CHECK_FILE")" -gt "$CHECK_INTERVAL_SECONDS" ]; then
    out=$(r check --read-data-subset=5% 2>&1); rc=$?
    now_iso > "$LAST_CHECK_FILE"
    [ $rc -eq 0 ] || { alert "weekly restic check FAILED (exit $rc)" "$out"; exit 1; }
  fi
}

do_prune() {
  exec 9>"$RUN_LOCK"; flock -w 1800 9 || exit 0
  load_env || exit 2
  local out rc
  # Retention per design §7, applied per tier so hourly estate snapshots do not crowd out code.
  out=$(restic -r "$RESTIC_REPOSITORY" -o rclone.program="$RCLONE_PROGRAM" -o rclone.args="$RCLONE_ARGS_PRUNE" \
          forget --group-by host,tags --keep-last 24 --keep-daily 30 --keep-weekly 12 --keep-monthly 24 --prune 2>&1)
  rc=$?
  [ $rc -eq 0 ] || { alert "weekly prune FAILED (exit $rc)" "$out"; exit 1; }
  log "prune ok"
}

do_report() {
  [ -f "$ALERT_FILE" ] && cat "$ALERT_FILE"
  exit 0
}

do_drill() {
  load_env || exit 2
  local scratch ref out
  scratch=$(mktemp -d "$STATE_DIR/drill.XXXXXX") || exit 1
  ref="$scratch/optmem-reference" out="$scratch/restore"
  [ -d "${OPTMEM_STORE:?set OPTMEM_STORE in the backup env file}" ] || exit 1
  cp -a "$OPTMEM_STORE" "$ref"
  r backup --tag drill "$ref" || exit 1
  r restore latest --tag drill --target "$out" || exit 1
  if diff -r --no-dereference "$ref" "$out$ref" >/dev/null 2>&1; then
    echo "DRILL A PASS: byte-identical round trip"
  else
    echo "DRILL A FAIL: restored copy differs from reference"; exit 1
  fi
  log "drill artifacts kept at $scratch"
}

case "${1:-}" in
  --run) do_run "${2:-estate}" ;;
  --prune) do_prune ;;
  --report) do_report ;;
  --drill) do_drill ;;
  *) echo "usage: $0 --run [estate|code] | --prune | --report | --drill" >&2; exit 2 ;;
esac
