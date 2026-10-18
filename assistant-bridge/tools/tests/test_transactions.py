from __future__ import annotations

import hashlib
import importlib.machinery
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
from datetime import datetime, timedelta, timezone

from .helpers import TOOLS, policy_text, write


def load_script(name: str, filename: str):
    tools_text = str(TOOLS)
    if tools_text not in sys.path:
        sys.path.insert(0, tools_text)
    loader = importlib.machinery.SourceFileLoader(name, str(TOOLS / filename))
    spec = importlib.util.spec_from_loader(name, loader)
    if spec is None:
        raise RuntimeError("cannot load bridge script")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class TransactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.importer = load_script("bridge_import_test", "bridge-import")
        cls.restorer = load_script("bridge_restore_test", "bridge-restore")
        from bridge_common import BridgeError
        import bridge_common
        from bridge_policy import load_policy

        cls.BridgeError = BridgeError
        cls.common = bridge_common
        cls.load_policy = staticmethod(load_policy)

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="bridge-transaction-")
        self.root = Path(self.temp.name)
        self.vault = self.root / "vault"
        self.run_dir = self.root / "backups" / "run"
        self.vault.mkdir()
        self.run_dir.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_import_second_write_failure_rolls_back_first(self) -> None:
        old = {"Shared/a.md": b"old-a", "Shared/b.md": b"old-b"}
        incoming = {"Shared/a.md": b"new-a", "Shared/b.md": b"new-b"}
        entries = []
        for rel, data in old.items():
            write(self.vault / rel, data)
            backup_rel = f"files/{rel}"
            write(self.run_dir / backup_rel, data)
            entries.append(
                {
                    "path": rel,
                    "existed": True,
                    "backup": backup_rel,
                    "before_sha256": hashlib.sha256(data).hexdigest(),
                    "after_sha256": hashlib.sha256(incoming[rel]).hexdigest(),
                }
            )
        expected = {rel: hashlib.sha256(data).hexdigest() for rel, data in old.items()}
        real_write = self.importer.secure_atomic_write
        failed = False

        def flaky(root, rel, data, *, mode=0o600):
            nonlocal failed
            if rel == "Shared/b.md" and not failed:
                failed = True
                raise self.BridgeError("synthetic", "synthetic write failure")
            return real_write(root, rel, data, mode=mode)

        with mock.patch.object(self.importer, "secure_atomic_write", side_effect=flaky):
            with self.assertRaises(self.BridgeError):
                self.importer.apply_incoming(
                    self.vault, incoming, entries, self.run_dir, expected
                )

        for rel, data in old.items():
            self.assertEqual((self.vault / rel).read_bytes(), data)

    def test_import_post_replace_failure_rolls_back_every_attempt(self) -> None:
        old = {"Shared/a.md": b"old-a", "Shared/b.md": b"old-b"}
        incoming = {"Shared/a.md": b"new-a", "Shared/b.md": b"new-b"}
        entries = []
        for rel, data in old.items():
            write(self.vault / rel, data)
            backup_rel = f"files/{rel}"
            write(self.run_dir / backup_rel, data)
            entries.append(
                {
                    "path": rel,
                    "existed": True,
                    "backup": backup_rel,
                    "before_sha256": hashlib.sha256(data).hexdigest(),
                    "after_sha256": hashlib.sha256(incoming[rel]).hexdigest(),
                }
            )
        expected = {rel: hashlib.sha256(data).hexdigest() for rel, data in old.items()}
        real_write = self.importer.secure_atomic_write
        failed = False

        def flaky(root, rel, data, *, mode=0o600):
            nonlocal failed
            result = real_write(root, rel, data, mode=mode)
            if rel == "Shared/b.md" and not failed:
                failed = True
                raise self.BridgeError("synthetic", "synthetic post-replace failure")
            return result

        with mock.patch.object(self.importer, "secure_atomic_write", side_effect=flaky):
            with self.assertRaises(self.BridgeError):
                self.importer.apply_incoming(
                    self.vault, incoming, entries, self.run_dir, expected
                )

        for rel, data in old.items():
            self.assertEqual((self.vault / rel).read_bytes(), data)

    def test_import_state_post_replace_failure_restores_prior_commit(self) -> None:
        state = self.root / "import-state"
        old = ("a" * 40 + "\n").encode("ascii")
        write(state, old)
        real_write = self.importer.atomic_write
        failed = False

        def flaky(path, data, *, mode=0o600):
            nonlocal failed
            result = real_write(path, data, mode=mode)
            if not failed:
                failed = True
                raise self.BridgeError("synthetic", "synthetic post-replace failure")
            return result

        with mock.patch.object(self.importer, "atomic_write", side_effect=flaky):
            with self.assertRaises(self.BridgeError):
                self.importer.update_state(
                    state,
                    "b" * 40,
                    old,
                    self.run_dir,
                )

        self.assertEqual(state.read_bytes(), old)

    def test_restore_second_write_failure_rolls_back_first(self) -> None:
        policy_path = self.root / "policy.toml"
        write(policy_path, policy_text())
        policy = self.load_policy(policy_path)
        files = []
        for name in ("a.md", "b.md"):
            rel = f"Shared/{name}"
            before = f"before-{name}".encode()
            after = f"after-{name}".encode()
            write(self.vault / rel, after)
            backup_rel = f"files/{rel}"
            write(self.run_dir / backup_rel, before)
            files.append(
                {
                    "path": rel,
                    "existed": True,
                    "backup": backup_rel,
                    "before_sha256": hashlib.sha256(before).hexdigest(),
                    "after_sha256": hashlib.sha256(after).hexdigest(),
                }
            )
        write(
            self.run_dir / "manifest.json",
            json.dumps({"version": 1, "run_id": "run", "files": files}),
        )
        real_write = self.restorer.secure_atomic_write
        failed = False

        def flaky(root, rel, data, *, mode=0o600):
            nonlocal failed
            if rel == "Shared/b.md" and not failed:
                failed = True
                raise self.BridgeError("synthetic", "synthetic write failure")
            return real_write(root, rel, data, mode=mode)

        with mock.patch.object(self.restorer, "secure_atomic_write", side_effect=flaky):
            with self.assertRaises(self.restorer.RestoreError):
                self.restorer.restore("run", str(self.vault), str(self.root / "backups"), policy)

        self.assertEqual((self.vault / "Shared/a.md").read_bytes(), b"after-a.md")
        self.assertEqual((self.vault / "Shared/b.md").read_bytes(), b"after-b.md")

    def test_audit_append_completes_partial_writes(self) -> None:
        audit = self.root / "audit.jsonl"
        real_write = self.common.os.write

        def partial(fd, data):
            return real_write(fd, data[:3])

        with mock.patch.object(self.common.os, "write", side_effect=partial):
            self.common.append_audit(audit, {"result_category": "success"})

        self.assertEqual(
            json.loads(audit.read_text(encoding="utf-8")),
            {"result_category": "success"},
        )

    def test_failed_audit_append_truncates_partial_record(self) -> None:
        audit = self.root / "audit.jsonl"
        self.common.append_audit(audit, {"result_category": "prior"})
        before = audit.read_bytes()
        real_write = self.common.os.write
        calls = 0

        def interrupted(fd, data):
            nonlocal calls
            calls += 1
            if calls == 1:
                return real_write(fd, data[:3])
            return 0

        with mock.patch.object(self.common.os, "write", side_effect=interrupted):
            with self.assertRaises(self.BridgeError):
                self.common.append_audit(audit, {"result_category": "never-committed"})

        self.assertEqual(audit.read_bytes(), before)

    def test_audit_reservation_handles_partial_finalize(self) -> None:
        audit = self.root / "audit.jsonl"
        reservation = self.common.reserve_audit(
            audit, {"result_category": "pending-remote-write"}
        )
        real_pwrite = self.common.os.pwrite

        def partial(fd, data, offset):
            return real_pwrite(fd, data[:5], offset)

        try:
            with mock.patch.object(self.common.os, "pwrite", side_effect=partial):
                reservation.finalize({"result_category": "success"})
        finally:
            reservation.close()

        self.assertEqual(
            json.loads(audit.read_text(encoding="utf-8")),
            {"result_category": "success"},
        )

    def test_failed_audit_reservation_truncates_partial_record(self) -> None:
        audit = self.root / "audit.jsonl"
        self.common.append_audit(audit, {"result_category": "prior"})
        before = audit.read_bytes()
        real_write = self.common.os.write
        calls = 0

        def interrupted(fd, data):
            nonlocal calls
            calls += 1
            if calls == 1:
                return real_write(fd, data[:3])
            return 0

        with mock.patch.object(self.common.os, "write", side_effect=interrupted):
            with self.assertRaises(self.BridgeError):
                self.common.reserve_audit(
                    audit, {"result_category": "pending-remote-write"}
                )

        self.assertEqual(audit.read_bytes(), before)

    def test_github_visibility_404_and_private_response_are_accepted(self) -> None:
        remote = "git@github-assistant-bridge:owner/repository.git"
        missing = self.common.urlerror.HTTPError(
            "https://api.github.com/repos/owner/repository", 404, "Not Found", None, None
        )
        with mock.patch.object(self.common.urlrequest, "urlopen", side_effect=missing):
            self.common.verify_github_not_public(remote, 123)

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _limit):
                return b'{"private":true,"id":123}'

        with mock.patch.object(self.common.urlrequest, "urlopen", return_value=Response()):
            self.common.verify_github_not_public(remote, 123)

    def test_github_public_response_is_rejected(self) -> None:
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _limit):
                return b'{"private":false,"id":123}'

        with mock.patch.object(self.common.urlrequest, "urlopen", return_value=Response()):
            with self.assertRaises(self.BridgeError) as caught:
                self.common.verify_github_not_public(
                    "git@github-assistant-bridge:owner/repository.git", 123
                )
        self.assertEqual(caught.exception.category, "visibility-mismatch")

    def test_github_repository_id_mismatch_is_rejected(self) -> None:
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _limit):
                return b'{"private":true,"id":999}'

        with mock.patch.object(self.common.urlrequest, "urlopen", return_value=Response()):
            with self.assertRaises(self.BridgeError) as caught:
                self.common.verify_github_not_public(
                    "git@github-assistant-bridge:owner/repository.git", 123
                )
        self.assertEqual(caught.exception.category, "visibility-mismatch")

    def test_github_timeout_and_rate_limit_fail_closed(self) -> None:
        failures = [
            TimeoutError("synthetic timeout"),
            self.common.urlerror.HTTPError(
                "https://api.github.com/repos/owner/repository",
                403,
                "rate limited",
                None,
                None,
            ),
        ]
        for failure in failures:
            with self.subTest(failure=type(failure).__name__):
                with mock.patch.object(
                    self.common.urlrequest, "urlopen", side_effect=failure
                ):
                    with self.assertRaises(self.BridgeError) as caught:
                        self.common.verify_github_not_public(
                            "git@github-assistant-bridge:owner/repository.git", 123
                        )
                self.assertEqual(caught.exception.category, "visibility-unverifiable")

    def test_stale_and_future_visibility_attestations_fail_closed(self) -> None:
        attestation = self.root / "repository.json"
        now = datetime.now(timezone.utc)
        for verified_at in (
            now - timedelta(days=32),
            now + timedelta(minutes=6),
        ):
            with self.subTest(verified_at=verified_at.isoformat()):
                write(
                    attestation,
                    json.dumps(
                        {
                            "version": 1,
                            "remote_url": str(self.root / "origin.git"),
                            "visibility": "private",
                            "repository_id": "synthetic-origin",
                            "verified_via": "local-test",
                            "verified_at": verified_at.isoformat(),
                        }
                    ),
                )
                attestation.chmod(0o600)
                with self.assertRaises(self.BridgeError) as caught:
                    self.common.verify_private_attestation(
                        attestation, str(self.root / "origin.git")
                    )
                self.assertEqual(caught.exception.category, "visibility-unverifiable")

    def test_pause_marker_holds_a_job_and_unreadable_directory_counts_as_paused(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            pause = Path(name) / "paused"
            pause.mkdir()
            self.assertFalse(self.common.job_paused("apply", pause))
            (pause / "apply").write_text("held for a test\n", encoding="utf-8")
            self.assertTrue(self.common.job_paused("apply", pause))
            self.assertFalse(self.common.job_paused("publish", pause))
            with mock.patch.object(self.common.os, "lstat", side_effect=PermissionError("denied")):
                self.assertTrue(self.common.job_paused("publish", pause))
            with mock.patch.dict(self.common.os.environ, {"BRIDGE_PAUSE_DIR": str(pause)}):
                self.assertTrue(self.common.job_paused("apply"))

    def test_job_status_round_trips_and_rejects_foreign_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            path = Path(name) / "publish-status.json"
            self.assertIsNone(self.common.read_job_status(path))
            self.common.write_job_status(path, {"last_real_run_at": "2026-09-23T17:00:00Z", "consecutive_skips": 0})
            document = self.common.read_job_status(path)
            self.assertEqual(document["consecutive_skips"], 0)
            self.assertIn("updated_at", document)
            self.assertEqual(path.stat().st_mode & 0o777, 0o644)
            path.write_text('{"version": 2}', encoding="utf-8")
            with self.assertRaises(self.BridgeError) as caught:
                self.common.read_job_status(path)
            self.assertEqual(caught.exception.category, "job-status-invalid")
            link = Path(name) / "link.json"
            link.symlink_to(path)
            with self.assertRaises(self.BridgeError):
                self.common.read_job_status(link)


if __name__ == "__main__":
    unittest.main()
