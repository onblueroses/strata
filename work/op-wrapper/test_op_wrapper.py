"""Offline checks for the wrapper's allowlisted read boundary."""
import importlib.machinery
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

HERE = Path(__file__).resolve().parent
loader = importlib.machinery.SourceFileLoader("op_wrapper", str(HERE / "op-wrapper"))
op = importlib.util.module_from_spec(importlib.util.spec_from_loader("op_wrapper", loader))
loader.exec_module(op)


class ReadBoundary(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "code"
        self.root.mkdir()
        (self.root / "public.txt").write_text("ok")
        self.allow = {"read_roots": {"code": str(self.root)}}
        audit = patch.object(op, "audit")
        audit.start()
        self.addCleanup(audit.stop)

    def test_allowlisted_file(self):
        self.assertEqual(op.safe_path(self.allow, "code", "public.txt"), self.root / "public.txt")

    def test_unknown_root_and_traversal_are_refused(self):
        for root, rel in (("other", "public.txt"), ("code", "../elsewhere")):
            with self.subTest(root=root, rel=rel), self.assertRaises(SystemExit):
                op.safe_path(self.allow, root, rel)

    def test_secret_name_and_symlink_escape_are_refused(self):
        (self.root / ".env").write_text("fixture")
        (self.root / "link").symlink_to(Path(self.tmp.name) / "outside")
        for rel in (".env", "link"):
            with self.subTest(rel=rel), self.assertRaises(SystemExit):
                op.safe_path(self.allow, "code", rel)


if __name__ == "__main__":
    unittest.main()
