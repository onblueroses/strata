import asyncio
import importlib.util
import json
import os
import sys
import tempfile
import time
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

    class FakeToolCallPart:
        def __init__(self, tool_name, tool_call_id):
            self.tool_name = tool_name
            self.tool_call_id = tool_call_id

    class FakeToolReturnPart:
        def __init__(
            self,
            tool_name,
            content,
            tool_call_id,
            *,
            outcome="success",
        ):
            self.tool_name = tool_name
            self.content = content
            self.tool_call_id = tool_call_id
            self.outcome = outcome

    class FakeModelRequest:
        def __init__(
            self,
            parts,
            *,
            run_id=None,
            conversation_id=None,
        ):
            self.parts = parts
            self.run_id = run_id
            self.conversation_id = conversation_id

    class FakeModelResponse:
        def __init__(
            self,
            parts,
            *,
            run_id=None,
            conversation_id=None,
        ):
            self.parts = parts
            self.run_id = run_id
            self.conversation_id = conversation_id

    setattr(messages, "AgentStreamEvent", object)
    setattr(messages, "ModelMessage", object)
    setattr(messages, "ModelMessagesTypeAdapter", FakeMessagesTypeAdapter)
    setattr(messages, "ModelRequest", FakeModelRequest)
    setattr(messages, "ModelResponse", FakeModelResponse)
    setattr(messages, "ToolCallPart", FakeToolCallPart)
    setattr(messages, "ToolReturnPart", FakeToolReturnPart)
    pydantic_core = types.ModuleType("pydantic_core")
    setattr(pydantic_core, "to_jsonable_python", lambda value: value)

    spec = importlib.util.spec_from_file_location(
        "agent_sessions_under_test", AGENT_PATH
    )
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


class SessionPersistenceTests(unittest.TestCase):
    def test_history_round_trip_preserves_nested_message_structure(self):
        module = load_agent()
        messages = [
            {
                "kind": "request",
                "parts": [
                    {"part_kind": "user-prompt", "content": "remember cobalt"},
                    {
                        "part_kind": "tool-return",
                        "tool_name": "read_file",
                        "content": "nested result",
                    },
                ],
            },
            {
                "kind": "response",
                "parts": [
                    {
                        "part_kind": "tool-call",
                        "tool_name": "read_file",
                        "args": {"path": "CONFIG.md"},
                    },
                    {"part_kind": "text", "content": "I remember cobalt."},
                ],
            },
        ]

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "strong-12345678-1234-4123-8123-123456789abc.json"
            module.persist_history(path, messages)
            loaded = module.load_history(path)

        self.assertEqual(loaded, messages)
        self.assertEqual(
            loaded[1]["parts"][0]["args"]["path"],
            "CONFIG.md",
        )

    def test_last_resolves_newest_session_for_requested_lane(self):
        module = load_agent()
        older_id = "12345678-1234-4123-8123-123456789abc"
        newer_id = "87654321-4321-4876-8876-cba987654321"
        other_lane_id = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"

        with tempfile.TemporaryDirectory() as tmp:
            session_dir = Path(tmp)
            older = module.session_path(session_dir, "strong", older_id)
            newer = module.session_path(session_dir, "strong", newer_id)
            other = module.session_path(session_dir, "fast", other_lane_id)
            for path in (older, newer, other):
                module.persist_history(path, [])
            os.utime(older, ns=(1_000_000_000, 1_000_000_000))
            os.utime(newer, ns=(2_000_000_000, 2_000_000_000))
            os.utime(other, ns=(3_000_000_000, 3_000_000_000))

            resolved_last = module.resolve_session_file(session_dir, "strong", "last")
            resolved_id = module.resolve_session_file(session_dir, "strong", older_id)

        self.assertEqual(resolved_last.name, newer.name)
        self.assertEqual(resolved_id.name, older.name)

    def test_second_run_on_one_session_is_refused(self):
        module = load_agent()
        session_id = "12345678-1234-4123-8123-123456789abc"

        with tempfile.TemporaryDirectory() as tmp:
            path = module.session_path(Path(tmp), "strong", session_id)
            module.persist_history(path, [])
            held = module.lock_session(path)
            try:
                with self.assertRaises(module.LaneAgentError) as caught:
                    module.lock_session(path)
            finally:
                os.close(held)

            self.assertEqual(caught.exception.exit_code, 1)
            # The lock releases with the run, so the next run resumes normally.
            os.close(module.lock_session(path))

    def test_lock_file_is_not_resolved_as_a_session(self):
        module = load_agent()
        session_id = "12345678-1234-4123-8123-123456789abc"

        with tempfile.TemporaryDirectory() as tmp:
            session_dir = Path(tmp)
            path = module.session_path(session_dir, "strong", session_id)
            module.persist_history(path, [])
            os.close(module.lock_session(path))

            resolved = module.resolve_session_file(session_dir, "strong", "last")

        self.assertEqual(resolved.name, path.name)

    def test_explicit_resume_rejects_non_uuid_path_input(self):
        module = load_agent()
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(module.LaneAgentError):
                module.resolve_session_file(Path(tmp), "strong", "../../CONFIG.md")

    def test_interrupted_tool_call_gets_a_native_interrupted_return(self):
        module = load_agent()
        response = module.ModelResponse(
            [module.ToolCallPart("run_bash", "call-1")],
            run_id="run-1",
            conversation_id="conversation-1",
        )

        repaired = module.close_interrupted_tool_calls([response])

        self.assertEqual(len(repaired), 2)
        request = repaired[-1]
        self.assertIsInstance(request, module.ModelRequest)
        self.assertEqual(request.run_id, "run-1")
        self.assertEqual(request.conversation_id, "conversation-1")
        tool_return = request.parts[0]
        self.assertIsInstance(tool_return, module.ToolReturnPart)
        self.assertEqual(tool_return.tool_call_id, "call-1")
        self.assertEqual(tool_return.outcome, "interrupted")


class SubprocessCancellationTests(unittest.TestCase):
    def test_cancel_terminates_the_subprocess_group_promptly(self):
        module = load_agent()

        async def exercise():
            process = await asyncio.create_subprocess_shell(
                "sleep 30",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
            )
            task = asyncio.create_task(module.communicate_with_timeout(process, 60))
            await asyncio.sleep(0.05)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            return process

        started = time.monotonic()
        process = asyncio.run(exercise())

        self.assertIsNotNone(process.returncode)
        self.assertLess(time.monotonic() - started, 3)


if __name__ == "__main__":
    unittest.main()
