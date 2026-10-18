#!/usr/bin/env bash
# Paid-compute guard. Three callers, one script:
#   --check    systemd timer: does the network calls, writes state + ALERT, notifies
#   --report   SessionStart hook: reads the cached state only, never touches the network
#   --sanction NAME HOURS "reason"   declare a run legitimate for HOURS
#
# Why a sanction marker instead of an age threshold: CLAUDE.md already requires naming a
# background process's lifecycle before spawning. That rule failed silently on 2026-08-11
# when a paid process ran unattended for hours and drove the wallet negative. An age cutoff would
# be an invented number and would also kill legitimate long training. A declared expiry makes
# the existing rule checkable: unsanctioned or expired paid compute is the alert condition.
#
# What is a problem: unsanctioned or expired paid compute (a prime-agent process, a Prime
# pod, a Vast.ai instance) and Prime wallet movement that no sanctioned compute explains.
# A negative balance on its own is a standing fact, not an event: after 2026-08-11 it stayed
# negative while the critical notification fired repeatedly
# (the operator, 2026-09-22: spam). It is recorded as detail and becomes a problem only while
# paid compute is active, or when it drops, which is new spend.
#
# This guard alerts; it never kills. Training pods block termination until PULL_DONE exists
# (CLAUDE.md), so an auto-reaper here would be more dangerous than the drift it prevents.

set -uo pipefail

STATE_DIR="$HOME/.cache/paid-compute"
SANCTION_DIR="$STATE_DIR/sanctioned"
STATE_FILE="$STATE_DIR/state.txt"
ALERT_FILE="$STATE_DIR/ALERT"
BALANCE_FILE="$STATE_DIR/last-balance"
mkdir -p "$SANCTION_DIR"

# Paid processes to watch: name -> human label. Extend as new paid harnesses appear.
WATCH_PROCS=("prime-agent")

sanctioned() { # $1 = name; true when an unexpired marker exists
  local m="$SANCTION_DIR/$1"
  [[ -f "$m" ]] || return 1
  local until_ts
  until_ts=$(head -n1 "$m" 2>/dev/null | tr -dc '0-9')
  [[ -n "$until_ts" ]] || return 1
  (( until_ts > $(date +%s) ))
}

do_sanction() {
  local name="${1:?name}" hours="${2:?hours}" reason="${3:-unstated}"
  local until_ts=$(( $(date +%s) + hours * 3600 ))
  printf '%s\n%s\nsanctioned %s for %sh: %s\n' \
    "$until_ts" "$(date -d "@$until_ts" '+%Y-%m-%d %H:%M')" "$name" "$hours" "$reason" \
    > "$SANCTION_DIR/$name"
  echo "sanctioned $name until $(date -d "@$until_ts" '+%Y-%m-%d %H:%M') — $reason"
}

# Called from do_check only: bash scopes dynamically, so this appends to do_check's
# own active/sanctioned_active/problems arrays.
note_active() { # $1 = sanction name, $2 = problem text when unsanctioned
  active+=("$1")
  if sanctioned "$1"; then sanctioned_active+=("$1"); else problems+=("$2"); fi
}

do_check() {
  local problems=() detail=() active=() sanctioned_active=()

  # 1. Wallet: read now, judged after the compute checks below.
  local wallet balance='' prev=''
  if wallet=$(timeout 20 prime --plain wallet 2>/dev/null); then
    balance=$(printf '%s' "$wallet" | grep -oP 'Balance:\s*\$\K-?[0-9.]+' | head -1)
  fi
  if [[ -n "$balance" ]]; then
    detail+=("prime wallet \$$balance")
    prev=$(cat "$BALANCE_FILE" 2>/dev/null)
    printf '%s\n' "$balance" > "$BALANCE_FILE"
  else
    detail+=("prime wallet unreachable")
  fi

  # 2. Unsanctioned paid processes, with their age.
  local p pids oldest n
  for p in "${WATCH_PROCS[@]}"; do
    # Match the name at an argv start ("prime-agent ..." or ".../bin/prime-agent ..."), not
    # anywhere in a command line: a shell or editor merely mentioning it is not paid compute.
    pids=$(pgrep -f -- "(^|/)$p( |$)" 2>/dev/null) || continue
    [[ -n "$pids" ]] || continue
    n=$(printf '%s\n' "$pids" | wc -l)
    oldest=$(ps -o etime= -p "$(printf '%s' "$pids" | head -1)" 2>/dev/null | tr -d ' ')
    detail+=("$p: $n proc(s), oldest $oldest")
    note_active "$p" "$p running unsanctioned ($n procs, oldest $oldest) — declare it: guard-paid-compute.sh --sanction $p <hours> \"<reason>\""
  done

  # 3. Prime pods, same rule. Unreachable is unknown, not idle: recorded, never a verdict.
  local pods npods=''
  if pods=$(timeout 20 prime --plain pods list 2>/dev/null); then
    npods=$(printf '%s' "$pods" | grep -oP 'Total:\s*\K[0-9]+' | head -1)
    if [[ "${npods:-0}" -gt 0 ]]; then
      detail+=("prime pods: $npods")
      note_active "prime-pods" "$npods Prime pod(s) running unsanctioned — declare: guard-paid-compute.sh --sanction prime-pods <hours> \"<reason>\""
    fi
  else
    detail+=("prime pods unreachable")
  fi

  # 4. Vast.ai instances, same rule.
  if command -v vastai >/dev/null 2>&1; then
    local vi; vi=$(timeout 20 vastai show instances --raw 2>/dev/null | grep -c '"id"' || true)
    if [[ "${vi:-0}" -gt 0 ]]; then
      detail+=("vast.ai: $vi instance(s)")
      note_active "vastai" "$vi vast.ai instance(s) running unsanctioned"
    fi
  fi

  # 5. Wallet verdict. Overdrawn matters while anything paid runs, sanctioned or not;
  #    a drop with no sanctioned compute to explain it is spend the guard cannot see.
  if [[ -n "$balance" ]]; then
    if awk -v b="$balance" 'BEGIN{exit !(b<0)}'; then
      if (( ${#active[@]} )); then
        problems+=("Prime wallet OVERDRAWN at \$$balance while paid compute is active: ${active[*]}")
      else
        detail+=("overdrawn, idle: not alerting")
      fi
    fi
    if [[ -n "$prev" ]] && awk -v b="$balance" -v p="$prev" 'BEGIN{exit !(b<p)}' \
       && (( ${#sanctioned_active[@]} == 0 )); then
      problems+=("Prime wallet dropped from \$$prev to \$$balance with no sanctioned compute to explain it")
    fi
  fi

  { date '+%Y-%m-%d %H:%M:%S %Z'; printf '%s\n' "${detail[@]}"; } > "$STATE_FILE"

  if (( ${#problems[@]} )); then
    printf '%s\n' "${problems[@]}" > "$ALERT_FILE"
    command -v notify-send >/dev/null 2>&1 && \
      notify-send -u critical "Paid compute alert" "$(printf '%s\n' "${problems[@]}" | head -3)"
    printf '%s\n' "${problems[@]}"
    return 1
  fi
  rm -f "$ALERT_FILE"
  return 0
}

do_report() { # SessionStart: cached only, silent when healthy
  [[ -f "$ALERT_FILE" ]] || exit 0
  echo "PAID COMPUTE ALERT (checked $(head -n1 "$STATE_FILE" 2>/dev/null || echo 'unknown')):"
  sed 's/^/  /' "$ALERT_FILE"
  echo "  Sanction a legitimate run: ~/.claude/hooks/guard-paid-compute.sh --sanction <name> <hours> \"<reason>\""
}

case "${1:---report}" in
  --check)    do_check ;;
  --report)   do_report ;;
  --sanction) shift; do_sanction "$@" ;;
  *) echo "usage: $0 [--check|--report|--sanction NAME HOURS REASON]" >&2; exit 1 ;;
esac
