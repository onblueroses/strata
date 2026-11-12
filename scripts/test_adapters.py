#!/usr/bin/env python3
"""Offline positive/negative controls; never starts a model provider."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent.parent


class AdapterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Keep test artifacts in ignored local scratch, including failed controls.
        scratch = ROOT / ".local"
        scratch.mkdir(exist_ok=True)
        cls.work = Path(tempfile.mkdtemp(prefix="adapter-tests-", dir=scratch))

    def test_codex_preflight_and_fixed_provider(self):
        mock = self.work / "codex"
        log = self.work / "codex-argv.json"
        mock.write_text("#!" + sys.executable + "\n" +
            "import json,os,sys\nfrom pathlib import Path\n"
            "if sys.argv[1:]==['login','status']:\n"
            " print(os.environ.get('TEST_AUTH','Logged in using ChatGPT'));sys.exit(0)\n"
            "Path(os.environ['TEST_LOG']).write_text(json.dumps(sys.argv[1:]))\n"
            "print(json.dumps({'type':'thread.started','thread_id':'example-session'}))\n")
        mock.chmod(0o700)
        env = {**os.environ, "PATH": str(self.work) + os.pathsep + os.environ["PATH"], "TEST_LOG": str(log)}
        cmd = [sys.executable, str(ROOT / "delegation/codex-run.py"), "fast", "--cwd", str(self.work), "example brief"]
        refused = subprocess.run(cmd, env={**env, "TEST_AUTH": "API key login"}, capture_output=True, text=True)
        self.assertEqual(refused.returncode, 2)
        self.assertIn("ChatGPT subscription login", refused.stderr)
        self.assertFalse(log.exists())
        accepted = subprocess.run(cmd, env=env, capture_output=True, text=True)
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        argv = json.loads(log.read_text())
        self.assertIn('model_provider="openai"', argv)
        self.assertIn("read-only", argv)
        self.assertNotIn("danger-full-access", argv)
        self.assertIn("example-session", accepted.stderr)

    def test_deepseek_confirmation_and_offline_flag_order(self):
        mock = self.work / "mock-dsh"
        log = self.work / "dsh-argv.json"
        mock.write_text("#!" + sys.executable + "\nimport json,os,sys\nfrom pathlib import Path\n"
                        "Path(os.environ['TEST_LOG']).write_text(json.dumps(sys.argv[1:]))\n")
        mock.chmod(0o700)
        env = {**os.environ, "DSH_PRIMARY_BIN": str(mock), "TEST_LOG": str(log)}
        cmd = ["bash", str(ROOT / "deepseek/launch-adapter.sh")]
        denied = subprocess.run(cmd + ["example brief"], env=env, capture_output=True)
        self.assertNotEqual(denied.returncode, 0)
        self.assertFalse(log.exists())
        dry = subprocess.run(cmd + ["example brief", "--print-prompt"], env=env, capture_output=True)
        self.assertEqual(dry.returncode, 0)
        self.assertEqual(json.loads(log.read_text())[0], "--print-prompt")
        paid = subprocess.run(cmd + ["--confirm-spend", "example brief"], env=env, capture_output=True)
        self.assertEqual(paid.returncode, 0)
        self.assertIn("--confirm-spend", json.loads(log.read_text()))


if __name__ == "__main__":
    unittest.main()
