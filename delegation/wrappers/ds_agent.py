#!/usr/bin/env python3
"""DeepSeek agent harness via Pydantic AI.

Gives DeepSeek v4 (flash or pro) full agentic capability: file ops, bash, grep,
web-search-via-search-cli. Read prompt from stdin or --prompt-file. Final answer
to stdout, diagnostics to stderr.

Invocation (typically through ds-flash or ds-pro shell wrappers):
    DEEPSEEK_API_KEY=... python ds_agent.py --model deepseek-v4-flash < prompt.md

Exit codes:
    0  success — final answer on stdout
    1  usage error
    2  API / model error
    3  rate limit (429)
    4  auth error
"""

# pyright: reportMissingImports=false
# pydantic_ai is installed in the runtime venv (~/.local/share/delegate-venv), not the env the
# pre-commit pyright scans; the import resolves where this script actually executes.

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

# House standing instructions, shared by every harness. Generated and owned by
# ~/.claude/agents-core/; this file only reads it.
CORE_COMPACT_PATH = Path.home() / ".claude" / "agents-core" / "CORE-compact.md"

DEFAULT_SYSTEM = (
    "You are an autonomous coding agent with bash, file, and grep tools. "
    "When the user asks a question that requires reading files, listing directories, "
    "or running commands, USE YOUR TOOLS — do not refuse or ask permission. "
    "Read whatever files you need, run whatever commands clarify the situation, "
    "then ALWAYS produce a final text answer. The final answer is mandatory: "
    "it must summarize what you did, what you found, and the verdict — even if "
    "the work was completed entirely through tool calls. Empty replies are a "
    "bug. Be terse (no preamble, no closing fluff), but do not be silent."
)


def load_core_prefix(core_path: Path | None = None) -> str:
    """Return the house core text, or "" when it is missing, empty, or unreadable.

    Degradation is loud on purpose: a silently absent core would let every ds
    dispatch drift from the house rules with no signal anywhere.

    `core_path` resolves late (module attribute, not a bound default) so tests can
    point the loader at a fixture without touching the real core file.
    """
    core_path = core_path or CORE_COMPACT_PATH
    try:
        text = core_path.read_text()
    except Exception as e:  # never fail a dispatch over the core file
        print(
            f"ds_agent: WARNING house core unreadable at {core_path} "
            f"({type(e).__name__}: {e}); running with the built-in system prompt only",
            file=sys.stderr,
        )
        return ""
    if not text.strip():
        print(
            f"ds_agent: WARNING house core empty at {core_path}; "
            "running with the built-in system prompt only",
            file=sys.stderr,
        )
        return ""
    return text.strip()


def resolve_system_prompt(
    system_prompt: str | None, core_path: Path | None = None
) -> str:
    """Compose the system prompt: house core first, tool-use instructions after.

    `--system` is the documented full-replacement opt-out — the core is neither
    loaded nor prepended, and no warning reaches stderr, because callers like
    cs-bench's nl_baseline.rs are controlled-prompt benchmarks that own their
    entire system message and capture stderr.
    """
    if system_prompt:
        return system_prompt
    core = load_core_prefix(core_path)
    return f"{core}\n\n{DEFAULT_SYSTEM}" if core else DEFAULT_SYSTEM


def build_agent(
    model_name: str, system_prompt: str | None, core_path: Path | None = None
) -> Agent:
    api_key = os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        env_file = Path.home() / ".config" / "delegate" / ".env"
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("DEEPSEEK_API_KEY="):
                    api_key = line.split("=", 1)[1].strip()
                    break
    if not api_key:
        print("ds_agent: DEEPSEEK_API_KEY missing", file=sys.stderr)
        sys.exit(4)

    provider = OpenAIProvider(api_key=api_key, base_url="https://api.deepseek.com/v1")
    model = OpenAIChatModel(model_name, provider=provider)

    agent = Agent(
        model,
        system_prompt=resolve_system_prompt(system_prompt, core_path),
        retries=2,
    )

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
            out = (result.stdout or result.stderr)[:4096]
            return out or "(no matches)"
        except FileNotFoundError:
            return "ERROR: ripgrep (rg) not installed"
        except Exception as e:
            return f"ERROR: {type(e).__name__}: {e}"

    return agent


def main() -> int:
    parser = argparse.ArgumentParser(description="DeepSeek agent harness")
    parser.add_argument("--model", default="deepseek-v4-flash")
    parser.add_argument("--prompt-file", help="Read prompt from file")
    parser.add_argument("--system", help="Override system prompt")
    parser.add_argument("--prompt", help="Inline prompt (else stdin)")
    args = parser.parse_args()

    if args.prompt:
        prompt = args.prompt
    elif args.prompt_file:
        prompt = Path(args.prompt_file).read_text()
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read()
    else:
        print(
            "ds_agent: no prompt (use --prompt, --prompt-file, or stdin)",
            file=sys.stderr,
        )
        return 1

    if not prompt.strip():
        print("ds_agent: empty prompt", file=sys.stderr)
        return 1

    try:
        agent = build_agent(args.model, args.system)
        result = agent.run_sync(prompt)
        text = result.output if hasattr(result, "output") else str(result)
        if not text or not text.strip():
            # Fallback: agent silently completed via tools without final text.
            # Re-prompt once for a forced summary, then fall back to message history.
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
                    f"ds_agent: re-prompt for empty output failed: {followup_err}",
                    file=sys.stderr,
                )
            if not text or not text.strip():
                # Last resort: dump tool-call summary so caller sees SOMETHING.
                lines = [
                    "[ds_agent: no final text from model; tool-call summary follows]"
                ]
                for msg in result.all_messages():
                    for part in getattr(msg, "parts", []):
                        kind = type(part).__name__
                        if kind == "ToolCallPart":
                            tool = getattr(part, "tool_name", "?")
                            args_obj = getattr(part, "args", "")
                            preview = str(args_obj)[:200].replace("\n", " ")
                            lines.append(f"  call {tool}({preview})")
                        elif kind == "ToolReturnPart":
                            tool = getattr(part, "tool_name", "?")
                            ret = str(getattr(part, "content", ""))[:200].replace(
                                "\n", " "
                            )
                            lines.append(f"  -> {tool}: {ret}")
                        elif kind == "TextPart":
                            content = getattr(part, "content", "")
                            if content and content.strip():
                                lines.append(f"  text: {content[:300]}")
                text = "\n".join(lines)
        usage_file = os.environ.get("DS_USAGE_FILE")
        if usage_file:
            try:
                u = result.usage()
                import json as _json

                with open(usage_file, "w") as _uf:
                    _json.dump(
                        {
                            "input": getattr(u, "input_tokens", 0) or 0,
                            "output": getattr(u, "output_tokens", 0) or 0,
                            "cache_read": getattr(u, "cache_read_tokens", 0) or 0,
                            "cache_write": getattr(u, "cache_write_tokens", 0) or 0,
                            "total": getattr(u, "total_tokens", 0) or 0,
                            "requests": getattr(u, "requests", 0) or 0,
                        },
                        _uf,
                    )
            except Exception:
                pass  # basis: usage capture is best-effort telemetry; never fail the dispatch
        sys.stdout.write(text)
        sys.stdout.write("\n")
        return 0
    except Exception as e:
        msg = str(e)
        # Quota / rate limit detection
        if "429" in msg or "rate limit" in msg.lower() or "quota" in msg.lower():
            print(f"ds_agent: rate limited: {msg}", file=sys.stderr)
            return 3
        if "401" in msg or "403" in msg or "auth" in msg.lower():
            print(f"ds_agent: auth error: {msg}", file=sys.stderr)
            return 4
        print(f"ds_agent: {type(e).__name__}: {msg}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
