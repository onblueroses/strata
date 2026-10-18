#!/usr/bin/env bash
# lib-orphan-scope.sh - shared process-selection logic for ownership-scoped reaping.
#
# Why this exists: a name-based sweep (`pkill -f codex`, `ps | grep codex`) reaps
# processes owned by OTHER live sessions on the same host. Every reaper here must
# prove the owner is gone before it kills anything; age and command name alone are
# not evidence of orphanhood (2026-07-27 cross-session reaping audit).
#
# The selection reads a process table on stdin so a test can drive it with a
# synthetic table and never touch a real process:
#   pid ppid sid etimes args...
# Emit with: ps -eo pid=,ppid=,sid=,etimes=,args=

# has_live_ancestor <pid> <ancestor-basename> <table-file>
# Walks the ppid chain upward. Returns 0 when an ancestor process whose executable
# basename matches the name is present in the table (= still alive).
has_live_ancestor() {
  local pid="$1" want="$2" table="$3"
  local hops=0 row ppid args base
  while [[ "$pid" -gt 1 && "$hops" -lt 64 ]]; do
    row="$(awk -v p="$pid" '$1==p {ppid=$2; $1=$2=$3=$4=""; sub(/^ +/,""); print ppid " " $0; exit}' "$table")"
    [[ -n "$row" ]] || return 1   # pid absent from the table: the chain is broken, owner gone
    ppid="${row%% *}"
    args="${row#* }"
    base="${args%% *}"; base="${base##*/}"
    [[ "$base" == "$want" ]] && return 0
    [[ "$ppid" =~ ^[0-9]+$ ]] || return 1
    pid="$ppid"
    hops=$((hops + 1))
  done
  return 1
}

# is_codex_subcommand <subcommand> <args-string>
# Command-position match: finds the token whose basename is `codex` and compares the
# NEXT token to the wanted subcommand. Substring matching would fire on prompt text
# and on filenames such as `f8-review.md` (the 2026-07-27 false-positive class).
is_codex_subcommand() {
  local want="$1" argstr="$2"
  local -a toks=()
  read -r -a toks <<< "$argstr"
  local i base
  for ((i = 0; i < ${#toks[@]}; i++)); do
    base="${toks[i]##*/}"
    if [[ "$base" == "codex" ]]; then
      [[ "${toks[i + 1]:-}" == "$want" ]] && return 0
      return 1
    fi
  done
  return 1
}

# descendants <pid> <table-file>: every pid below this one, breadth-first.
descendants() {
  local frontier="$1" table="$2"
  local next kid
  while [[ -n "$frontier" ]]; do
    next=""
    for kid in $(awk -v parents=" $frontier " '{ if (index(parents, " " $2 " ")) print $1 }' "$table"); do
      printf '%s\n' "$kid"
      next="$next $kid"
    done
    frontier="${next# }"
  done
}

# has_recent_descendant <pid> <max_age_seconds> <table-file>
# Returns 0 when the subtree holds a process younger than max_age: positive evidence
# that something is still driving this process, so it is in use rather than abandoned.
has_recent_descendant() {
  local pid="$1" max_age="$2" table="$3"
  local kid etimes
  for kid in $(descendants "$pid" "$table"); do
    etimes="$(awk -v p="$kid" '$1==p {print $4; exit}' "$table")"
    [[ "$etimes" =~ ^[0-9]+$ ]] || continue
    (( etimes < max_age )) && return 0
  done
  return 1
}

# select_orphaned_codex <subcommand> <min_age_seconds>
# Reads the process table on stdin, prints the pids that are safe to reap.
# A pid is emitted only when ALL of these hold:
#   1. the process runs `codex <subcommand>` in command position
#   2. it is older than min_age_seconds
#   3. it is not its own session leader (pid != sid): a `setsid`-detached job has a
#      deliberate lifetime that outlives its launcher on purpose
#   4. no live `claude` process appears anywhere in its ancestor chain, which is the
#      positive evidence that the owning session died
select_orphaned_codex() {
  local want="$1" min_age="$2"
  local table
  table="$(mktemp)"
  cat > "$table"

  local pid ppid sid etimes args
  while read -r pid ppid sid etimes args; do
    [[ "$pid" =~ ^[0-9]+$ ]] || continue
    [[ "$etimes" =~ ^[0-9]+$ ]] || continue
    (( etimes > min_age )) || continue
    is_codex_subcommand "$want" "$args" || continue
    [[ "$pid" != "$sid" ]] || continue
    has_live_ancestor "$pid" claude "$table" && continue
    printf '%s\n' "$pid"
  done < "$table"

  rm -f "$table"
}
