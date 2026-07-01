import contextlib
import importlib.util
import io
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

    spec = importlib.util.spec_from_file_location("agent_under_test", AGENT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {AGENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, {"pydantic_ai": pydantic_ai}):
        spec.loader.exec_module(module)
    return module


def call_main(module, argv):
    stdout = io.StringIO()
    stderr = io.StringIO()
    old_argv = sys.argv[:]
    try:
        sys.argv = [str(AGENT_PATH), *argv]
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
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

        class FakeAgent:
            def __init__(self):
                self.prompts = []

            def run_sync(self, prompt):
                self.prompts.append(prompt)
                return FakeResult()

        with tempfile.TemporaryDirectory() as tmp:
            prompt_file = Path(tmp) / "prompt.md"
            prompt_file.write_text("read this\n")
            fake_agent = FakeAgent()
            with mock.patch.object(module, "build_agent", return_value=fake_agent):
                status, out, err = call_main(
                    module, ["--model", "gpt-test", "--prompt-file", str(prompt_file)]
                )

        self.assertEqual(status, 0, err)
        self.assertEqual(out, "ok\n")
        self.assertEqual(err, "")
        self.assertEqual(fake_agent.prompts, ["read this\n"])


if __name__ == "__main__":
    unittest.main()
