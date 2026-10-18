from __future__ import annotations

import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest


DEEPSEEK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEEPSEEK_ROOT))

import install  # noqa: E402


class LauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.base = Path(self.tempdir.name)
        self.primary = self.base / "primary"
        self.link = self.base / "bin" / "dsh-primary"
        install.install(self.primary, DEEPSEEK_ROOT, self.link, check_only=False)

        self.driver_root = self.base / "driver"
        self.driver = self.driver_root / "node_modules" / ".bin" / "dsh"
        self.driver.parent.mkdir(parents=True)
        self.driver_marker = self.base / "driver-called"
        self.driver.write_text(
            "#!/bin/sh\n"
            "printf '%s\\n' \"${DSH_PRIMARY_MODEL:-missing}|${DSH_PERMISSION_MODE:-missing}|${DSH_MALICIOUS-unset}|${DEEPSEEK_BASE_URL-unset}|${DEEPSEEK_SEARCH_BASE_URL-unset}|${DSH_HOME:-missing}\" > \"$DRIVER_MARKER\"\n"
            "printf '%s\\n' \"$*\" > \"$DRIVER_ARGS_MARKER\"\n"
            "printf 'fake answer\\n'\n",
            encoding="utf-8",
        )
        self.driver.chmod(0o700)

        launcher = (self.primary / "bin" / "dsh-primary").read_text(
            encoding="utf-8"
        )
        expected = 'DRIVER_ROOT="${DSH_DRIVER_ROOT:-$HOME/.local/share/dsh-driver}"'
        self.assertIn(expected, launcher)
        (self.primary / "bin" / "dsh-primary").write_text(
            launcher.replace(expected, f'DRIVER_ROOT="{self.driver_root}"'),
            encoding="utf-8",
        )
        launcher = (self.primary / "bin" / "dsh-primary").read_text(
            encoding="utf-8"
        )
        expected_env = 'ENV_FILE="${DELEGATE_ENV_FILE:-$HOME/.config/delegate/.env}"'
        self.assertIn(expected_env, launcher)
        (self.primary / "bin" / "dsh-primary").write_text(
            launcher.replace(expected_env, f'ENV_FILE="{self.base / "delegate.env"}"'),
            encoding="utf-8",
        )
        (self.primary / "bin" / "dsh-primary").chmod(0o700)

        (self.primary / "startup.py").write_text(
            "#!/usr/bin/env python3\n"
            "import argparse\n"
            "p=argparse.ArgumentParser(); p.add_argument('--scope', required=True); a=p.parse_args()\n"
            "print(f'DEEPSEEK PRIMARY STARTUP\\nSESSION SCOPE: @s/{a.scope}\\nOPTMEM WAKE — UNTRUSTED MEMORY DATA')\n",
            encoding="utf-8",
        )
        (self.primary / "startup.py").chmod(0o700)
        (self.primary / "doctor.py").write_text(
            "#!/usr/bin/env python3\nraise SystemExit(0)\n", encoding="utf-8"
        )
        (self.primary / "doctor.py").chmod(0o700)
        self.env_file = self.base / "delegate.env"
        self.env_file.write_text("DEEPSEEK_API_KEY='test-key'\n", encoding="utf-8")

    def environment(self) -> dict[str, str]:
        environment = os.environ.copy()
        environment.pop("DEEPSEEK_API_KEY", None)
        environment.update(
            {
                "DSH_DRIVER_ROOT": str(self.base / "attacker-driver"),
                "DRIVER_MARKER": str(self.driver_marker),
                "DRIVER_ARGS_MARKER": str(self.base / "driver-args"),
                "DSH_MALICIOUS": "must-be-cleared",
                "DEEPSEEK_BASE_URL": "https://attacker.invalid",
                "DEEPSEEK_SEARCH_BASE_URL": "https://attacker.invalid/search",
            }
        )
        return environment

    def run_launcher(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [str(self.link), *arguments],
            check=False,
            capture_output=True,
            text=True,
            env=self.environment(),
        )

    def test_print_prompt_is_offline_and_contains_one_valid_scope(self) -> None:
        result = self.run_launcher(
            "--print-prompt", "literal task $(touch /tmp/never-execute)"
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        scopes = re.findall(r"SESSION SCOPE: @s/([a-z0-9]{8})", result.stdout)
        self.assertEqual(len(scopes), 1)
        self.assertIn("UNTRUSTED MEMORY DATA", result.stdout)
        self.assertNotIn("LINEAR QUEUE", result.stdout)
        self.assertIn("DIRECT USER TASK", result.stdout)
        self.assertIn("literal task $(touch /tmp/never-execute)", result.stdout)
        self.assertFalse(self.driver_marker.exists())

    def test_paid_dispatch_requires_explicit_confirmation(self) -> None:
        result = self.run_launcher("task")

        self.assertEqual(result.returncode, 77)
        self.assertIn("paid dispatch refused", result.stderr)
        self.assertFalse(self.driver_marker.exists())

    def test_confirmed_pro_dispatch_clears_inherited_dsh_state(self) -> None:
        result = self.run_launcher("--pro", "--confirm-spend", "task")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "fake answer\n")
        self.assertEqual(
            self.driver_marker.read_text(encoding="utf-8"),
            f"deepseek-v4-pro|danger-full-access|unset|unset|unset|{self.primary}\n",
        )
        self.assertIn("provider deepseek-official; model deepseek-v4-pro", result.stderr)
        driver_args = (self.base / "driver-args").read_text(encoding="utf-8")
        self.assertNotIn(str(self.primary / "primary-overlay.yml"), driver_args)
        self.assertRegex(
            driver_args,
            rf"--patch {re.escape(str(self.primary / 'dispatches'))}/[a-z0-9]{{8}}/primary-overlay.yml",
        )

    def test_env_file_is_parsed_as_data_not_sourced(self) -> None:
        side_effect = self.base / "env-was-executed"
        self.env_file.write_text(
            f"DEEPSEEK_API_KEY=test-key\ntouch {side_effect}\n", encoding="utf-8"
        )

        result = self.run_launcher("--confirm-spend", "task")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(side_effect.exists())

    def test_duplicate_api_key_is_refused(self) -> None:
        self.env_file.write_text(
            "DEEPSEEK_API_KEY=first\nDEEPSEEK_API_KEY=second\n",
            encoding="utf-8",
        )

        result = self.run_launcher("--confirm-spend", "task")

        self.assertEqual(result.returncode, 65)
        self.assertIn("could not load DEEPSEEK_API_KEY", result.stderr)
        self.assertFalse(self.driver_marker.exists())

    def test_paid_path_ignores_path_shadow_executables(self) -> None:
        shadow_bin = self.base / "shadow-bin"
        shadow_bin.mkdir()
        shadow_marker = self.base / "shadow-command-ran"
        for executable in (
            "awk",
            "dirname",
            "flock",
            "mkdir",
            "python3",
            "readlink",
            "timeout",
        ):
            shadow = shadow_bin / executable
            shadow.write_text(
                f"#!/usr/bin/sh\ntouch '{shadow_marker}'\nexit 90\n",
                encoding="utf-8",
            )
            shadow.chmod(0o700)
        environment = self.environment()
        environment["PATH"] = str(shadow_bin)

        result = subprocess.run(
            [str(self.link), "--confirm-spend", "task"],
            check=False,
            capture_output=True,
            text=True,
            env=environment,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(shadow_marker.exists())


if __name__ == "__main__":
    unittest.main()
