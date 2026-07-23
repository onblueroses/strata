#!/usr/bin/env python3
# pyright: reportMissingImports=false
# Imports resolve only after `strata-init` builds the agent venv at
# $STRATA_HOME/.local/agent-venv. Static checkers run against the system
# Python cannot see them; the wrappers invoke the venv Python directly.
"""Strata lane agent — multi-provider pydantic-ai harness.

Routes by model-id prefix to Anthropic, OpenAI, DeepSeek, or Google.
Gives the model bash, file, list, grep, and read tools so it can act on
the working directory instead of just answering in text.

Invocation: typically through the bin/strong | bin/fast | bin/grader | bin/breadth
bash wrappers, which read lane → model from config/model-map.toml and call:

    python agent.py --lane strong --model <model-id> < prompt.md

Exit codes:
    0  success — final answer on stdout
    1  usage error
    2  API / model error
    3  rate limit / quota exhausted (caller should fall back)
    4  auth error (missing or rejected API key)
    5  empty content from model (after one re-prompt attempt)
    130 interrupted — resume the emitted session id to steer
"""

from __future__ import annotations

import argparse
import asyncio
import fcntl
import json
import os
import re
import signal
import sys
import time
import uuid
from collections.abc import AsyncIterable, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, RunContext
from pydantic_ai.messages import (
    AgentStreamEvent,
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelResponse,
    ToolCallPart,
    ToolReturnPart,
)
from pydantic_core import to_jsonable_python


SESSION_ID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
LANE_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


class LaneAgentError(Exception):
    """An expected lane failure with a public exit code."""

    def __init__(self, exit_code: int, message: str) -> None:
        super().__init__(message)
        self.exit_code = exit_code


class LaneInterrupted(Exception):
    """The current lane turn was interrupted by SIGINT or SIGTERM."""


async def terminate_process(process: asyncio.subprocess.Process) -> None:
    """Terminate one subprocess group and escalate when it does not exit."""
    if process.returncode is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    try:
        await asyncio.wait_for(process.wait(), timeout=2)
    except asyncio.TimeoutError:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            return
        await process.wait()


async def communicate_with_timeout(
    process: asyncio.subprocess.Process, timeout_seconds: int
) -> bytes:
    """Collect combined output and clean up the process group on every abort."""
    try:
        stdout, _ = await asyncio.wait_for(
            process.communicate(), timeout=timeout_seconds
        )
        return stdout
    except BaseException:
        await terminate_process(process)
        raise


def strata_home() -> Path:
    """Return the configured install root or infer it from this script."""
    configured = os.environ.get("STRATA_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2]


def ensure_private_dir(path: Path) -> None:
    """Create a local state directory readable only by the current user."""
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)


def validate_lane(lane: str) -> str:
    """Validate a lane name before using it in local filenames."""
    if not LANE_PATTERN.fullmatch(lane):
        raise LaneAgentError(1, f"invalid lane name: {lane!r}")
    return lane


def validate_session_id(session_id: str) -> str:
    """Validate and normalize a UUID session handle."""
    normalized = session_id.lower()
    if not SESSION_ID_PATTERN.fullmatch(normalized):
        raise LaneAgentError(1, f"invalid session id: {session_id!r}")
    return normalized


def session_path(session_dir: Path, lane: str, session_id: str) -> Path:
    """Return the session file for a validated lane and id."""
    return session_dir / f"{validate_lane(lane)}-{validate_session_id(session_id)}.json"


def resolve_session_file(session_dir: Path, lane: str, resume: str) -> Path:
    """Resolve an explicit session id or the newest session for one lane."""
    validate_lane(lane)
    if resume != "last":
        path = session_path(session_dir, lane, resume)
        if not path.is_file():
            raise LaneAgentError(1, f"session not found: {resume}")
        return path

    candidates = [
        path
        for path in session_dir.glob(f"{lane}-*.json")
        if path.is_file()
        and SESSION_ID_PATTERN.fullmatch(
            path.name.removeprefix(f"{lane}-").removesuffix(".json")
        )
    ]
    if not candidates:
        raise LaneAgentError(1, f"no saved session for lane '{lane}'")
    return max(candidates, key=lambda path: (path.stat().st_mtime_ns, path.name))


def session_id_from_path(path: Path, lane: str) -> str:
    """Extract a validated session id from a lane session filename."""
    name = path.name
    prefix = f"{lane}-"
    if not name.startswith(prefix) or not name.endswith(".json"):
        raise LaneAgentError(1, f"invalid session filename: {name}")
    return validate_session_id(name[len(prefix) : -len(".json")])


def lock_session(path: Path) -> int:
    """Claim one session exclusively for this run.

    A resumed turn reads the whole history and writes the whole history back, so
    two concurrent runs on one session would each persist over the other and drop
    a completed turn. Refuse the second run instead of losing its history.
    """
    lock_path = path.with_name(f"{path.name}.lock")
    fd = os.open(lock_path, os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        os.close(fd)
        raise LaneAgentError(
            1,
            f"session '{path.stem}' is busy in another run; "
            "wait for it to finish or resume a different session",
        ) from error
    return fd


def persist_history(path: Path, messages: Sequence[ModelMessage]) -> None:
    """Atomically persist native pydantic-ai message history as JSON."""
    payload = ModelMessagesTypeAdapter.dump_json(list(messages), indent=2)
    temp = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    finally:
        try:
            temp.unlink()
        except FileNotFoundError:
            pass


def load_history(path: Path) -> list[ModelMessage]:
    """Load and validate native pydantic-ai message history."""
    try:
        return ModelMessagesTypeAdapter.validate_json(path.read_bytes())
    except (OSError, ValueError) as error:
        raise LaneAgentError(1, f"cannot load session '{path.name}': {error}") from error


def close_interrupted_tool_calls(
    messages: Sequence[ModelMessage],
) -> list[ModelMessage]:
    """Close pending function calls so the saved history accepts a new turn."""
    history = list(messages)
    if not history or not isinstance(history[-1], ModelResponse):
        return history

    response = history[-1]
    tool_calls = [
        part for part in response.parts if isinstance(part, ToolCallPart)
    ]
    if not tool_calls:
        return history

    returns = [
        ToolReturnPart(
            tool_name=part.tool_name,
            tool_call_id=part.tool_call_id,
            content="Tool execution was interrupted before completion.",
            outcome="interrupted",
        )
        for part in tool_calls
    ]
    history.append(
        ModelRequest(
            parts=returns,
            run_id=response.run_id,
            conversation_id=response.conversation_id,
        )
    )
    return history


def prune_progress_files(progress_dir: Path, max_age_days: int = 7) -> None:
    """Best-effort prune progress files older than the retention window."""
    cutoff = time.time() - max_age_days * 24 * 60 * 60
    try:
        for path in progress_dir.iterdir():
            try:
                if path.is_file() and path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                continue
    except OSError:
        pass


class ProgressWriter:
    """Flush JSONL progress events so another process can tail the run."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle = path.open("a", encoding="utf-8", buffering=1)
        os.chmod(path, 0o600)

    def write(self, event_type: str, payload: Any = None) -> None:
        record: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": event_type,
        }
        if payload is not None:
            record["payload"] = to_jsonable_python(payload)
        self._handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._handle.flush()

    def close(self) -> None:
        self._handle.close()


def create_progress_writer(
    progress_dir: Path, lane: str, session_id: str
) -> ProgressWriter:
    """Create a unique progress file for one lane turn."""
    ensure_private_dir(progress_dir)
    prune_progress_files(progress_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = progress_dir / f"{stamp}-{lane}-{session_id}.jsonl"
    return ProgressWriter(path)


@dataclass
class RunState:
    """Mutable state that survives cancellation of the agent coroutine."""

    session_file: Path
    progress: ProgressWriter
    messages: Sequence[ModelMessage]
    interrupted_signal: int | None = None

    def persist(self) -> None:
        persist_history(self.session_file, self.messages)

    async def stream_events(
        self,
        context: RunContext[Any],
        events: AsyncIterable[AgentStreamEvent],
    ) -> None:
        """Mirror native events and keep a live reference to run messages."""
        self.messages = context.messages
        self.persist()
        try:
            async for event in events:
                self.progress.write(event.event_kind, event)
        finally:
            self.messages = context.messages
            self.persist()


def load_env_file(path: Path) -> None:
    """Source a KEY=VALUE .env file into os.environ. Lines starting with # are ignored."""
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def resolve_api_key(env_var: str) -> str:
    """Read api key from env, with fallback to strata's local .env file."""
    key = os.environ.get(env_var)
    if key:
        return key
    strata_home = os.environ.get("STRATA_HOME")
    if strata_home:
        load_env_file(Path(strata_home) / ".local" / ".env")
        key = os.environ.get(env_var)
        if key:
            return key
    raise LaneAgentError(
        4,
        f"{env_var} missing — set it in env or in $STRATA_HOME/.local/.env",
    )


def build_model(model_name: str):
    """Pick the right provider + model class based on model-id prefix."""
    name = model_name.strip()

    if name.startswith("claude-") or name.startswith("anthropic/"):
        from pydantic_ai.models.anthropic import AnthropicModel
        from pydantic_ai.providers.anthropic import AnthropicProvider

        api_key = resolve_api_key("ANTHROPIC_API_KEY")
        stripped = name.removeprefix("anthropic/")
        return AnthropicModel(stripped, provider=AnthropicProvider(api_key=api_key))

    if name.startswith("deepseek-"):
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.deepseek import DeepSeekProvider

        api_key = resolve_api_key("DEEPSEEK_API_KEY")
        # DeepSeek thinking tool loops require every reasoning_content value on
        # later requests. DeepSeekProvider profiles that field as a ThinkingPart
        # and OpenAIChatModel sends it back under the same field.
        return OpenAIChatModel(name, provider=DeepSeekProvider(api_key=api_key))

    if name.startswith("gemini-") or name.startswith("google/"):
        from pydantic_ai.models.google import GoogleModel
        from pydantic_ai.providers.google import GoogleProvider

        api_key = resolve_api_key("GEMINI_API_KEY")
        stripped = name.removeprefix("google/")
        return GoogleModel(stripped, provider=GoogleProvider(api_key=api_key))

    if (
        name.startswith("gpt-")
        or name.startswith("openai/")
        or name.startswith("o1")
        or name.startswith("o3")
    ):
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        api_key = resolve_api_key("OPENAI_API_KEY")
        stripped = name.removeprefix("openai/")
        return OpenAIChatModel(stripped, provider=OpenAIProvider(api_key=api_key))

    # Allow explicit provider prefix as a generic escape hatch.
    if "/" in name:
        provider_prefix = name.split("/", 1)[0]
        raise LaneAgentError(
            1,
            f"unknown provider prefix '{provider_prefix}'",
        )

    raise LaneAgentError(
        1,
        f"cannot infer provider from model id '{name}'. "
        "Use a prefix (claude-, gpt-, deepseek-, gemini-) or qualify as provider/model.",
    )


def build_agent(model_name: str, system_prompt: str | None) -> Agent:
    model = build_model(model_name)

    default_system = (
        "You are an autonomous coding agent with bash, file, and grep tools. "
        "When the user asks a question that requires reading files, listing directories, "
        "or running commands, USE YOUR TOOLS — do not refuse or ask permission. "
        "Read whatever files you need, run whatever commands clarify the situation, "
        "then ALWAYS produce a final text answer. The final answer is mandatory: "
        "summarize what you did, what you found, and the verdict — even if the work "
        "was completed entirely through tool calls. Empty replies are a bug. Be terse "
        "(no preamble, no closing fluff), but do not be silent."
    )
    agent = Agent(model, system_prompt=system_prompt or default_system, retries=2)

    @agent.tool_plain
    def read_file(path: str) -> str:
        """Read a text file from disk and return its contents."""
        try:
            return Path(path).expanduser().read_text()
        except FileNotFoundError:
            return f"ERROR: file not found: {path}"
        except Exception as e:
            return f"ERROR: {type(e).__name__}: {e}"

    @agent.tool_plain
    def write_file(path: str, content: str) -> str:
        """Write text content to a file. Creates parent dirs. Overwrites existing."""
        p = Path(path).expanduser()
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
            return f"wrote {len(content)} bytes to {path}"
        except Exception as e:
            return f"ERROR: {type(e).__name__}: {e}"

    @agent.tool_plain
    def list_dir(path: str = ".") -> str:
        """List entries in a directory. Returns one entry per line with type prefix."""
        try:
            entries = sorted(Path(path).expanduser().iterdir())
            return "\n".join(f"{'d' if e.is_dir() else 'f'} {e.name}" for e in entries)
        except Exception as e:
            return f"ERROR: {type(e).__name__}: {e}"

    @agent.tool_plain
    async def run_bash(command: str, timeout_seconds: int = 60) -> str:
        """Run a bash command. Returns combined stdout+stderr (truncated to 8KB) and exit code."""
        try:
            process = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
            )
            raw_output = await communicate_with_timeout(process, timeout_seconds)
            output = raw_output.decode(errors="replace")[:8192]
            return f"exit={process.returncode}\n{output}"
        except asyncio.TimeoutError:
            return f"ERROR: command timed out after {timeout_seconds}s"
        except asyncio.CancelledError:
            raise
        except Exception as e:
            return f"ERROR: {type(e).__name__}: {e}"

    @agent.tool_plain
    async def grep(
        pattern: str, path: str = ".", case_insensitive: bool = False
    ) -> str:
        """Search for a regex pattern recursively. Returns matching lines (max 4KB)."""
        cmd = ["rg", "--no-heading", "--line-number", "--color=never"]
        if case_insensitive:
            cmd.append("-i")
        cmd += [pattern, path]
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
            )
            raw_output = await communicate_with_timeout(process, 30)
            return raw_output.decode(errors="replace")[:4096] or "(no matches)"
        except FileNotFoundError:
            return "ERROR: ripgrep (rg) not installed"
        except asyncio.TimeoutError:
            return "ERROR: ripgrep timed out after 30s"
        except asyncio.CancelledError:
            raise
        except Exception as e:
            return f"ERROR: {type(e).__name__}: {e}"

    return agent


async def run_agent_turn(
    agent: Agent,
    prompt: str,
    history: Sequence[ModelMessage],
    session_id: str,
    state: RunState,
) -> str:
    """Run one turn with native event streaming and durable history updates."""
    result = await agent.run(
        prompt,
        message_history=history,
        conversation_id=session_id,
        event_stream_handler=state.stream_events,
    )
    state.messages = result.all_messages()
    state.persist()
    text = result.output if hasattr(result, "output") else str(result)
    if text and str(text).strip():
        return str(text)

    followup = await agent.run(
        "You returned no text. Produce the mandatory final answer now: "
        "what did you do, what did you find, and what is the verdict? "
        "Reply in plain text under 200 words.",
        message_history=result.all_messages(),
        conversation_id=session_id,
        event_stream_handler=state.stream_events,
    )
    state.messages = followup.all_messages()
    state.persist()
    text = followup.output if hasattr(followup, "output") else str(followup)
    return str(text) if text else ""


async def run_interruptible(
    agent: Agent,
    prompt: str,
    history: Sequence[ModelMessage],
    session_id: str,
    state: RunState,
) -> str:
    """Cancel the active turn when the process receives SIGINT or SIGTERM."""
    loop = asyncio.get_running_loop()
    task = asyncio.current_task()

    def request_interrupt(signum: int) -> None:
        state.interrupted_signal = signum
        if task is not None:
            task.cancel()

    installed: list[signal.Signals] = []
    for signum in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(signum, request_interrupt, signum)
            installed.append(signum)
        except (NotImplementedError, RuntimeError):
            continue

    try:
        return await run_agent_turn(agent, prompt, history, session_id, state)
    except asyncio.CancelledError as error:
        if state.interrupted_signal is not None:
            raise LaneInterrupted from error
        raise
    finally:
        for signum in installed:
            loop.remove_signal_handler(signum)


def classify_exception(error: Exception) -> int:
    """Map provider failures to the stable lane exit contract."""
    msg = str(error)
    if "429" in msg or "rate limit" in msg.lower() or "quota" in msg.lower():
        return 3
    if "401" in msg or "403" in msg or "auth" in msg.lower():
        return 4
    return 2


def main() -> int:
    parser = argparse.ArgumentParser(description="Strata lane agent — multi-provider")
    parser.add_argument("--lane", default="agent", help="Symbolic lane name")
    parser.add_argument(
        "--model", required=True, help="Model id; provider inferred by prefix"
    )
    parser.add_argument("--resume", help="Resume a session id or the latest lane session")
    parser.add_argument("--prompt-file", help="Read prompt from file")
    parser.add_argument("--system", help="Override system prompt")
    parser.add_argument("--prompt", help="Inline prompt (else stdin)")
    args = parser.parse_args()

    if args.prompt:
        prompt = args.prompt
    elif args.prompt_file:
        try:
            prompt = Path(args.prompt_file).read_text()
        except OSError as e:
            detail = e.strerror or str(e)
            print(
                f"strata-agent: cannot read prompt file '{args.prompt_file}': {detail}",
                file=sys.stderr,
            )
            return 1
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read()
    else:
        print(
            "strata-agent: no prompt (use --prompt, --prompt-file, or stdin)",
            file=sys.stderr,
        )
        return 1

    if not prompt.strip():
        print("strata-agent: empty prompt", file=sys.stderr)
        return 1

    state: RunState | None = None
    session_id = ""
    session_lock: int | None = None
    lane = args.lane
    try:
        validate_lane(lane)
        local_dir = strata_home() / ".local"
        session_dir = local_dir / "lane-sessions"
        progress_dir = local_dir / "progress"
        ensure_private_dir(session_dir)

        if args.resume:
            saved_path = resolve_session_file(session_dir, lane, args.resume)
            session_id = session_id_from_path(saved_path, lane)
        else:
            session_id = str(uuid.uuid4())
            saved_path = session_path(session_dir, lane, session_id)

        session_lock = lock_session(saved_path)
        history = load_history(saved_path) if args.resume else []

        persist_history(saved_path, history)
        progress = create_progress_writer(progress_dir, lane, session_id)
        state = RunState(saved_path, progress, history)
        state.progress.write(
            "run_started",
            {"lane": lane, "session_id": session_id, "resumed": bool(args.resume)},
        )
        print(f"{lane}: progress {progress.path}", file=sys.stderr, flush=True)

        agent = build_agent(args.model, args.system)
        text = asyncio.run(
            run_interruptible(agent, prompt, history, session_id, state)
        )
        if not text.strip():
            state.progress.write("empty_output")
            return 5
        state.progress.write("final_output", {"output": text})
        sys.stdout.write(text)
        sys.stdout.write("\n")
        return 0
    except LaneInterrupted:
        if state is not None:
            state.messages = close_interrupted_tool_calls(state.messages)
            state.persist()
            state.progress.write(
                "interrupted", {"signal": state.interrupted_signal or signal.SIGTERM}
            )
        print(
            f'{lane}: interrupted; steer with: {lane} --resume {session_id} "correction"',
            file=sys.stderr,
            flush=True,
        )
        return 130
    except LaneAgentError as error:
        if state is not None:
            state.progress.write("error", {"message": str(error)})
        print(f"strata-agent: {error}", file=sys.stderr)
        return error.exit_code
    except Exception as error:
        exit_code = classify_exception(error)
        if state is not None:
            state.progress.write(
                "error",
                {"error_type": type(error).__name__, "message": str(error)},
            )
        if exit_code == 3:
            label = "rate limited"
        elif exit_code == 4:
            label = "auth error"
        else:
            label = type(error).__name__
        print(f"strata-agent: {label}: {error}", file=sys.stderr)
        return exit_code
    finally:
        try:
            if state is not None:
                try:
                    state.persist()
                finally:
                    state.progress.close()
                print(
                    f"{lane}: session {session_id} "
                    f'(resume: {lane} --resume {session_id} "...")',
                    file=sys.stderr,
                    flush=True,
                )
        finally:
            if session_lock is not None:
                os.close(session_lock)


if __name__ == "__main__":
    sys.exit(main())
