#!/usr/bin/env bash
# Shared implementation for the lane shims in bin/.

set -uo pipefail

__lane_argv0="${STRATA_LANE_ARGV0:-${STRATA_LANE_SHIM:-$0}}"
LANE="${STRATA_LANE:-$(basename "$__lane_argv0")}"
case "$LANE" in
  strong|fast|grader|breadth) ;;
  *) echo "$LANE: unsupported lane executable" >&2; exit 1 ;;
esac

if [[ -n "${STRATA_LANE_SHIM:-}" ]]; then
  STRATA_HOME="${STRATA_HOME:-$(cd "$(dirname "$STRATA_LANE_SHIM")/.." && pwd)}"
else
  STRATA_HOME="${STRATA_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
fi
export STRATA_HOME

TIMEOUT=1800

__t_start=$(date +%s 2>/dev/null || echo 0)
# Trap invokes this function indirectly at shell exit.
# shellcheck disable=SC2329
__tel_emit() {
  [ "${STRATA_TELEMETRY:-0}" = "1" ] || return 0
  local emit="$STRATA_HOME/telemetry/telemetry-emit.sh"
  [ -r "$emit" ] || return 0
  local dur=$(( $(date +%s 2>/dev/null || echo 0) - __t_start ))
  "${BASH:-bash}" "$emit" delegation "${CLAUDE_SESSION_ID:-unknown}" \
    "$(printf '{"lane":"%s","exit":%s,"dur_s":%s}' "$LANE" "${1:-0}" "$dur")" >/dev/null 2>&1 || true
}
trap '__tel_emit $?' EXIT

print_help() {
  local summary
  case "$LANE" in
    strong) summary="heaviest reasoning lane" ;;
    fast) summary="cheap parallel code workhorse" ;;
    grader) summary="cheap parallel sanity-check lane" ;;
    breadth) summary="non-primary breadth lane / strong-lane fallback" ;;
  esac

  cat <<EOF
$LANE - $summary.

Reads the '$LANE' model id from \$STRATA_HOME/config/model-map.toml and
dispatches via the strata multi-provider agent.

Usage:
  $LANE "prompt"
  $LANE --file prompt.md
  echo "prompt" | $LANE

Flags:
  --file PATH       Read prompt from file
  --system TEXT     Override default system prompt
  --timeout SECS    Wall-clock timeout (default 1800)
  --effort VALUE    Accepted for compatibility; ignored
  --reasoning VALUE Accepted for compatibility; ignored
  --cache VALUE     Accepted for compatibility; ignored
  --max-tokens VAL  Accepted for compatibility; ignored
  --raw             Accepted for compatibility; ignored

Exit codes inherited from agent.py: 0 ok, 1 usage, 2 api, 3 quota, 4 auth, 5 empty.
EOF
}

require_operand() {
  if [[ $# -lt 2 ]]; then
    echo "$LANE: $1 requires a value" >&2
    exit 1
  fi
}

lookup_lane_model() {
  local model_map=$1
  local lane=$2

  "$VENV_PY" - "$model_map" "$lane" <<'PY'
import ast
import sys

path, lane = sys.argv[1], sys.argv[2]

try:
    import tomllib
except ImportError:
    tomllib = None

if tomllib is not None:
    with open(path, "rb") as f:
        data = tomllib.load(f)
    print(data.get("lanes", {}).get(lane, ""))
    raise SystemExit(0)


def strip_comment(value: str) -> str:
    quote = ""
    escaped = False
    for i, ch in enumerate(value):
        if escaped:
            escaped = False
            continue
        if quote:
            if quote == '"' and ch == "\\":
                escaped = True
            elif ch == quote:
                quote = ""
            continue
        if ch in ("'", '"'):
            quote = ch
        elif ch == "#":
            return value[:i].strip()
    return value.strip()


in_lanes = False
with open(path, encoding="utf-8") as f:
    for raw in f:
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            in_lanes = line == "[lanes]"
            continue
        if not in_lanes or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().strip('"').strip("'")
        if key != lane:
            continue
        value = strip_comment(value)
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            parsed = value.strip('"').strip("'")
        print(parsed if isinstance(parsed, str) else "")
        raise SystemExit(0)

print("")
PY
}

ARGS=()
PROMPT_FILE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --file) require_operand "$@"; PROMPT_FILE="$2"; shift 2 ;;
    --system) require_operand "$@"; ARGS+=(--system "$2"); shift 2 ;;
    --timeout) require_operand "$@"; TIMEOUT="$2"; shift 2 ;;
    --effort|--reasoning|--cache|--max-tokens) require_operand "$@"; shift 2 ;;
    --raw) shift ;;
    -h|--help) print_help; exit 0 ;;
    --) shift; ARGS+=(--prompt "$*"); break ;;
    -*) echo "$LANE: unknown flag: $1" >&2; exit 1 ;;
    *) ARGS+=(--prompt "$*"); break ;;
  esac
done

VENV_PY="$STRATA_HOME/.local/agent-venv/bin/python"
[[ -x "$VENV_PY" ]] || { echo "$LANE: agent venv missing at $VENV_PY - run bin/strata-init" >&2; exit 1; }

MODEL_MAP="$STRATA_HOME/config/model-map.toml"
[[ -f "$MODEL_MAP" ]] || { echo "$LANE: model-map missing: $MODEL_MAP" >&2; exit 1; }
MODEL=$(lookup_lane_model "$MODEL_MAP" "$LANE" 2>/dev/null)
if [[ -z "$MODEL" || "$MODEL" =~ ^\<PICK_ ]]; then
  echo "$LANE: lane '$LANE' unset or still placeholder ($MODEL)" >&2
  echo "  edit $MODEL_MAP and set [lanes].$LANE to a concrete model id" >&2
  exit 1
fi

if [[ -n "$PROMPT_FILE" ]]; then
  [[ -f "$PROMPT_FILE" ]] || { echo "$LANE: file not found: $PROMPT_FILE" >&2; exit 1; }
  ARGS+=(--prompt-file "$PROMPT_FILE")
fi

timeout "$TIMEOUT" "$VENV_PY" "$STRATA_HOME/bin/lib/agent.py" --model "$MODEL" "${ARGS[@]}"
EXIT=$?
if [[ "$EXIT" == "124" ]]; then
  echo "$LANE: timeout after ${TIMEOUT}s; remapping to exit 3 (treat as quota fallback)" >&2
  exit 3
fi
exit "$EXIT"
