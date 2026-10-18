import datetime as dt
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).with_name("sweep-retired-paths.py")
spec = importlib.util.spec_from_file_location("sweep", MODULE)
sweep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sweep)


class SweepTests(unittest.TestCase):
    def test_classified_batch_moves_to_holding_before_retired_sweep(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            vault = base / "vault"
            vault.mkdir()
            for folder in ("1 CRM", "2 Market/private-notes", "retired", "external-mirror", "9 Agents/machine"):
                (vault / folder).mkdir(parents=True)
            typed = vault / "1 CRM" / "typed.md"
            typed.write_text('---\ntype: "private-note"\n---\n')
            folder_match = vault / "2 Market" / "private-notes" / "folder.md"
            folder_match.write_text("# Folder match\n")
            index = vault / "retired" / "index.md"
            index.write_text('---\ntype: index\ntitle: "Private notes index"\n---\n')
            normal = vault / "retired" / "normal.md"
            normal.write_text("# Normal\n")
            mirror = vault / "external-mirror" / "private.md"
            mirror.write_text("---\ntype: private-note\n---\n")
            agent = vault / "9 Agents" / "machine" / "private.md"
            agent.write_text("---\ntype: private-note\n---\n")
            now = dt.datetime.now(dt.timezone.utc)
            old_time = (now - dt.timedelta(hours=1)).timestamp()
            for path in (typed, folder_match, normal, mirror, agent):
                os.utime(path, (old_time, old_time))
            roots = dict(sweep.DEFAULT_ROOTS, **{"external-mirror": "mirror"})
            classifier = sweep.classifier_from(Path(__file__).with_name("content-classifier.example.json"))
            holding = base / "holding"
            manifest = base / "manifest.txt"
            opts = dict(classifier=classifier, holding=holding, manifest=manifest,
                        vault_host_path="/srv/brain/vault")
            self.assertEqual(sweep.sweep(vault, roots, dt.timedelta(minutes=30), False, now, **opts), 1)
            self.assertTrue(typed.exists())
            self.assertTrue(index.exists())
            self.assertTrue((vault / "5 Inbox" / "captures" / "normal.md").exists())
            self.assertFalse(holding.exists())
            os.utime(index, (old_time, old_time))
            self.assertEqual(sweep.sweep(vault, roots, dt.timedelta(minutes=30), True, now, **opts), 0)
            self.assertTrue(typed.exists())
            self.assertFalse(holding.exists())
            self.assertEqual(sweep.sweep(vault, roots, dt.timedelta(minutes=30), False, now, **opts), 0)
            day = now.strftime("%Y-%m-%d")
            for rel in ("1 CRM/typed.md", "2 Market/private-notes/folder.md", "retired/index.md"):
                self.assertTrue((holding / day / rel).exists(), rel)
            self.assertTrue(mirror.exists())
            self.assertTrue(agent.exists())
            self.assertFalse((vault / "5 Inbox" / "captures" / "index.md").exists())
            lines = manifest.read_text().splitlines()
            self.assertEqual(len(lines), 3)
            self.assertTrue(any("/srv/brain/vault/retired/index.md" in line for line in lines))

    def test_subtype_matches_and_emptied_folders_are_pruned(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            vault = base / "vault"
            for folder in ("1 CRM/deep/deeper", "retired-empty", "retired/sub", "9 Agents/machine"):
                (vault / folder).mkdir(parents=True)
            subtype = vault / "1 CRM" / "deep" / "deeper" / "sub.md"
            subtype.write_text("---\ntype: private-note-draft\n---\n")
            stray = vault / "retired" / "sub" / "stray.md"
            stray.write_text("# Stray\n")
            now = dt.datetime.now(dt.timezone.utc)
            old_time = (now - dt.timedelta(hours=1)).timestamp()
            for path in (subtype, stray):
                os.utime(path, (old_time, old_time))
            classifier = sweep.classifier_from(Path(__file__).with_name("content-classifier.example.json"))
            opts = dict(classifier=classifier, holding=base / "holding", manifest=base / "manifest.txt",
                        vault_host_path="/srv/brain/vault")
            self.assertEqual(sweep.sweep(vault, sweep.DEFAULT_ROOTS, dt.timedelta(minutes=30), False, now, **opts), 1)
            day = now.strftime("%Y-%m-%d")
            self.assertTrue((base / "holding" / day / "1 CRM" / "deep" / "deeper" / "sub.md").exists())
            self.assertTrue((vault / "5 Inbox" / "captures" / "stray.md").exists())
            # Emptied folders go, deepest first; a section and its record folder stay.
            self.assertFalse((vault / "1 CRM" / "deep" / "deeper").exists())
            self.assertTrue((vault / "1 CRM" / "deep").exists())
            self.assertFalse((vault / "retired").exists())
            self.assertFalse((vault / "retired-empty").exists())

    def test_unknown_root_moves_but_mirror_stays(self):
        with tempfile.TemporaryDirectory() as temp:
            vault = Path(temp)
            (vault / "5 Inbox" / "captures").mkdir(parents=True)
            (vault / "9 Agents").mkdir()
            (vault / "external-mirror").mkdir()
            (vault / "external-mirror" / "page.md").write_text("# Keep\n")
            (vault / "retired").mkdir()
            old = vault / "retired" / "note.md"
            old.write_text("# Moved\n")
            now = dt.datetime.now(dt.timezone.utc)
            old_time = (now - dt.timedelta(hours=1)).timestamp()
            os.utime(old, (old_time, old_time))
            roots = dict(sweep.DEFAULT_ROOTS, **{"external-mirror": "mirror"})
            self.assertEqual(sweep.sweep(vault, roots, dt.timedelta(minutes=30), True, now), 1)
            self.assertTrue(old.exists())
            self.assertEqual(sweep.sweep(vault, roots, dt.timedelta(minutes=30), False, now), 1)
            self.assertFalse(old.exists())
            self.assertTrue((vault / "external-mirror" / "page.md").exists())
            captured = (vault / "5 Inbox" / "captures" / "note.md").read_text()
            self.assertIn('swept_from: "retired/note.md"', captured)
            self.assertIn("moved `retired/note.md`", (vault / "9 Agents" / "machine" / "traces" / "retired-path-sweep.md").read_text())

    def test_root_config_is_single_source_for_allowed_and_mirrors(self):
        with tempfile.TemporaryDirectory() as temp:
            config = Path(temp) / "roots.json"
            config.write_text('{"AGENTS.md":"managed","5 Inbox":"managed","9 Agents":"managed","example-mirror":"mirror"}')
            roots = sweep.roots_from(config)
            self.assertEqual(roots["example-mirror"], "mirror")
            allowed, mirrors = sweep.root_sets(roots)
            self.assertIn("example-mirror", allowed)
            self.assertEqual(mirrors, {"example-mirror"})
            config.write_text('{"AGENTS.md":"managed","5 Inbox":"managed","9 Agents":"managed","bad/path":"mirror"}')
            with self.assertRaises(ValueError):
                sweep.roots_from(config)


if __name__ == "__main__":
    unittest.main()
