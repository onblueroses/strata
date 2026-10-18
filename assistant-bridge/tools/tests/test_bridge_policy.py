from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

from .helpers import TOOLS, policy_text, write


def load_module():
    spec = importlib.util.spec_from_file_location("bridge_policy", TOOLS / "bridge_policy.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load bridge_policy")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class BridgePolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.bp = load_module()

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="policy-test-")
        self.root = Path(self.temp.name) / "vault"
        self.root.mkdir()
        self.policy_path = Path(self.temp.name) / "policy.toml"
        write(self.policy_path, policy_text())
        self.policy = self.bp.load_policy(self.policy_path)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def decision(self, relative: str, content: str = "ok"):
        write(self.root / relative, content)
        return self.policy.evaluate(self.root, relative)

    def test_loads_valid_policy_and_exposes_limits(self) -> None:
        self.assertEqual(self.policy.version, 1)
        self.assertEqual(self.policy.publish_root, "vault")
        self.assertEqual(self.policy.max_file_bytes, 1024)
        self.assertEqual(self.policy.max_total_bytes, 4096)

    def test_missing_policy_fails_closed(self) -> None:
        with self.assertRaises(self.bp.PolicyError):
            self.bp.load_policy(Path(self.temp.name) / "missing.toml")

    def test_unparsable_policy_fails_closed(self) -> None:
        write(self.policy_path, "this is not = toml [")
        with self.assertRaises(self.bp.PolicyError):
            self.bp.load_policy(self.policy_path)

    def test_fifo_policy_fails_closed_without_blocking(self) -> None:
        fifo = Path(self.temp.name) / "policy-fifo.toml"
        os.mkfifo(fifo)
        with self.assertRaises(self.bp.PolicyError):
            self.bp.load_policy(fifo)

    def test_schema_validation_rejects_missing_section(self) -> None:
        text = policy_text().replace("[limits]", "[not_limits]")
        write(self.policy_path, text)
        with self.assertRaises(self.bp.PolicyError):
            self.bp.load_policy(self.policy_path)

    def test_schema_validation_rejects_wrong_types_and_unknown_modes(self) -> None:
        cases = [
            policy_text().replace("version = 1", 'version = "1"'),
            policy_text().replace("max_file_bytes = 1024", "max_file_bytes = -1"),
            policy_text().replace('special_files = "reject"', 'special_files = "follow"'),
            policy_text(mode="automatic"),
        ]
        for index, text in enumerate(cases):
            with self.subTest(index=index):
                write(self.policy_path, text)
                with self.assertRaises(self.bp.PolicyError):
                    self.bp.load_policy(self.policy_path)

    def test_allowed_file_and_exact_file_root(self) -> None:
        self.assertTrue(self.decision("Shared/note.md").allowed)
        self.assertTrue(self.decision("Single.md").allowed)

    def test_similar_prefix_does_not_match_allowed_root(self) -> None:
        result = self.decision("Sharedness/note.md")
        self.assertFalse(result.allowed)
        self.assertEqual(result.category, "outside-allowed-root")

    def test_deny_path_wins_over_allowed_root(self) -> None:
        result = self.decision("Shared/private/note.md")
        self.assertFalse(result.allowed)
        self.assertEqual(result.category, "denied-path")

    def test_denied_basename_glob_wins(self) -> None:
        for relative in ("Shared/.env", "Shared/.env.prod", "Shared/private.key"):
            with self.subTest(relative=relative):
                result = self.decision(relative)
                self.assertFalse(result.allowed)
                self.assertEqual(result.category, "denied-name")

    def test_denied_extension(self) -> None:
        result = self.decision("Shared/program.exe")
        self.assertFalse(result.allowed)
        self.assertEqual(result.category, "denied-extension")

    def test_deny_rules_are_case_insensitive(self) -> None:
        for relative, category in (
            ("Shared/Private/note.md", "denied-path"),
            ("Shared/PRIVATE/deep/note.md", "denied-path"),
            (".Local/note.md", "denied-path"),
            ("Shared/.ENV", "denied-name"),
            ("Shared/.Env.prod", "denied-name"),
            ("Shared/Server.KEY", "denied-name"),
        ):
            with self.subTest(relative=relative):
                result = self.decision(relative)
                self.assertFalse(result.allowed)
                self.assertEqual(result.category, category)

    def test_extension_is_case_insensitive(self) -> None:
        result = self.decision("Shared/NOTE.MD")
        self.assertTrue(result.allowed)

    def test_dot_dot_and_absolute_paths_are_rejected(self) -> None:
        for relative in ("../outside.md", "Shared/../../outside.md", "/etc/passwd"):
            with self.subTest(relative=relative):
                result = self.policy.evaluate(self.root, relative, require_exists=False, size=1)
                self.assertFalse(result.allowed)
                self.assertIn(result.category, {"invalid-path", "outside-vault"})

    def test_symlink_file_and_symlink_parent_are_rejected(self) -> None:
        outside = Path(self.temp.name) / "outside.md"
        write(outside, "private")
        (self.root / "Shared").mkdir()
        (self.root / "Shared" / "link.md").symlink_to(outside)
        result = self.policy.evaluate(self.root, "Shared/link.md")
        self.assertFalse(result.allowed)
        self.assertEqual(result.category, "special-file")

        outside_dir = Path(self.temp.name) / "outside-dir"
        outside_dir.mkdir()
        write(outside_dir / "note.md", "private")
        (self.root / "Shared" / "linked-dir").symlink_to(outside_dir, target_is_directory=True)
        result = self.policy.evaluate(self.root, "Shared/linked-dir/note.md")
        self.assertFalse(result.allowed)
        self.assertEqual(result.category, "special-file")

    def test_directory_and_hardlink_are_rejected_as_special(self) -> None:
        directory = self.root / "Shared" / "folder.md"
        directory.mkdir(parents=True)
        result = self.policy.evaluate(self.root, "Shared/folder.md")
        self.assertFalse(result.allowed)
        self.assertEqual(result.category, "special-file")

        original = self.root / "Shared" / "original.md"
        write(original, "same inode")
        link = self.root / "Shared" / "hardlink.md"
        link.hardlink_to(original)
        result = self.policy.evaluate(self.root, "Shared/hardlink.md")
        self.assertFalse(result.allowed)
        self.assertEqual(result.category, "special-file")

    def test_oversized_file_is_rejected(self) -> None:
        result = self.decision("Shared/large.md", "x" * 1025)
        self.assertFalse(result.allowed)
        self.assertEqual(result.category, "oversized")

    def test_nonexistent_inbound_blob_can_be_checked_by_size(self) -> None:
        result = self.policy.evaluate(
            self.root, "Shared/new.md", size=8, require_exists=False
        )
        self.assertTrue(result.allowed)
        self.assertEqual(result.size, 8)

    def test_require_allowed_raises_path_policy_error(self) -> None:
        result = self.policy.evaluate(
            self.root, "Shared/no.exe", size=8, require_exists=False
        )
        with self.assertRaises(self.bp.PathPolicyError):
            result.require_allowed()


if __name__ == "__main__":
    unittest.main()
