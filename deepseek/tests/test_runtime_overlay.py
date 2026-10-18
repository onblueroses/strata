from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest


DEEPSEEK_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEEPSEEK_ROOT))

import runtime_overlay  # noqa: E402


class RuntimeOverlayTests(unittest.TestCase):
    def test_copies_the_static_overlay_exclusively_and_byte_exactly(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.yml"
            destination = root / "run" / "primary-overlay.yml"
            destination.parent.mkdir()
            source.write_bytes(b"- id: exact-static-overlay\n")

            runtime_overlay.copy_static_overlay(source, destination)

            self.assertEqual(destination.read_bytes(), source.read_bytes())
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                runtime_overlay.copy_static_overlay(source, destination)

    def test_static_copy_refuses_a_symlink_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            real = root / "real.yml"
            source = root / "source.yml"
            destination = root / "destination.yml"
            real.write_text("safe\n", encoding="utf-8")
            source.symlink_to(real)

            with self.assertRaisesRegex(ValueError, "regular file"):
                runtime_overlay.copy_static_overlay(source, destination)

    def test_writes_exact_official_provider_model_and_session_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "overlay.json"
            sessions = root / "sessions"

            runtime_overlay.write_overlay(
                destination, sessions, "deepseek-v4-pro"
            )

            data = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(
                data,
                [
                    {
                        "id": "agent-default-model",
                        "config": {
                            "provider": "deepseek-official",
                            "model": "deepseek-v4-pro",
                        },
                    },
                    {
                        "id": "session-persistence-jsonl",
                        "config": {"root": str(sessions)},
                    },
                ],
            )
            self.assertEqual(destination.stat().st_mode & 0o777, 0o600)

    def test_refuses_unknown_model_relative_paths_and_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "overlay.json"
            sessions = root / "sessions"
            with self.assertRaisesRegex(ValueError, "unsupported"):
                runtime_overlay.write_overlay(destination, sessions, "other")
            with self.assertRaisesRegex(ValueError, "absolute"):
                runtime_overlay.write_overlay(
                    Path("overlay.json"), sessions, "deepseek-v4-flash"
                )
            destination.write_text("mine\n", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                runtime_overlay.write_overlay(
                    destination, sessions, "deepseek-v4-flash"
                )
            self.assertEqual(destination.read_text(encoding="utf-8"), "mine\n")

    def test_reader_refuses_provider_root_and_nonfinite_drift(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            destination = root / "runtime-overlay.json"
            sessions = root / "sessions"
            runtime_overlay.write_overlay(
                destination, sessions, "deepseek-v4-flash"
            )
            self.assertEqual(
                runtime_overlay.read_overlay(destination, "deepseek-v4-flash"),
                sessions,
            )

            baseline = destination.read_text(encoding="utf-8")
            mutations = (
                baseline.replace("deepseek-official", "other-provider"),
                baseline.replace(str(sessions), str(root / "other-sessions")),
                baseline[:-2] + ',\n  {"extra": 1e400}\n]\n',
            )
            for mutated in mutations:
                with self.subTest(mutated=mutated):
                    destination.write_text(mutated, encoding="utf-8")
                    with self.assertRaisesRegex(ValueError, "runtime overlay|non-finite"):
                        runtime_overlay.read_overlay(
                            destination, "deepseek-v4-flash"
                        )
            destination.write_text(
                baseline.replace(
                    '"provider": "deepseek-official"',
                    '"provider": "deepseek-official", "provider": "other"',
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
                runtime_overlay.read_overlay(destination, "deepseek-v4-flash")


if __name__ == "__main__":
    unittest.main()
