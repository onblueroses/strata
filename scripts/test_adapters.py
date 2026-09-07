#!/usr/bin/env python3
"""Offline positive/negative controls; never starts a model provider."""
import json
import os
from pathlib import Path
import subprocess
import signal
import time
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

    def hook(self, event, config, payload=None):
        config_path = self.work / "adapters.json"
        config_path.write_text(json.dumps(config))
        return subprocess.run(
            [sys.executable, str(ROOT / "integrations/hook_adapter.py"), event],
            input=json.dumps(payload if payload is not None else {"cwd": str(self.work),
                  "tool_input": {"command": "echo example"}}),
            text=True, capture_output=True,
            env={**os.environ, "STRATA_ADAPTERS_FILE": str(config_path)}, timeout=5)

    def test_both_privacy_gates_must_pass(self):
        marker = self.work / "gates"
        def gate(label, code):
            program = "from pathlib import Path; import sys; " + \
                f"p=Path({str(marker)!r}); p.open('a').write({label!r}); sys.exit({code})"
            return [sys.executable, "-c", program]
        config = {"privacy-public": gate("a", 0), "privacy-push": gate("b", 0)}
        self.assertEqual(self.hook("privacy", config).returncode, 0)
        self.assertEqual(marker.read_text(), "ab")
        config["privacy-push"] = gate("c", 1)
        self.assertEqual(self.hook("privacy", config).returncode, 2)
        config.pop("privacy-push")
        self.assertEqual(self.hook("privacy", config).returncode, 2)
        self.assertEqual(self.hook("privacy", {}, []).returncode, 2)

    def test_missing_memory_does_not_invent_context(self):
        result = self.hook("memory-wake", {})
        self.assertEqual(result.returncode, 0)
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("unavailable", context)
        result = self.hook("memory-wake", {"memory-wake": [sys.executable, "-c", "print('record one')"]})
        self.assertEqual(result.returncode, 0)
        self.assertIn("record one", result.stdout)

    def test_hook_interruption_stops_descendants(self):
        started = self.work / "descendant-started"
        delayed = self.work / "descendant-finished"
        # The child keeps inherited pipes open; terminating just its parent is insufficient.
        helper = self.work / "spawn-child.py"
        helper.write_text(
            "import subprocess,sys,time\nfrom pathlib import Path\n"
            + "subprocess.Popen([sys.executable,'-c',"
            + repr("import time; from pathlib import Path; time.sleep(1); "
                   + f"Path({str(delayed)!r}).write_text('finished')") + "])\n"
            + f"Path({str(started)!r}).write_text('started')\n"
            + "time.sleep(3)\n")
        config = self.work / "lifecycle-adapters.json"
        config.write_text(json.dumps({"lifecycle-test": [sys.executable, str(helper)]}))
        child = subprocess.Popen(
            [sys.executable, str(ROOT / "integrations/hook_adapter.py"), "lifecycle-test"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            env={**os.environ, "STRATA_ADAPTERS_FILE": str(config)})
        child.stdin.write("{}")
        child.stdin.close()
        try:
            deadline = time.monotonic() + 3
            while not started.exists() and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertTrue(started.exists(), "adapter must start before interruption")
            child.send_signal(signal.SIGTERM)
            self.assertEqual(child.wait(timeout=3), 2)
            time.sleep(1.2)
            self.assertFalse(delayed.exists(), "grandchild survived interrupted hook")
        finally:
            if child.poll() is None:
                child.kill()
                child.wait()
            child.stdout.close()
            child.stderr.close()
        # Same descendant actually produces the marker without interruption.
        control = subprocess.run([sys.executable, str(helper)], timeout=5)
        self.assertEqual(control.returncode, 0)
        self.assertEqual(delayed.read_text(), "finished")

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
