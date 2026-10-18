"""Offline boundary tests for the DeepSeek primary startup renderer."""

from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import unittest
from unittest import mock
from typing import Any


DEEPSEEK_DIR = Path(__file__).resolve().parents[1]
if str(DEEPSEEK_DIR) not in sys.path:
    sys.path.insert(0, str(DEEPSEEK_DIR))

import startup  # noqa: E402


def completed(
    args: list[str],
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args, returncode, stdout, stderr)


class StartupContextTests(unittest.TestCase):
    def test_success_uses_valid_scope_absolute_defaults_and_argv_commands(self) -> None:
        calls: list[tuple[list[str], dict[str, Any]]] = []

        def runner(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            calls.append((args, kwargs))
            return completed(args, stdout="#8 retained context\nYou are awake.\n")

        context = startup.render_startup_context("a1b2c3d4", runner=runner)

        self.assertIn("SESSION SCOPE: @s/a1b2c3d4", context)
        self.assertIn("DEEPSEEK OPTMEM AUTHORITY", context)
        self.assertIn("#8 retained context\nYou are awake.", context)
        self.assertIn("user-facing primary DeepSeek", context)
        self.assertTrue(startup.DEFAULT_MEMO.is_absolute())
        self.assertTrue(startup.DEFAULT_MEMORY_DIR.is_absolute())
        self.assertEqual(calls[0][0], [str(startup.DEFAULT_MEMO), "wake"])
        self.assertFalse(calls[0][1]["shell"])
        self.assertEqual(len(calls), 1)
        self.assertNotIn("LINEAR", context)

    def test_rejects_an_invalid_correlation_scope(self) -> None:
        with self.assertRaisesRegex(ValueError, "eight lowercase alphanumeric"):
            startup.render_startup_context("UPPER123", runner=mock.MagicMock())

    def test_accepts_explicit_test_command_and_store_overrides(self) -> None:
        calls: list[tuple[list[str], dict[str, Any]]] = []

        def runner(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
            calls.append((args, kwargs))
            return completed(args, stdout="You are awake.")

        startup.render_startup_context(
            "a1b2c3d4",
            memo_path=Path("/test/memo"),
            memory_dir=Path("/test/memory"),
            runner=runner,
        )

        self.assertEqual(calls[0][0], ["/test/memo", "wake"])
        self.assertEqual(calls[0][1]["env"]["MEMORY_DIR"], "/test/memory")

    def test_wake_nonzero_forbids_memory_writes(self) -> None:
        def runner(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
            return completed(args, returncode=23, stderr="store broken")

        context = startup.render_startup_context("a1b2c3d4", runner=runner)

        self.assertIn("OPTMEM WAKE UNAVAILABLE", context)
        self.assertIn("Do not call memo note or memo nap", context)

    def test_wake_timeout_forbids_memory_writes(self) -> None:
        def runner(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
            raise subprocess.TimeoutExpired(args, startup.WAKE_TIMEOUT_SECONDS)

        context = startup.render_startup_context("a1b2c3d4", runner=runner)

        self.assertIn("OPTMEM WAKE UNAVAILABLE", context)
        self.assertIn("measured 3.867-second budget", context)
        self.assertIn("Do not call memo note or memo nap", context)

    def test_malformed_successful_wake_forbids_memory_writes(self) -> None:
        def runner(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
            return completed(args, stdout="apparently healthy")

        context = startup.render_startup_context("a1b2c3d4", runner=runner)

        self.assertIn("OPTMEM WAKE UNAVAILABLE", context)
        self.assertIn("success marker", context)
        self.assertIn("Do not call memo note or memo nap", context)

    def test_wake_compression_request_becomes_a_trusted_settlement_gate(self) -> None:
        wake = "\n".join(
            [
                "#8 retained context",
                "You are awake.",
                "",
                "Compress memories #8-11 into one line of at most 280 characters.",
                "Keep what has lasting effect, drop what does not. Invent nothing.",
                "",
                'Run: ~/Work/optmem/memo nap 8-11 "<your line>"',
            ]
        )

        def runner(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
            return completed(args, stdout=wake)

        context = startup.render_startup_context("a1b2c3d4", runner=runner)

        self.assertIn("OPTMEM SETTLEMENT REQUIRED", context)
        self.assertIn("#8-11", context)
        self.assertIn("before appending a new note", context)

    def test_oversize_external_context_is_bounded_and_recoverable(self) -> None:
        large_wake = "wake-memory-" * 4_000 + "\nYou are awake.\n"

        def runner(args: list[str], **_: Any) -> subprocess.CompletedProcess[str]:
            return completed(args, stdout=large_wake)

        context = startup.render_startup_context("a1b2c3d4", runner=runner)

        self.assertLessEqual(
            len(context.encode("utf-8")), startup.MAX_STARTUP_CONTEXT_BYTES
        )
        self.assertIn("STARTUP DATA PREVIEW TRUNCATED", context)
        self.assertIn("memo wake", context)
        self.assertIn("SESSION SCOPE: @s/a1b2c3d4", context)

    def test_utf8_bound_never_splits_a_multibyte_character(self) -> None:
        text = "header\n" + ("🌹" * startup.MAX_STARTUP_CONTEXT_BYTES) + "\ntail"

        bounded = startup.bound_untrusted_section(
            text,
            startup.MAX_STARTUP_CONTEXT_BYTES,
            source="TEST DATA",
            reread_command="test source",
        )

        self.assertLessEqual(
            len(bounded.encode("utf-8")), startup.MAX_STARTUP_CONTEXT_BYTES
        )
        self.assertIn("header", bounded)
        self.assertIn("tail", bounded)

if __name__ == "__main__":
    unittest.main()
