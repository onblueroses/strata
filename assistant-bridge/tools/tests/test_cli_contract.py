from __future__ import annotations

import importlib.machinery
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

from .helpers import APPLY, IMPORT, PUBLISH, RESTORE, TOOLS


def load_tool(name: str, path: Path):
    tools_text = str(TOOLS)
    if tools_text not in sys.path:
        sys.path.insert(0, tools_text)
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    if spec is None:
        raise RuntimeError(f"cannot load {path.name}")
    module = importlib.util.module_from_spec(spec)
    # Dataclasses resolve their module through sys.modules.
    sys.modules[name] = module
    loader.exec_module(module)
    return module


class CliContractTests(unittest.TestCase):
    def test_commands_exist_and_are_executable(self) -> None:
        for command in (PUBLISH, IMPORT, APPLY, RESTORE):
            with self.subTest(command=command.name):
                self.assertTrue(command.is_file(), f"missing {command}")
                self.assertTrue(os.access(command, os.X_OK), f"not executable: {command}")

    def test_publish_and_apply_take_status_and_pause_directories(self) -> None:
        # bridge-health reads <status dir>/<job>-status.json; the pause directory holds
        # the owner's markers. Both follow the flag-with-BRIDGE_*-fallback convention.
        cleared = {
            key: value
            for key, value in os.environ.items()
            if key not in {"BRIDGE_JOB_STATUS_DIR", "BRIDGE_PAUSE_DIR"}
        }
        for name, path in (("publish", PUBLISH), ("apply", APPLY)):
            with self.subTest(job=name):
                tool = load_tool(f"bridge_{name}_contract", path)
                base = ["--remote-url", "git@github-assistant-bridge:owner/repo.git"]
                with mock.patch.dict(os.environ, cleared, clear=True):
                    defaults = tool.parse_args(base)
                self.assertEqual(defaults.status_dir, "/var/lib/assistant-bridge")
                self.assertIsNone(defaults.pause_dir)
                self.assertEqual(tool.STATUS_FILE, f"{name}-status.json")
                with mock.patch.dict(
                    os.environ,
                    {"BRIDGE_JOB_STATUS_DIR": "/env/status", "BRIDGE_PAUSE_DIR": "/env/paused"},
                ):
                    from_env = tool.parse_args(base)
                    flagged = tool.parse_args(
                        [*base, "--status-dir", "/flag/status", "--pause-dir", "/flag/paused"]
                    )
                self.assertEqual((from_env.status_dir, from_env.pause_dir), ("/env/status", "/env/paused"))
                self.assertEqual((flagged.status_dir, flagged.pause_dir), ("/flag/status", "/flag/paused"))

    def test_secret_defaults_name_the_files_the_installer_writes(self) -> None:
        # install.sh writes the responder's token as /etc/assistant-bridge/github.token and
        # bridge-vault's copy as /etc/assistant-bridge/apply.token.
        respond = load_tool("bridge_respond_secret_contract", TOOLS / "bridge-respond")
        apply = load_tool("bridge_apply_secret_contract", APPLY)
        with mock.patch.dict(os.environ, {}, clear=True):
            responder = respond.parse_args([])
            applier = apply.parse_args(["--remote-url", "git@github-assistant-bridge:o/r.git"])
        self.assertEqual(responder.token_file, "/etc/assistant-bridge/github.token")
        self.assertEqual(applier.token_file, "/etc/assistant-bridge/apply.token")


if __name__ == "__main__":
    unittest.main()
