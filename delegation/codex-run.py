#!/usr/bin/env python3
"""Portable form of the local codex-fast / codex-strong delegation wrappers."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid
import math

MODELS = {"fast": ("gpt-5.6-luna", "medium"),
          "bounded": ("gpt-5.6-terra", "high"),
          "strong": ("gpt-5.6-sol", "xhigh")}
BOUNDARY = (
    "You are a delegated worker, not the user-facing primary. Follow the bounded brief "
    "and applicable repository instructions. Other agents may edit the tree; do not revert "
    "their work. Never write or compact shared memory, send messages externally, commit, "
    "or push. Return findings, verification, and memory candidates to the primary."
)


def stop(child):
    if child.poll() is None:
        os.killpg(child.pid, signal.SIGTERM)
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
            child.wait()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tier", choices=MODELS)
    parser.add_argument("prompt", nargs="?")
    parser.add_argument("--file", type=Path)
    parser.add_argument("--cwd", type=Path, default=Path.cwd())
    parser.add_argument("--sandbox", choices=["read-only", "workspace-write"], default="read-only")
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        parser.error("timeout must be positive")
    if args.file and args.prompt:
        parser.error("choose a prompt argument or --file")
    prompt = args.file.read_text() if args.file else args.prompt
    if prompt is None:
        prompt = sys.stdin.read()
    if not prompt.strip():
        parser.error("prompt is empty")
    cwd = args.cwd.resolve(strict=True)
    if not cwd.is_dir():
        parser.error("cwd must be a directory")
    model, effort = MODELS[args.tier]
    command = ["codex", "exec", "-c", 'model_provider="openai"',
               "-c", f'model_reasoning_effort="{effort}"',
               "-c", 'approval_policy="never"',
               "-c", 'developer_instructions=' + json.dumps(BOUNDARY),
               "--model", model, "--sandbox", args.sandbox, "--json", "-"]
    if args.dry_run:
        print(json.dumps({"argv": command, "cwd": str(cwd), "prompt_source": "stdin",
                          "provider": "openai", "model": model}))
        return 0
    login = subprocess.run(["codex", "login", "status"], capture_output=True, text=True, timeout=10)
    if login.returncode or "Logged in using ChatGPT" not in login.stdout + login.stderr:
        print("Refused: verify a ChatGPT subscription login; no API/provider fallback.", file=sys.stderr)
        return 2
    # Preserve durable outputs under repo-local scratch, never in the public tree.
    os.umask(0o077)
    output = cwd / ".local" / "delegation" / (time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:8])
    output.mkdir(parents=True)
    print(f"progress {output / 'events.jsonl'}", file=sys.stderr, flush=True)
    child = None
    try:
        with (output / "events.jsonl").open("w") as events, (output / "stderr.log").open("w") as errors:
            child = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE, stdout=events,
                                     stderr=errors, text=True, start_new_session=True,
                                     env={**os.environ, "STRATA_AGENT_ROLE": "delegate"})
            child.communicate(prompt, timeout=args.timeout)
            code = child.returncode
    except (KeyboardInterrupt, subprocess.TimeoutExpired):
        if child is not None:
            stop(child)
        print("Stopped delegate; produced artifacts retained.", file=sys.stderr)
        return 130
    except OSError as exc:
        print(f"Delegate could not start: {exc}", file=sys.stderr)
        return 2
    for line in (output / "events.jsonl").read_text().splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "thread.started":
            print("session " + str(event.get("thread_id", "unknown")), file=sys.stderr)
    print(f"exit {code}; artifacts {output}", file=sys.stderr)
    return code


def interrupt(_signum, _frame):
    raise KeyboardInterrupt


if __name__ == "__main__":
    signal.signal(signal.SIGTERM, interrupt)
    signal.signal(signal.SIGHUP, interrupt)
    raise SystemExit(main())
