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

    python agent.py --model <model-id> < prompt.md

Exit codes:
    0  success — final answer on stdout
    1  usage error
    2  API / model error
    3  rate limit / quota exhausted (caller should fall back)
    4  auth error (missing or rejected API key)
    5  empty content from model (after one re-prompt attempt)
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from pydantic_ai import Agent


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
    print(
        f"strata-agent: {env_var} missing — set it in env or in $STRATA_HOME/.local/.env",
        file=sys.stderr,
    )
    sys.exit(4)


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
        from pydantic_ai.providers.openai import OpenAIProvider

        api_key = resolve_api_key("DEEPSEEK_API_KEY")
        provider = OpenAIProvider(
            api_key=api_key, base_url="https://api.deepseek.com/v1"
        )
        return OpenAIChatModel(name, provider=provider)

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
        print(
            f"strata-agent: unknown provider prefix '{provider_prefix}'",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        f"strata-agent: cannot infer provider from model id '{name}'. "
        f"Use a prefix (claude-, gpt-, deepseek-, gemini-) or qualify as provider/model.",
        file=sys.stderr,
    )
    sys.exit(1)


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
    def run_bash(command: str, timeout_seconds: int = 60) -> str:
        """Run a bash command. Returns combined stdout+stderr (truncated to 8KB) and exit code."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
            output = (result.stdout + result.stderr)[:8192]
            return f"exit={result.returncode}\n{output}"
        except subprocess.TimeoutExpired:
            return f"ERROR: command timed out after {timeout_seconds}s"
        except Exception as e:
            return f"ERROR: {type(e).__name__}: {e}"

    @agent.tool_plain
    def grep(pattern: str, path: str = ".", case_insensitive: bool = False) -> str:
        """Search for a regex pattern recursively. Returns matching lines (max 4KB)."""
        cmd = ["rg", "--no-heading", "--line-number", "--color=never"]
        if case_insensitive:
            cmd.append("-i")
        cmd += [pattern, path]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return (result.stdout or result.stderr)[:4096] or "(no matches)"
        except FileNotFoundError:
            return "ERROR: ripgrep (rg) not installed"
        except Exception as e:
            return f"ERROR: {type(e).__name__}: {e}"

    return agent


def main() -> int:
    parser = argparse.ArgumentParser(description="Strata lane agent — multi-provider")
    parser.add_argument(
        "--model", required=True, help="Model id; provider inferred by prefix"
    )
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

    try:
        agent = build_agent(args.model, args.system)
        result = agent.run_sync(prompt)
        text = result.output if hasattr(result, "output") else str(result)
        if not text or not text.strip():
            try:
                followup = agent.run_sync(
                    "You returned no text. Produce the mandatory final answer now: "
                    "what did you do, what did you find, and what is the verdict? "
                    "Reply in plain text under 200 words.",
                    message_history=result.all_messages(),
                )
                text = followup.output if hasattr(followup, "output") else str(followup)
            except Exception as followup_err:
                print(
                    f"strata-agent: re-prompt for empty output failed: {followup_err}",
                    file=sys.stderr,
                )
            if not text or not text.strip():
                return 5
        sys.stdout.write(text)
        sys.stdout.write("\n")
        return 0
    except Exception as e:
        msg = str(e)
        if "429" in msg or "rate limit" in msg.lower() or "quota" in msg.lower():
            print(f"strata-agent: rate limited: {msg}", file=sys.stderr)
            return 3
        if "401" in msg or "403" in msg or "auth" in msg.lower():
            print(f"strata-agent: auth error: {msg}", file=sys.stderr)
            return 4
        print(f"strata-agent: {type(e).__name__}: {msg}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
