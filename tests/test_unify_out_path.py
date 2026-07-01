import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
UNIFY_PATH = REPO_ROOT / "telemetry" / "unify.py"


def load_unify():
    spec = importlib.util.spec_from_file_location("unify", UNIFY_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {UNIFY_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OutPathSafetyTests(unittest.TestCase):
    def test_tracked_path_blocked_when_git_ceiling_hides_worktree(self):
        unify = load_unify()
        tracked = REPO_ROOT / "telemetry" / "README.md"

        self.assertTrue(tracked.is_file())
        with mock.patch.dict(
            os.environ, {"GIT_CEILING_DIRECTORIES": str(REPO_ROOT)}, clear=False
        ):
            self.assertFalse(unify.out_path_is_safe(str(tracked)))

        with tempfile.TemporaryDirectory() as tmp:
            self.assertTrue(unify.out_path_is_safe(str(Path(tmp) / "out.jsonl")))

    def test_missing_output_parent_is_refused_before_opening(self):
        unify = load_unify()

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            missing = tmp_path / "missing" / "out.jsonl"

            self.assertFalse(unify.out_path_is_safe(str(missing)))
            self.assertTrue(unify.out_path_is_safe(str(tmp_path / "out.jsonl")))

            env = os.environ.copy()
            env.update(
                {
                    "STRATA_HOME": str(tmp_path / "strata-home"),
                    "KB_DIR": str(tmp_path / "kb"),
                    "STATE_DIR": str(tmp_path / "state"),
                    "STRATA_TELEMETRY_DIR": str(tmp_path / "telemetry"),
                }
            )
            proc = subprocess.run(
                [sys.executable, str(UNIFY_PATH), "--out", str(missing)],
                cwd=REPO_ROOT,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=10,
            )

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIn("refusing --out", proc.stderr)
            self.assertNotIn("Traceback", proc.stderr)
            self.assertFalse(missing.exists())


if __name__ == "__main__":
    unittest.main()
