#!/usr/bin/env bash
# Guard for an externally installed dsh-primary. This file never calls a provider by itself.
set -euo pipefail

launcher=${DSH_PRIMARY_BIN:-dsh-primary}
paid=0
dry_flag=""
forward=()
for argument in "$@"; do
  case "$argument" in
    --confirm-spend) paid=1; forward+=("$argument") ;;
    --print-prompt|--help) dry_flag="$argument" ;;
    *) forward+=("$argument") ;;
  esac
done

if [[ -n "$dry_flag" ]]; then
  exec "$launcher" "$dry_flag" "${forward[@]}"
fi

if (( paid == 0 )); then
  echo "launch-adapter: paid dispatch refused; use --print-prompt or --help for offline inspection, or pass --confirm-spend after authorization" >&2
  exit 77
fi

exec "$launcher" "${forward[@]}"
