#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

assert_missing_operand() {
  local script=$1
  local flag=$2
  local out="$tmpdir/out"
  local err="$tmpdir/err"

  : >"$out"
  : >"$err"
  if "$ROOT/$script" "$flag" >"$out" 2>"$err"; then
    echo "expected $script $flag to fail" >&2
    exit 1
  fi

  if grep -qi 'unbound variable' "$err"; then
    echo "$script $flag leaked an unbound variable error" >&2
    cat "$err" >&2
    exit 1
  fi

  if ! grep -Fq 'requires a value' "$err"; then
    echo "$script $flag did not report a controlled missing operand" >&2
    cat "$err" >&2
    exit 1
  fi
}

for flag in --project --slug --agent --brief --branch-from --permission-mode --session; do
  assert_missing_operand bin/dmux-dispatch.sh "$flag"
done

for script in bin/fast bin/strong bin/grader bin/breadth; do
  for flag in --file --resume --system --timeout --effort --reasoning --cache --max-tokens; do
    assert_missing_operand "$script" "$flag"
  done
done
