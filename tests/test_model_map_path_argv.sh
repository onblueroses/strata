#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

home="$tmpdir/strata's"
mkdir -p "$home/.local/agent-venv/bin" "$home/bin/lib" "$home/config"
ln -s "$(command -v python3)" "$home/.local/agent-venv/bin/python"

cat >"$home/config/model-map.toml" <<'TOML'
[lanes]
fast = "model-fast"
strong = "model-strong"
grader = "model-grader"
breadth = "model-breadth"
TOML

cat >"$home/bin/lib/agent.py" <<'PY'
#!/usr/bin/env python3
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--model", required=True)
parser.add_argument("--prompt", default="")
parser.add_argument("--prompt-file")
parser.add_argument("--system")
args = parser.parse_args()
print(f"agent model: {args.model}")
PY

for lane in fast strong grader breadth; do
  out="$tmpdir/$lane.out"
  err="$tmpdir/$lane.err"

  if ! STRATA_HOME="$home" "$ROOT/bin/$lane" --timeout 5 "hello" >"$out" 2>"$err"; then
    echo "$lane failed with a quoted STRATA_HOME path" >&2
    cat "$err" >&2
    exit 1
  fi

  if ! grep -Fxq "agent model: model-$lane" "$out"; then
    echo "$lane did not pass the model read from model-map.toml" >&2
    cat "$out" >&2
    exit 1
  fi
done
