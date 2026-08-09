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
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--lane", required=True)
parser.add_argument("--model", required=True)
parser.add_argument("--prompt", default="")
parser.add_argument("--prompt-file")
parser.add_argument("--system")
parser.add_argument("--resume")
args = parser.parse_args()
stdin_prompt = ""
if not args.prompt and not args.prompt_file and not sys.stdin.isatty():
    stdin_prompt = sys.stdin.read().strip()
print(f"agent model: {args.model}")
print(f"agent lane: {args.lane}")
print(f"agent resume: {args.resume or ''}")
print(f"agent stdin: {stdin_prompt}")
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

  if ! grep -Fxq "agent lane: $lane" "$out"; then
    echo "$lane did not pass its symbolic lane name" >&2
    cat "$out" >&2
    exit 1
  fi

  if ! STRATA_HOME="$home" "$ROOT/bin/$lane" --timeout 5 \
    --resume 12345678-1234-4123-8123-123456789abc "follow-up" >"$out" 2>"$err"; then
    echo "$lane failed to pass --resume" >&2
    cat "$err" >&2
    exit 1
  fi

  if ! grep -Fxq "agent resume: 12345678-1234-4123-8123-123456789abc" "$out"; then
    echo "$lane did not pass the resume handle" >&2
    cat "$out" >&2
    exit 1
  fi

  if ! printf 'piped hello' | STRATA_HOME="$home" "$ROOT/bin/$lane" --timeout 5 >"$out" 2>"$err"; then
    echo "$lane failed with a piped stdin prompt" >&2
    cat "$err" >&2
    exit 1
  fi

  if ! grep -Fxq "agent stdin: piped hello" "$out"; then
    echo "$lane did not deliver piped stdin to the agent" >&2
    cat "$out" >&2
    exit 1
  fi
done
