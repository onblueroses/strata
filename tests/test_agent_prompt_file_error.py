import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = ROOT / "bin" / "lib" / "agent.py"


def load_agent():
    pydantic_ai = types.ModuleType("pydantic_ai")
    setattr(pydantic_ai, "Agent", object)
    setattr(pydantic_ai, "RunContext", object)
    messages = types.ModuleType("pydantic_ai.messages")

    class FakeMessagesTypeAdapter:
        @staticmethod
        def dump_json(value, **_kwargs):
            return json.dumps(value).encode()

        @staticmethod
        def validate_json(value):
            return json.loads(value)

    setattr(messages, "AgentStreamEvent", object)
    setattr(messages, "ModelMessage", object)
    setattr(messages, "ModelMessagesTypeAdapter", FakeMessagesTypeAdapter)
    setattr(messages, "ModelRequest", object)
    setattr(messages, "ModelResponse", object)
    setattr(messages, "ToolCallPart", object)
    setattr(messages, "ToolReturnPart", object)
    pydantic_core = types.ModuleType("pydantic_core")
    setattr(pydantic_core, "to_jsonable_python", lambda value: value)

    spec = importlib.util.spec_from_file_location("agent_under_test", AGENT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {AGENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    fake_modules = {
        spec.name: module,
        "pydantic_ai": pydantic_ai,
        "pydantic_ai.messages": messages,
        "pydantic_core": pydantic_core,
    }
    with mock.patch.dict(sys.modules, fake_modules):
        spec.loader.exec_module(module)
    return module


def call_main(module, argv, *, strata_home=None):
    stdout = io.StringIO()
    stderr = io.StringIO()
    old_argv = sys.argv[:]
    try:
        sys.argv = [str(AGENT_PATH), *argv]
        environment = (
            mock.patch.dict(os.environ, {"STRATA_HOME": str(strata_home)})
            if strata_home is not None
            else contextlib.nullcontext()
        )
        with (
            environment,
            contextlib.redirect_stdout(stdout),
            contextlib.redirect_stderr(stderr),
        ):
            status = module.main()
    finally:
        sys.argv = old_argv
    return status, stdout.getvalue(), stderr.getvalue()


class PromptFileErrorTests(unittest.TestCase):
    def test_missing_prompt_file_returns_usage_error(self):
        module = load_agent()

        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing-prompt.md"
            status, out, err = call_main(
                module, ["--model", "gpt-test", "--prompt-file", str(missing)]
            )

        self.assertEqual(status, 1)
        self.assertEqual(out, "")
        self.assertIn("strata-agent: cannot read prompt file", err)
        self.assertIn("missing-prompt.md", err)
        self.assertNotIn("Traceback", err)

    def test_valid_prompt_file_runs_agent(self):
        module = load_agent()

        class FakeResult:
            output = "ok"

            @staticmethod
            def all_messages():
                return [{"kind": "response", "content": "ok"}]

        class FakeAgent:
            def __init__(self):
                self.prompts = []

            async def run(self, prompt, **_kwargs):
                self.prompts.append(prompt)
                return FakeResult()

        with tempfile.TemporaryDirectory() as tmp:
            prompt_file = Path(tmp) / "prompt.md"
            prompt_file.write_text("read this\n")
            fake_agent = FakeAgent()
            with mock.patch.object(module, "build_agent", return_value=fake_agent):
                status, out, err = call_main(
                    module,
                    ["--model", "gpt-test", "--prompt-file", str(prompt_file)],
                    strata_home=tmp,
                )

        self.assertEqual(status, 0, err)
        self.assertEqual(out, "ok\n")
        self.assertIn("agent: progress ", err)
        self.assertIn("agent: session ", err)
        self.assertEqual(fake_agent.prompts, ["read this\n"])


if __name__ == "__main__":
    unittest.main()
