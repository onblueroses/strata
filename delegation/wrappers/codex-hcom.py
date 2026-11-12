#!/usr/bin/env python3
"""Run a Codex turn through hcom and emit events for the delegate wrapper."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import tomllib
import uuid

# Sample value; set CODEX_HCOM_POLL_SECONDS (see runtime.env.example) to change how often the
# session's state is read.
POLL_SECONDS = float(os.environ.get("CODEX_HCOM_POLL_SECONDS", "1"))


def hcom(*args):
    env = os.environ.copy()
    # hcom starts a PTY, including when the calling shell has no interactive terminal.
    if env.get("TERM", "dumb") == "dumb":
        env["TERM"] = "xterm-256color"
    return subprocess.run(["hcom", *args], capture_output=True, text=True, env=env)


def emit(kind, **fields):
    print(json.dumps({"type": kind, **fields}), flush=True)


def interrupt(signum, frame):
    raise InterruptedError(f"Received signal {signum}")


def selected_directory(directory):
    if not directory:
        return None
    path = Path(directory).resolve(strict=True)
    if not path.is_dir():
        raise RuntimeError(f"The selected directory is not a folder: {path}")
    config = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "config.toml"
    if config.exists():
        projects = tomllib.loads(config.read_text()).get("projects", {})
        # Keep saved refusals, including a refusal on the enclosing repository.
        for parent in (path, *path.parents):
            if projects.get(str(parent), {}).get("trust_level") == "untrusted":
                raise RuntimeError(f"Codex trust was refused for {parent}. Review that folder in Codex before retrying.")
    return str(path)


def startup_screen(name):
    result = hcom("term", name, "--json")
    if result.returncode:
        raise RuntimeError(f"Cannot inspect Codex startup for {name}: {result.stderr or result.stdout}")
    return json.loads(result.stdout)


def check_startup(screen, info):
    lines = screen.get("lines", [])
    text = "\n".join(lines)
    if "Trust this folder?" in text or "Do you trust the contents of this directory?" in text:
        raise RuntimeError("Codex stopped at folder trust before prompt delivery. "
                           "Review and trust the folder in Codex, then retry.")
    if any(line.strip().startswith("enter ") and " · esc " in line for line in lines):
        raise RuntimeError(f"Codex needs startup attention before prompt delivery:\n{text}\n"
                           "Resolve this prompt in an interactive Codex launch, then retry.")
    if ("Waiting for startup" in text or "MCP startup" in text
            or "Starting MCP servers" in text or "esc to interrupt" in text):
        return
    # Codex can draw its footer before hcom receives the native session binding.
    configured = any("To get started, describe a task" in line
                     or ("Context " in line and "% used" in line) for line in lines)
    if (info.get("session_id") and configured and screen.get("ready") and screen.get("prompt_empty") is True
            and info.get("status") == "listening"):
        raise RuntimeError("Codex became idle without starting the supplied prompt. "
                           "Inspect the retained startup records and retry the explicit --cwd launch.")


def run(args):
    prompt = sys.stdin.read()
    # Each launch gets a private tag so cleanup can also find a partially started agent.
    tag = "delegate-" + uuid.uuid4().hex
    name = None
    launched = False
    stream = None
    log_path = None
    try:
        signal.signal(signal.SIGTERM, interrupt)
        signal.signal(signal.SIGINT, interrupt)
        directory = selected_directory(args.directory)
        launch_args = list(args.codex_args)
        if directory:
            # hcom changes cwd before Codex resolves its own -C argument.
            for index, value in enumerate(launch_args[:-1]):
                if value == "-C":
                    launch_args[index + 1] = directory
        directory_args = ["--dir", directory] if directory else []
        launched = True
        result = hcom("codex", "--headless", "--go", "--json", "--tag", tag,
                      *directory_args, "--hcom-prompt", prompt, "--", *launch_args)
        try:
            launch = json.loads(result.stdout)
        except ValueError:
            raise RuntimeError(f"hcom did not return a launch result: {result.stderr or result.stdout}")
        log_path = next(iter(launch.get("log_files", [])), None)
        names = launch.get("names", [])
        if len(names) == 1:
            name = names[0]
            print(f"hcom: {name}", file=os.fdopen(os.dup(3), "w"), flush=True)
        if result.returncode not in (0, 2) or not name or launch.get("failed"):
            raise RuntimeError(f"hcom launch failed: {result.stderr or result.stdout}")
        with os.fdopen(os.dup(3), "w") as progress:
            print(f"hcom: {name} waiting for prompt delivery; inspect with hcom term {name}",
                  file=progress, flush=True)
        usage = None
        completed = False
        started = False
        final = ""
        while True:
            result = hcom("list", name, "--json")
            if result.returncode:
                raise RuntimeError(f"hcom lost {name}: {result.stderr}")
            info = json.loads(result.stdout)
            log_path = info.get("background_log_file") or log_path
            screen = startup_screen(name) if not started else None
            if screen and screen.get("ready") and screen.get("prompt_empty") is True:
                # Refresh after the screen snapshot so a new rollout can supply its receipt.
                result = hcom("list", name, "--json")
                if result.returncode:
                    raise RuntimeError(f"hcom lost {name}: {result.stderr or result.stdout}")
                info = json.loads(result.stdout)
            path = info.get("transcript_path")
            if stream is None and path and Path(path).is_file():
                stream = open(path, encoding="utf-8")
                emit("thread.started", thread_id=info.get("session_id"))
            if stream:
                while True:
                    position = stream.tell()
                    line = stream.readline()
                    if not line.endswith("\n"):
                        stream.seek(position)
                        break
                    entry = json.loads(line)
                    payload = entry.get("payload", {})
                    if entry.get("type") != "event_msg":
                        continue
                    kind = payload.get("type")
                    if kind == "task_started":
                        started = True
                        completed = False
                        final = ""
                        emit("turn.started")
                        with os.fdopen(os.dup(3), "w") as progress:
                            print(f"hcom: {name} prompt turn started", file=progress, flush=True)
                    elif kind == "agent_message":
                        emit("item.completed", item={"type": "agent_message", "text": payload.get("message", "")})
                    elif kind == "token_count":
                        usage = (payload.get("info") or {}).get("total_token_usage")
                    elif kind == "task_complete" and started:
                        completed = True
                        final = payload.get("last_agent_message") or ""
                    elif kind in ("error", "turn_aborted"):
                        emit("error", message=payload.get("message", kind))
                        raise RuntimeError(f"Codex reported {kind}")
            if not started:
                check_startup(screen, info)
            if completed and info.get("status") == "listening":
                Path(args.last_message).write_text(final)
                fields = {"usage": usage} if usage else {}
                emit("turn.completed", **fields)
                return 0
            if info.get("status") in ("blocked", "inactive"):
                raise RuntimeError(f"hcom {name} is {info['status']}: {info.get('status_detail', '')}")
            # Observation interval only; the wrapper's --timeout controls the run duration.
            time.sleep(POLL_SECONDS)
    except InterruptedError as error:
        print(error, file=sys.stderr)
        return 130
    except (OSError, ValueError, RuntimeError) as error:
        print(error, file=sys.stderr)
        if log_path and Path(log_path).is_file():
            print(Path(log_path).read_text(errors="replace"), file=sys.stderr)
        return 1
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        if stream:
            stream.close()
        if launched:
            cleanup = hcom("kill", name or f"tag:{tag}", "--json")
            if cleanup.returncode:
                print(f"hcom cleanup failed for {name or tag}: {cleanup.stderr or cleanup.stdout}", file=sys.stderr)
                return 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--last-message", required=True)
    parser.add_argument("--directory", default="")
    parser.add_argument("codex_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.codex_args[:1] == ["--"]:
        args.codex_args.pop(0)
    sys.exit(run(args))
