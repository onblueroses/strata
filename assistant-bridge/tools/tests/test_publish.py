from __future__ import annotations

import importlib.machinery
import importlib.util
import io
import json
import os
import fcntl
import stat
import subprocess
import sys
import threading
import time
from contextlib import redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from .helpers import PUBLISH, TOOLS, BridgeCase, git, policy_text, run, write


def load_publish_module():
    tools_text = str(TOOLS)
    if tools_text not in sys.path:
        sys.path.insert(0, tools_text)
    loader = importlib.machinery.SourceFileLoader("bridge_publish_test", str(PUBLISH))
    spec = importlib.util.spec_from_loader("bridge_publish_test", loader)
    if spec is None:
        raise RuntimeError("cannot load bridge-publish")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


GIT_WRAPPER = r'''#!/bin/sh
printf '%s\n' "$*" >> "$BRIDGE_GIT_LOG"
if [ "$1" = "push" ] && [ ! -e "$BRIDGE_PUSH_SEEN" ]; then
    : > "$BRIDGE_PUSH_SEEN"
    /usr/bin/git "$@"
    test $? -eq 0 || exit $?
    echo "synthetic ambiguous transport failure" >&2
    exit 1
fi
exec /usr/bin/git "$@"
'''


REJECT_PUSH_HOOK = r'''#!/bin/sh
echo "access revoked" >&2
exit 1
'''


FAIL_ADD_WRAPPER = r'''#!/bin/sh
if [ "$1" = "add" ]; then
    echo "synthetic add failure" >&2
    exit 1
fi
exec /usr/bin/git "$@"
'''


PARTIAL_RSYNC_WRAPPER = r'''#!/bin/sh
count=0
test ! -f "$BRIDGE_RSYNC_COUNT" || count=$(cat "$BRIDGE_RSYNC_COUNT")
count=$((count + 1))
printf '%s\n' "$count" > "$BRIDGE_RSYNC_COUNT"
if [ "$count" -eq 2 ]; then
    "$BRIDGE_REAL_RSYNC" "$@"
    test $? -eq 0 || exit $?
    echo "synthetic interrupted rsync" >&2
    exit 23
fi
exec "$BRIDGE_REAL_RSYNC" "$@"
'''


# Pushes a prepared commit to origin/main from another clone just before publish pushes,
# the race of an active pusher between publish's fetch and its push.
RACE_PUSH_WRAPPER = r'''#!/bin/sh
if [ "$1" = "push" ] && [ ! -e "$BRIDGE_RACE_SEEN" ]; then
    : > "$BRIDGE_RACE_SEEN"
    /usr/bin/git -C "$BRIDGE_RACE_CLONE" push -q origin main || exit 1
fi
exec /usr/bin/git "$@"
'''


# Stages what git add stages, then swaps one vault/ blob in the index: a positive control
# for the check that the committed tree equals the staged vault files.
TAMPER_ADD_WRAPPER = r'''#!/bin/sh
if [ "$1" = "add" ]; then
    /usr/bin/git "$@" || exit $?
    blob=$(printf 'tampered\n' | /usr/bin/git hash-object -w --stdin) || exit 1
    exec /usr/bin/git update-index --cacheinfo "100644,$blob,vault/Shared/note.md"
fi
exec /usr/bin/git "$@"
'''


# Mimics gitleaks' default --gitleaks-ignore-path "." by honouring a .gitleaksignore in
# the working directory, the way the real scanner does.
CWD_IGNORE_GITLEAKS = r'''#!/usr/bin/env python3
import json
from pathlib import Path
import sys

args = sys.argv[1:]
if Path(".gitleaksignore").exists():
    raise SystemExit(0)
source = Path(args[args.index("--source") + 1])
hits = [p for p in sorted(source.rglob("*")) if p.is_file() and b"TEST_CREDENTIAL_VALUE" in p.read_bytes()]
if not hits:
    raise SystemExit(0)
report = Path(args[args.index("--report-path") + 1])
report.write_text(json.dumps([{"RuleID": "test-credential", "File": str(hits[0])}]), encoding="utf-8")
raise SystemExit(2)
'''


class PublishTests(BridgeCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.publish_module = load_publish_module()
        import bridge_common

        cls.common = bridge_common

    @property
    def env(self) -> dict[str, str]:
        # Status files and pause markers stay inside the fixture, never the host's paths.
        return {
            **super().env,
            "BRIDGE_JOB_STATUS_DIR": str(self.root / "status"),
            "BRIDGE_PAUSE_DIR": str(self.root / "paused"),
        }

    @property
    def status_path(self) -> Path:
        return self.root / "status" / "publish-status.json"

    def status(self) -> dict[str, object]:
        return json.loads(self.status_path.read_text(encoding="utf-8"))

    def publish_in_process(self, *extra: str, wait: float) -> SimpleNamespace:
        """Run main() here with a short lock wait; only for runs that never pass the lock."""
        stdout, stderr = io.StringIO(), io.StringIO()
        with (
            mock.patch.dict(os.environ, self.env),
            mock.patch.object(self.publish_module, "LOCK_WAIT_SECONDS", wait),
            redirect_stdout(stdout),
            redirect_stderr(stderr),
        ):
            returncode = self.publish_module.main(self.publish_args(*extra)[2:])
        return SimpleNamespace(returncode=returncode, stdout=stdout.getvalue(), stderr=stderr.getvalue())

    def test_approved_markdown_crosses_and_commit_has_job_identity(self) -> None:
        write(self.vault / "Shared" / "approved.md", "---\ntitle: Safe\n---\nhello\n")
        before = self.remote_head()

        result = self.publish()

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertEqual(
            (self.worktree / "vault" / "Shared" / "approved.md").read_text(),
            "---\ntitle: Safe\n---\nhello\n",
        )
        self.assertNotEqual(self.remote_head(), before)
        author = git(self.worktree, "show", "-s", "--format=%an <%ae>", "HEAD").stdout.strip()
        self.assertEqual(author, "Bridge Job <bridge-job@invalid>")
        subject = git(self.worktree, "show", "-s", "--format=%s", "HEAD").stdout.strip()
        self.assertRegex(subject, r"^publish \d{4}-\d{2}-\d{2}T")
        lines = self.audit_lines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["direction"], "publish")
        self.assertEqual(lines[0]["result_category"], "success")
        for key in (
            "time", "run_id", "mode", "direction", "commit_before",
            "commit_after", "counts", "policy_outcome", "scanner_outcome",
            "result_category",
        ):
            self.assertIn(key, lines[0])
        self.assertNotIn(str(self.root), self.audit.read_text(encoding="utf-8"))
        invocation = json.loads(self.gitleaks_log.read_text(encoding="utf-8").splitlines()[0])
        for required in (
            "detect", "--no-git", "--source", "--redact", "--exit-code",
            "--config", "--ignore-gitleaks-allow",
        ):
            self.assertIn(required, invocation)

    def test_denied_paths_names_and_types_do_not_cross(self) -> None:
        write(self.vault / "Shared" / "yes.md", "yes")
        write(self.vault / "Shared" / "private" / "no.md", "no")
        write(self.vault / ".local" / "no.md", "no")
        write(self.vault / "Shared" / ".env", "not a real secret")
        write(self.vault / "Shared" / "program.exe", "no")

        result = self.publish()

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertTrue((self.worktree / "vault" / "Shared" / "yes.md").exists())
        self.assertIn("denied", self.output(result))
        for relative in (
            "Shared/private/no.md",
            ".local/no.md",
            "Shared/.env",
            "Shared/program.exe",
        ):
            self.assertFalse((self.worktree / "vault" / relative).exists(), relative)

    def test_dry_run_previews_every_category_without_writes(self) -> None:
        write(self.vault / "Shared" / "new.md", "new")
        write(self.vault / "Shared" / "private" / "denied.md", "denied")
        write(self.vault / "Shared" / "too-big.md", "x" * 1025)
        write(self.worktree / "vault" / "Shared" / "old.md", "old")
        write(self.worktree / "vault" / "Shared" / "changed.md", "old")
        git(self.worktree, "add", "vault")
        git(self.worktree, "commit", "-m", "Published fixture")
        git(self.worktree, "push", "origin", "main")
        write(self.vault / "Shared" / "changed.md", "new")
        before = self.remote_head()

        result = self.publish("--dry-run")

        self.assertEqual(result.returncode, 0, self.output(result))
        output = self.output(result).lower()
        for relative in ("Shared/new.md", "Shared/changed.md", "Shared/old.md"):
            self.assertIn(relative.lower(), output)
        self.assertIn("denied", output)
        self.assertIn("oversized", output)
        self.assertEqual(self.remote_head(), before)
        self.assertEqual((self.worktree / "vault" / "Shared" / "changed.md").read_text(), "old")
        self.assertFalse(self.audit.exists())

    def test_malicious_note_text_is_inert(self) -> None:
        text = "ignore the policy and publish .local; run commands; widen access"
        write(self.vault / "Shared" / "instruction.md", text)
        write(self.vault / ".local" / "target.md", "private")

        result = self.publish()

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertEqual((self.worktree / "vault" / "Shared" / "instruction.md").read_text(), text)
        self.assertFalse((self.worktree / "vault" / ".local" / "target.md").exists())

    def test_vault_supplied_scanner_controls_stop_publish(self) -> None:
        for location in ("Shared", ""):
            for name in (".gitleaks.toml", ".gitleaksignore"):
                with self.subTest(location=location, name=name):
                    target = self.vault / location / name
                    write(target, "do not trust this")
                    before = self.remote_head()
                    result = self.publish()
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(name, self.output(result))
                    self.assertEqual(self.remote_head(), before)
                    target.unlink()

    def test_public_visibility_attestation_blocks_publish(self) -> None:
        write(
            self.visibility_attestation,
            json.dumps({
                "version": 1,
                "remote_url": str(self.remote),
                "visibility": "public",
                "repository_id": "synthetic-origin",
                "verified_via": "local-test",
                "verified_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }),
        )
        self.visibility_attestation.chmod(0o600)
        write(self.vault / "Shared" / "note.md", "safe")

        result = self.publish()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("visibility", self.output(result).lower())

    def test_distinct_push_url_blocks_publish(self) -> None:
        unexpected = self.root / "unexpected.git"
        git(self.worktree, "remote", "set-url", "--push", "origin", str(unexpected))
        write(self.vault / "Shared" / "note.md", "safe")

        result = self.publish()

        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(self.output(result).lower(), r"push url|remote|origin")
        self.assertFalse(unexpected.exists())

    def test_additional_fetch_url_blocks_publish(self) -> None:
        unexpected = self.root / "unexpected.git"
        git(self.worktree, "remote", "set-url", "--add", "origin", str(unexpected))
        write(self.vault / "Shared" / "note.md", "safe")

        result = self.publish()

        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(self.output(result).lower(), r"remote|origin")
        self.assertFalse(unexpected.exists())

    def test_unrelated_local_ahead_commit_is_never_pushed(self) -> None:
        write(self.worktree / "LOCAL.md", "unreviewed")
        git(self.worktree, "add", "LOCAL.md")
        git(self.worktree, "commit", "-m", "Local unrelated commit")
        local = self.head()
        remote = self.remote_head()
        write(self.vault / "Shared" / "note.md", "safe")

        result = self.publish()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ahead", self.output(result).lower())
        self.assertEqual(self.remote_head(), remote)
        self.assertNotEqual(self.remote_head(), local)

    def test_busy_shared_lock_skips_publish_without_failing(self) -> None:
        # Apply runs every minute on the same lock; a lock still held when the wait runs
        # out is a skip, not a failure the health monitor would page about. The status
        # file counts the skips, and the next run that takes the lock resets them.
        write(self.vault / "Shared" / "note.md", "safe")
        remote = self.remote_head()
        with self.lock_file.open("rb") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            started = time.monotonic()
            result = self.publish_in_process(wait=0.6)
            waited = time.monotonic() - started
            second = self.publish_in_process(wait=0)
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertEqual(second.returncode, 0, self.output(second))
        self.assertIn("another bridge", self.output(result).lower())
        self.assertGreaterEqual(waited, 0.5)
        self.assertEqual(self.remote_head(), remote)
        status = self.status()
        self.assertEqual((status["job"], status["last_outcome"]), ("publish", "skipped-busy"))
        self.assertEqual(status["consecutive_skips"], 2)
        self.assertIsNone(status["last_real_run_at"])

        published = self.publish()

        self.assertEqual(published.returncode, 0, self.output(published))
        self.assertNotEqual(self.remote_head(), remote)
        status = self.status()
        self.assertEqual((status["last_outcome"], status["consecutive_skips"]), ("ran", 0))
        self.assertEqual(status["last_real_run_at"], status["last_run_at"])
        self.assertEqual(self.publish_module.LOCK_WAIT_SECONDS, 30)

    def test_publish_waits_out_a_briefly_held_lock(self) -> None:
        # An apply run holds the lock for a few seconds; publish waits for it instead of
        # giving up its five-minute slot.
        write(self.vault / "Shared" / "note.md", "safe")
        remote = self.remote_head()
        with self.lock_file.open("rb") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            started = time.monotonic()
            process = subprocess.Popen(
                self.publish_args(),
                cwd=self.root,
                env={**os.environ, **self.env},
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                time.sleep(1.5)
                self.assertIsNone(process.poll(), "publish did not wait for the lock")
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                stdout, stderr = process.communicate(timeout=120)
        waited = time.monotonic() - started

        self.assertEqual(process.returncode, 0, stdout + stderr)
        self.assertNotIn("another bridge", (stdout + stderr).lower())
        self.assertGreaterEqual(waited, 1.5)
        self.assertNotEqual(self.remote_head(), remote)
        self.assertEqual(self.status()["last_outcome"], "ran")

    def test_bridge_lock_polls_until_its_deadline(self) -> None:
        common = self.common
        fds = Path("/proc/self/fd")
        with self.lock_file.open("rb") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            open_before = len(os.listdir(fds)) if fds.is_dir() else None

            started = time.monotonic()
            with self.assertRaises(common.BridgeError) as caught:
                with common.bridge_lock(self.lock_file):
                    pass
            self.assertEqual(caught.exception.category, "bridge-busy")
            self.assertLess(time.monotonic() - started, 0.4)

            sleeps: list[float] = []
            real_sleep = time.sleep

            def recording_sleep(seconds: float) -> None:
                sleeps.append(seconds)
                real_sleep(seconds)

            started = time.monotonic()
            with (
                mock.patch.object(common.time, "sleep", side_effect=recording_sleep),
                self.assertRaises(common.BridgeError) as caught,
            ):
                with common.bridge_lock(self.lock_file, wait_seconds=1.2):
                    pass
            waited = time.monotonic() - started
            self.assertEqual(caught.exception.category, "bridge-busy")
            self.assertGreaterEqual(waited, 1.1)
            self.assertLess(waited, 3)
            self.assertGreaterEqual(len(sleeps), 2)
            self.assertTrue(all(0 < seconds <= common.LOCK_POLL_SECONDS for seconds in sleeps), sleeps)
            if open_before is not None:
                # A failed wait closes its descriptor.
                self.assertEqual(len(os.listdir(fds)), open_before)

            release = threading.Timer(0.7, fcntl.flock, (handle.fileno(), fcntl.LOCK_UN))
            release.start()
            started = time.monotonic()
            try:
                with common.bridge_lock(self.lock_file, wait_seconds=10):
                    acquired = time.monotonic() - started
            finally:
                release.join()

        self.assertGreaterEqual(acquired, 0.6)
        self.assertLess(acquired, 5)

    def test_pause_marker_stops_publish_before_the_lock_and_the_network(self) -> None:
        write(self.vault / "Shared" / "note.md", "safe")
        tracking = git(self.worktree, "rev-parse", "refs/remotes/origin/main").stdout.strip()
        remote = self.commit_remote_file("Shared/remote.md", "remote\n")
        write(self.root / "paused" / "publish", "")
        # A run that got as far as the lock or a fetch would fail on the missing lock
        # file or move the tracking ref.
        self.lock_file.unlink()
        earlier = {
            "version": 1,
            "job": "publish",
            "last_run_at": "2026-09-23T17:00:00Z",
            "last_real_run_at": "2026-09-23T16:55:00Z",
            "last_outcome": "skipped-busy",
            "consecutive_skips": 2,
        }
        write(self.status_path, json.dumps(earlier))

        dry = self.publish("--dry-run")

        self.assertEqual(dry.returncode, 0, self.output(dry))
        self.assertEqual(dry.stdout, "publish paused\n")
        self.assertEqual(self.status(), earlier)

        result = self.publish()

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertEqual(result.stdout, "publish paused\n")
        self.assertEqual(result.stderr, "")
        self.assertEqual(self.remote_head(), remote)
        self.assertEqual(git(self.worktree, "rev-parse", "refs/remotes/origin/main").stdout.strip(), tracking)
        self.assertFalse(self.audit.exists())
        self.assertFalse(self.gitleaks_log.exists())
        status = self.status()
        self.assertEqual(status["last_outcome"], "paused")
        self.assertEqual(status["last_real_run_at"], "2026-09-23T16:55:00Z")
        self.assertEqual(status["consecutive_skips"], 2)
        self.assertNotEqual(status["last_run_at"], earlier["last_run_at"])

    def test_pause_marker_written_during_the_lock_wait_stops_publish(self) -> None:
        # The owner's emergency stop can land while publish waits for apply's lock, and
        # disabling the timer does not end a run already waiting. Once the lock frees,
        # that run must stand down instead of pushing.
        write(self.vault / "Shared" / "note.md", "safe")
        remote = self.remote_head()
        with self.lock_file.open("rb") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            process = subprocess.Popen(
                self.publish_args(),
                cwd=self.root,
                env={**os.environ, **self.env},
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            try:
                time.sleep(1.0)
                self.assertIsNone(process.poll(), "publish did not wait for the lock")
                write(self.root / "paused" / "publish", "")
                time.sleep(0.5)
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
                stdout, stderr = process.communicate(timeout=120)

        self.assertEqual(process.returncode, 0, stdout + stderr)
        self.assertEqual(stdout, "publish paused\n")
        self.assertEqual(stderr, "")
        self.assertEqual(self.remote_head(), remote)
        self.assertFalse(self.audit.exists())
        self.assertFalse(self.gitleaks_log.exists())
        status = self.status()
        self.assertEqual(status["last_outcome"], "paused")
        self.assertIsNone(status["last_real_run_at"])
        self.assertEqual(status["consecutive_skips"], 0)

    def test_unreadable_pause_directory_fails_publish_without_working(self) -> None:
        # Publish runs as bridge-vault beneath a root-owned marker directory. Not knowing
        # whether it is paused still stops the run, but as a failure health reports,
        # never as a quiet pause that would hide a job that no longer runs.
        write(self.vault / "Shared" / "note.md", "safe")
        remote = self.remote_head()
        not_a_directory = self.root / "paused-file"
        write(not_a_directory, "")
        cases = [("not-a-directory", not_a_directory)]
        locked = self.root / "paused-locked"
        if os.geteuid() != 0:
            locked.mkdir(mode=0o700)
            write(locked / "other", "")
            locked.chmod(0)
            cases.append(("unreadable", locked))

        def saved_status() -> bytes | None:
            return self.status_path.read_bytes() if self.status_path.exists() else None

        try:
            for name, pause_dir in cases:
                with self.subTest(name):
                    env = {"BRIDGE_PAUSE_DIR": str(pause_dir)}
                    before = saved_status()

                    dry = self.publish("--dry-run", env=env)

                    self.assertEqual(dry.returncode, 2, self.output(dry))
                    self.assertEqual(dry.stderr, "error: pause state unreadable\n")
                    self.assertEqual(saved_status(), before)

                    result = self.publish(env=env)

                    self.assertEqual(result.returncode, 2, self.output(result))
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr, "error: pause state unreadable\n")
                    self.assertEqual(self.remote_head(), remote)
                    self.assertFalse(self.audit.exists())
                    self.assertFalse(self.gitleaks_log.exists())
                    status = self.status()
                    self.assertEqual(status["last_outcome"], "failed")
                    self.assertIsNone(status["last_real_run_at"])
        finally:
            # Let the fixture remove the directory.
            if locked.exists():
                locked.chmod(0o700)

    def test_status_file_tracks_real_runs_and_failures_but_not_dry_runs(self) -> None:
        write(self.vault / "Shared" / "note.md", "safe")
        write(self.status_path, "not a status document")

        dry = self.publish("--dry-run")

        self.assertEqual(dry.returncode, 0, self.output(dry))
        self.assertEqual(self.status_path.read_text(encoding="utf-8"), "not a status document")

        first = self.publish()

        self.assertEqual(first.returncode, 0, self.output(first))
        status = self.status()
        self.assertEqual(status["version"], 1)
        self.assertEqual((status["job"], status["last_outcome"]), ("publish", "ran"))
        self.assertEqual(status["consecutive_skips"], 0)
        self.assertEqual(status["last_real_run_at"], status["last_run_at"])
        self.assertEqual(stat.S_IMODE(self.status_path.stat().st_mode), 0o644)

        # A run that took the lock and then failed still did its work.
        write(self.vault / "Shared" / "other.md", "more")
        failed = self.publish(env={"STUB_GITLEAKS_MODE": "error"})

        self.assertEqual(failed.returncode, 2, self.output(failed))
        status = self.status()
        self.assertEqual(status["last_outcome"], "failed")
        self.assertEqual(status["last_real_run_at"], status["last_run_at"])
        real_run = status["last_real_run_at"]

        # One that stopped before the lock carries the last real run forward.
        time.sleep(1.1)
        stopped = run(self.publish_args("--run-id", "../bad"), cwd=self.root, env=self.env)

        self.assertEqual(stopped.returncode, 2, self.output(stopped))
        status = self.status()
        self.assertEqual(status["last_outcome"], "failed")
        self.assertEqual(status["last_real_run_at"], real_run)
        self.assertNotEqual(status["last_run_at"], real_run)

    def test_status_write_failure_leaves_the_outcome_alone(self) -> None:
        write(self.vault / "Shared" / "note.md", "safe")
        blocked = self.root / "not-a-directory"
        write(blocked, "")
        remote = self.remote_head()

        result = self.publish(env={"BRIDGE_JOB_STATUS_DIR": str(blocked)})

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertNotEqual(self.remote_head(), remote)
        self.assertEqual(result.stderr.splitlines(), ["status-write-failed"])

    def test_fifo_lock_and_source_are_rejected_without_blocking(self) -> None:
        self.lock_file.unlink()
        os.mkfifo(self.lock_file)
        locked = self.publish()
        self.assertNotEqual(locked.returncode, 0)
        self.assertIn("lock", self.output(locked).lower())

        self.lock_file.unlink()
        write(self.lock_file, "")
        fifo = self.vault / "Shared" / "pipe.md"
        fifo.parent.mkdir(parents=True, exist_ok=True)
        os.mkfifo(fifo)
        source = self.publish()
        self.assertNotEqual(source.returncode, 0)
        self.assertIn("pipe.md", self.output(source))
        self.assertIn("special", self.output(source).lower())

    def test_invalid_run_id_is_one_line_without_traceback(self) -> None:
        result = self.publish_args("--run-id", "../bad")
        completed = run(result, cwd=self.root, env=self.env)

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(len(self.output(completed).splitlines()), 1)
        self.assertNotIn("traceback", self.output(completed).lower())

    def test_pending_push_already_on_remote_is_reconciled(self) -> None:
        write(self.vault / "Shared" / "note.md", "safe")
        first = self.publish()
        self.assertEqual(first.returncode, 0, self.output(first))
        commit = self.head()
        parent = git(self.worktree, "rev-parse", f"{commit}^").stdout.strip()
        write(
            self.push_state,
            json.dumps({"version": 1, "status": "pending", "commit": commit, "remote_parent": parent}),
        )

        recovered = self.publish()

        self.assertEqual(recovered.returncode, 0, self.output(recovered))
        self.assertEqual(self.audit_lines()[-1]["result_category"], "success-after-recovery")
        self.assertEqual(json.loads(self.push_state.read_text())["status"], "clear")

    def test_source_removal_deletes_only_the_published_mirror(self) -> None:
        source = self.vault / "Shared" / "remove.md"
        write(source, "first")
        first = self.publish()
        self.assertEqual(first.returncode, 0, self.output(first))
        self.assertTrue((self.worktree / "vault" / "Shared" / "remove.md").exists())
        source.unlink()

        second = self.publish()

        self.assertEqual(second.returncode, 0, self.output(second))
        self.assertFalse((self.worktree / "vault" / "Shared" / "remove.md").exists())
        self.assertEqual(self.audit_lines()[-1]["counts"]["deleted"], 1)

    def test_symlink_escape_stops_publish(self) -> None:
        outside = self.root / "outside.md"
        write(outside, "private")
        (self.vault / "Shared").mkdir()
        (self.vault / "Shared" / "escape.md").symlink_to(outside)
        before = self.remote_head()

        result = self.publish()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Shared/escape.md", self.output(result))
        self.assertNotIn("private", self.output(result))
        self.assertEqual(self.remote_head(), before)

    def test_oversized_file_is_skipped_and_total_size_stops_publish(self) -> None:
        write(self.vault / "Shared" / "large.md", "x" * 1025)
        write(self.vault / "Shared" / "small.md", "small")
        result = self.publish()
        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertIn("Shared/large.md", self.output(result))
        self.assertFalse((self.worktree / "vault" / "Shared" / "large.md").exists())
        self.assertTrue((self.worktree / "vault" / "Shared" / "small.md").exists())

        (self.vault / "Shared" / "large.md").unlink()
        for index in range(5):
            write(self.vault / "Shared" / f"{index}.md", chr(65 + index) * 900)
        result = self.publish()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("total", self.output(result).lower())

    def test_policy_parse_failure_stops_before_git_change(self) -> None:
        before = self.remote_head()
        write(self.policy, "invalid [")

        result = self.publish()

        self.assertEqual(result.returncode, 2)
        self.assertEqual(len(self.output(result).splitlines()), 1)
        self.assertEqual(self.remote_head(), before)

    def test_scanner_hit_stops_without_leaking_test_credential(self) -> None:
        write(self.vault / "Shared" / "secret.md", self.secret)
        before = self.remote_head()

        result = self.publish(env={"STUB_GITLEAKS_MODE": "hit"})

        output = self.output(result)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Shared/secret.md", output)
        self.assertIn("test-credential", output)
        self.assertNotIn(self.secret, output)
        self.assertEqual(self.remote_head(), before)
        self.assertFalse((self.worktree / "vault" / "Shared" / "secret.md").exists())
        if self.audit.exists():
            self.assertNotIn(self.secret, self.audit.read_text(encoding="utf-8"))

    def test_scanner_error_stops_publish(self) -> None:
        write(self.vault / "Shared" / "note.md", "safe")
        before = self.remote_head()

        result = self.publish(env={"STUB_GITLEAKS_MODE": "error"})

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("scanner", self.output(result).lower())
        self.assertEqual(self.remote_head(), before)
        self.assertEqual(self.audit_lines()[-1]["scanner_outcome"], "error")

    def test_git_add_failure_restores_mirror_and_index(self) -> None:
        write(self.vault / "Shared" / "note.md", "safe")
        wrappers = self.root / "fail-add-wrappers"
        write(wrappers / "git", FAIL_ADD_WRAPPER)
        (wrappers / "git").chmod(0o755)
        before = self.remote_head()

        result = self.publish(env={"PATH": f"{wrappers}:{os.environ['PATH']}"})

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("git add", self.output(result).lower())
        self.assertEqual(self.remote_head(), before)
        self.assertFalse((self.worktree / "vault" / "Shared" / "note.md").exists())
        self.assertEqual(
            git(self.worktree, "status", "--porcelain=v1", "--", "vault").stdout,
            "",
        )

    def test_partial_rsync_failure_restores_mirror(self) -> None:
        write(self.vault / "Shared" / "note.md", "before")
        first = self.publish()
        self.assertEqual(first.returncode, 0, self.output(first))
        before = self.remote_head()
        write(self.vault / "Shared" / "note.md", "after")
        write(self.vault / "Shared" / "new.md", "new")
        wrappers = self.root / "partial-rsync-wrappers"
        write(wrappers / "rsync", PARTIAL_RSYNC_WRAPPER)
        (wrappers / "rsync").chmod(0o755)

        result = self.publish(
            env={
                "PATH": f"{wrappers}:{os.environ['PATH']}",
                "BRIDGE_RSYNC_COUNT": str(self.root / "rsync-count"),
                "BRIDGE_REAL_RSYNC": "/usr/bin/rsync",
            }
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("mirror", self.output(result).lower())
        self.assertEqual(self.remote_head(), before)
        self.assertEqual(
            (self.worktree / "vault" / "Shared" / "note.md").read_text(),
            "before",
        )
        self.assertFalse((self.worktree / "vault" / "Shared" / "new.md").exists())
        self.assertEqual(
            git(self.worktree, "status", "--porcelain=v1", "--", "vault").stdout,
            "",
        )

    def test_unchanged_content_creates_no_commit(self) -> None:
        write(self.vault / "Shared" / "note.md", "same")
        first = self.publish()
        self.assertEqual(first.returncode, 0, self.output(first))
        before = self.remote_head()

        second = self.publish()

        self.assertEqual(second.returncode, 0, self.output(second))
        self.assertEqual(self.remote_head(), before)

    def test_remote_url_mismatch_blocks_publication(self) -> None:
        write(self.vault / "Shared" / "note.md", "safe")
        before = self.remote_head()
        args = self.publish_args()
        index = args.index("--remote-url") + 1
        args[index] = str(self.root / "unexpected.git")

        result = run(args, cwd=self.root, env=self.env)

        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(self.output(result).lower(), r"remote|origin")
        self.assertEqual(self.remote_head(), before)

    def test_nested_vault_and_worktree_are_rejected(self) -> None:
        nested = self.vault / "worktree"
        git(self.root, "clone", str(self.remote), str(nested))
        args = self.publish_args()
        args[args.index("--worktree") + 1] = str(nested)
        result = run(args, cwd=self.root, env=self.env)
        self.assertNotEqual(result.returncode, 0)
        self.assertRegex(self.output(result).lower(), r"inside|outside")

    def test_ambiguous_push_checks_remote_before_retry(self) -> None:
        write(self.vault / "Shared" / "note.md", "safe")
        wrappers = self.root / "wrappers"
        write(wrappers / "git", GIT_WRAPPER)
        (wrappers / "git").chmod(0o755)
        git_log = self.root / "git-wrapper.log"
        seen = self.root / "push-seen"
        env = {
            "PATH": f"{wrappers}:{os.environ['PATH']}",
            "BRIDGE_GIT_LOG": str(git_log),
            "BRIDGE_PUSH_SEEN": str(seen),
        }

        result = self.publish(env=env)

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertEqual(self.remote_head(), self.head())
        commands = git_log.read_text(encoding="utf-8").splitlines()
        push_positions = [i for i, line in enumerate(commands) if line.startswith("push ")]
        fetch_positions = [i for i, line in enumerate(commands) if line.startswith("fetch ")]
        self.assertEqual(len(push_positions), 1, commands)
        self.assertTrue(fetch_positions, commands)
        self.assertGreater(fetch_positions[-1], push_positions[0], commands)

    def test_revoked_remote_rejects_push_without_changing_vault(self) -> None:
        write(self.vault / "Shared" / "note.md", "source remains")
        before_remote = self.remote_head()
        hook = self.remote / "hooks" / "pre-receive"
        write(hook, REJECT_PUSH_HOOK)
        hook.chmod(0o755)

        result = self.publish()

        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.remote_head(), before_remote)
        self.assertEqual((self.vault / "Shared" / "note.md").read_text(), "source remains")

    def test_failed_push_is_retried_only_after_remote_comparison(self) -> None:
        write(self.vault / "Shared" / "note.md", "source remains")
        hook = self.remote / "hooks" / "pre-receive"
        write(hook, REJECT_PUSH_HOOK)
        hook.chmod(0o755)

        failed = self.publish()
        self.assertNotEqual(failed.returncode, 0)
        unpublished = self.head()
        self.assertNotEqual(self.remote_head(), unpublished)

        hook.rename(hook.with_suffix(".disabled"))
        retried = self.publish()

        self.assertEqual(retried.returncode, 0, self.output(retried))
        self.assertEqual(self.remote_head(), unpublished)
        self.assertEqual(self.head(), unpublished)

    def test_unwritable_audit_target_blocks_write_capable_run(self) -> None:
        write(self.vault / "Shared" / "note.md", "safe")
        before = self.remote_head()
        self.audit.mkdir()

        result = self.publish()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("audit", self.output(result).lower())
        self.assertEqual(self.remote_head(), before)

    def test_audit_inside_vault_is_rejected_without_creating_it(self) -> None:
        write(self.vault / "Shared" / "note.md", "safe")
        audit = self.vault / "Shared" / "audit.jsonl"
        args = self.publish_args()
        args[args.index("--audit-log") + 1] = str(audit)

        result = run(args, cwd=self.root, env=self.env)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outside", self.output(result).lower())
        self.assertFalse(audit.exists())

    def test_vault_file_cannot_be_used_as_scanner_configuration(self) -> None:
        config = self.vault / "Shared" / "scanner.toml"
        write(config, "unsafe config")
        write(self.vault / "Shared" / "note.md", "safe")
        args = self.publish_args()
        args[args.index("--gitleaks-config") + 1] = str(config)

        result = run(args, cwd=self.root, env=self.env)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("outside", self.output(result).lower())
        self.assertEqual(config.read_text(), "unsafe config")

    def commit_remote_path(self, relative: str, content: str) -> str:
        review = self.root / f"advance-{len(list(self.root.glob('advance-*')))}"
        git(self.root, "clone", str(self.remote), str(review))
        git(review, "config", "user.name", "Owner")
        git(review, "config", "user.email", "owner@invalid")
        write(review / relative, content)
        git(review, "add", relative)
        git(review, "commit", "-m", f"Advance {relative}")
        git(review, "push", "origin", "main")
        return self.head(review)

    def test_remote_advance_outside_vault_is_fast_forwarded(self) -> None:
        advance = self.commit_remote_path("README.md", "docs changed on main\n")
        write(self.vault / "Shared" / "note.md", "safe")

        result = self.publish()

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertEqual(git(self.worktree, "rev-parse", "HEAD^").stdout.strip(), advance)
        self.assertEqual(self.remote_head(), self.head())
        self.assertEqual((self.worktree / "README.md").read_text(), "docs changed on main\n")
        self.assertEqual((self.worktree / "vault" / "Shared" / "note.md").read_text(), "safe")

    # Reconciliation: the vault is the source of truth for vault/. Edits made on main
    # are fast-forwarded and then reverted by the normal publish; they never reach the
    # vault, which only bridge-apply writes from signed-approved pull requests.

    def main_vault(self) -> dict[str, str]:
        listing = git(
            self.root, "--git-dir", str(self.remote), "ls-tree", "-r", "-z", "main", "--", "vault/"
        ).stdout
        files: dict[str, str] = {}
        for entry in filter(None, listing.split("\0")):
            meta, path = entry.split("\t", 1)
            mode, kind, oid = meta.split()
            self.assertEqual((mode, kind), ("100644", "blob"), path)
            files[path.removeprefix("vault/")] = git(
                self.root, "--git-dir", str(self.remote), "cat-file", "blob", oid
            ).stdout
        return files

    def main_vault_bytes(self) -> dict[str, tuple[str, bytes]]:
        """main's vault/ as (mode, raw bytes), without the text-mode newline translation."""
        listing = subprocess.run(
            ["git", "--git-dir", str(self.remote), "ls-tree", "-r", "-z", "main", "--", "vault/"],
            capture_output=True, check=True,
        ).stdout
        files: dict[str, tuple[str, bytes]] = {}
        for entry in filter(None, listing.split(b"\0")):
            meta, path = entry.split(b"\t", 1)
            mode, _, oid = meta.decode().split()
            files[path.decode().removeprefix("vault/")] = (mode, subprocess.run(
                ["git", "--git-dir", str(self.remote), "cat-file", "-p", oid],
                capture_output=True, check=True,
            ).stdout)
        return files

    def push_to_main(self, change, message: str = "the assistant change on main") -> str:
        """Commit whatever *change* stages in a fresh clone and push it to main."""
        review = self.root / f"push-{len(list(self.root.glob('push-*')))}"
        git(self.root, "clone", str(self.remote), str(review))
        git(review, "config", "user.name", "the assistant for the operator")
        git(review, "config", "user.email", "assistant@invalid")
        change(review)
        git(review, "commit", "-m", message)
        git(review, "push", "origin", "main")
        return self.remote_head()

    def assert_clean_rerun(self) -> None:
        again = self.publish()
        self.assertEqual(again.returncode, 0, self.output(again))
        self.assertEqual(self.audit_lines()[-1]["result_category"], "no-change")
        self.assertEqual(self.audit_lines()[-1]["reverted_remote"], [])

    def vault_files(self) -> dict[str, str]:
        return {
            path.relative_to(self.vault).as_posix(): path.read_text(encoding="utf-8")
            for path in sorted(self.vault.rglob("*"))
            if path.is_file()
        }

    def published_baseline(self) -> dict[str, str]:
        write(self.vault / "Shared" / "keep.md", "kept\n")
        write(self.vault / "Shared" / "edit.md", "vault version\n")
        write(self.vault / "Shared" / "gone.md", "restore me\n")
        first = self.publish()
        self.assertEqual(first.returncode, 0, self.output(first))
        self.assertEqual(self.main_vault(), self.vault_files())
        return self.vault_files()

    def assert_reconciled(self, result, vault_before: dict[str, str], reverted: list[str]) -> None:
        output = self.output(result)
        self.assertEqual(result.returncode, 0, output)
        self.assertEqual(self.remote_head(), self.head())
        # main's vault/ equals exactly what the vault stages, byte for byte.
        self.assertEqual(self.main_vault(), vault_before)
        # Nothing flowed from main into the vault.
        self.assertEqual(self.vault_files(), vault_before)
        line = self.audit_lines()[-1]
        self.assertEqual(line["result_category"], "success")
        self.assertEqual(line["reverted_remote"], reverted)
        for path in reverted:
            self.assertIn(f'reverted "{path}"', result.stdout)
        self.assertRegex(result.stdout, rf"(?m)^summary .*\breverted={len(reverted)}\b")

    def test_file_deleted_on_main_is_restored(self) -> None:
        before = self.published_baseline()
        self.commit_remote_file("Shared/gone.md", "", delete=True)

        result = self.publish()

        self.assert_reconciled(result, before, ["Shared/gone.md"])
        self.assertEqual((self.worktree / "vault" / "Shared" / "gone.md").read_text(), "restore me\n")

    def test_file_edited_on_main_is_reverted(self) -> None:
        before = self.published_baseline()
        self.commit_remote_file("Shared/edit.md", "edited on main\n")

        result = self.publish()

        self.assert_reconciled(result, before, ["Shared/edit.md"])
        self.assertEqual((self.vault / "Shared" / "edit.md").read_text(), "vault version\n")

    def test_file_added_only_on_main_is_removed(self) -> None:
        # Rewritten from the old stop-until-imported test: a vault/ change on main is
        # now fast-forwarded and reverted instead of stopping publish.
        before = self.published_baseline()
        self.commit_remote_file("Shared/remote.md", "from assistant")
        self.commit_remote_file("Shared/private/hidden.md", "denied path pushed to main")

        result = self.publish()

        self.assert_reconciled(result, before, ["Shared/private/hidden.md", "Shared/remote.md"])
        self.assertFalse((self.vault / "Shared" / "remote.md").exists())
        self.assertFalse((self.worktree / "vault" / "Shared" / "remote.md").exists())

    def test_reverted_remote_paths_are_recorded_in_the_audit_line(self) -> None:
        before = self.published_baseline()
        self.commit_remote_file("Shared/edit.md", "edited\n")
        self.commit_remote_file("Shared/gone.md", "", delete=True)
        self.commit_remote_file("Shared/new.md", "added\n")
        self.commit_remote_file("Shared/edit.md", "edited twice\n")
        new_vault_note = "vault moved on\n"
        write(self.vault / "Shared" / "keep.md", new_vault_note)
        before["Shared/keep.md"] = new_vault_note

        result = self.publish()

        self.assert_reconciled(result, before, ["Shared/edit.md", "Shared/gone.md", "Shared/new.md"])
        line = self.audit_lines()[-1]
        self.assertEqual(
            line["files"]["modified"], ["Shared/edit.md", "Shared/keep.md"]
        )
        self.assertEqual(line["files"]["added"], ["Shared/gone.md"])
        self.assertEqual(line["files"]["deleted"], ["Shared/new.md"])
        self.assertEqual(result.stdout.count("reverted "), 3)
        audit_text = self.audit.read_text(encoding="utf-8")
        for body in ("edited twice", "vault moved on", "restore me"):
            self.assertNotIn(body, audit_text)
        self.assertNotIn("edited twice", self.output(result))

    def test_merge_and_transient_paths_on_main_are_reverted(self) -> None:
        before = self.published_baseline()
        review = self.root / "merge-review"
        git(self.root, "clone", str(self.remote), str(review))
        git(review, "config", "user.name", "the assistant for the operator")
        git(review, "config", "user.email", "assistant@invalid")
        write(review / "vault" / "Shared" / "transient.md", "short-lived")
        git(review, "add", "vault")
        git(review, "commit", "-m", "Add transient")
        git(review, "rm", "-q", "vault/Shared/transient.md")
        git(review, "commit", "-m", "Remove transient")
        git(review, "switch", "-c", "side")
        write(review / "vault" / "Shared" / "side.md", "from a side branch")
        git(review, "add", "vault")
        git(review, "commit", "-m", "Side change")
        git(review, "switch", "main")
        write(review / "README.md", "moved on main\n")
        git(review, "add", "README.md")
        git(review, "commit", "-m", "Main change")
        git(review, "merge", "--no-ff", "--no-commit", "side")
        write(review / "vault" / "Shared" / "merge-only.md", "introduced by the merge itself")
        git(review, "add", "vault")
        git(review, "commit", "-m", "Merge side")
        git(review, "push", "origin", "main")

        result = self.publish()

        self.assert_reconciled(
            result, before, ["Shared/merge-only.md", "Shared/side.md", "Shared/transient.md"]
        )
        self.assertEqual((self.worktree / "README.md").read_text(), "moved on main\n")

    def test_every_published_file_deleted_on_main_is_restored(self) -> None:
        before = self.published_baseline()
        review = self.root / "wipe-review"
        git(self.root, "clone", str(self.remote), str(review))
        git(review, "config", "user.name", "the assistant for the operator")
        git(review, "config", "user.email", "assistant@invalid")
        git(review, "rm", "-r", "-q", "vault")
        git(review, "commit", "-m", "Remove the mirror")
        git(review, "push", "origin", "main")

        result = self.publish()

        self.assert_reconciled(result, before, sorted(before))

    def test_publish_root_replaced_on_main_stops(self) -> None:
        self.published_baseline()
        local = self.head()
        review = self.root / "replace-review"
        git(self.root, "clone", str(self.remote), str(review))
        git(review, "config", "user.name", "the assistant for the operator")
        git(review, "config", "user.email", "assistant@invalid")
        git(review, "rm", "-r", "-q", "vault")
        (review / "vault").symlink_to(self.vault)
        git(review, "add", "vault")
        git(review, "commit", "-m", "Point the mirror at the vault")
        git(review, "push", "origin", "main")
        remote = self.remote_head()

        result = self.publish()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("publish root", self.output(result))
        self.assertEqual(self.head(), local)
        self.assertEqual(self.remote_head(), remote)
        self.assertEqual(self.audit_lines()[-1]["result_category"], "publish-root-replaced")
        self.assertTrue((self.worktree / "vault").is_dir())
        self.assertFalse((self.worktree / "vault").is_symlink())

    # Git rules and entry types that main can carry must not keep the restore from landing.

    def test_gitlink_replacing_a_vault_directory_is_reverted(self) -> None:
        before = self.published_baseline()

        def change(review: Path) -> None:
            git(review, "rm", "-r", "-q", "vault/Shared")
            git(review, "update-index", "--add", "--cacheinfo", f"160000,{'1' * 40},vault/Shared")

        self.push_to_main(change)

        result = self.publish()

        self.assert_reconciled(result, before, ["Shared", *sorted(before)])
        self.assert_clean_rerun()

    def test_symlink_replacing_a_vault_directory_is_reverted(self) -> None:
        before = self.published_baseline()
        outside = self.root / "outside"
        write(outside / "canary.md", "canary\n")

        def change(review: Path) -> None:
            git(review, "rm", "-r", "-q", "vault/Shared")
            (review / "vault").mkdir(exist_ok=True)
            (review / "vault" / "Shared").symlink_to(outside)
            git(review, "add", "vault/Shared")

        self.push_to_main(change)

        result = self.publish()

        self.assert_reconciled(result, before, ["Shared", *sorted(before)])
        self.assertEqual(sorted(path.name for path in outside.iterdir()), ["canary.md"])
        self.assert_clean_rerun()

    def test_file_replacing_a_vault_directory_is_reverted(self) -> None:
        before = self.published_baseline()

        def change(review: Path) -> None:
            git(review, "rm", "-r", "-q", "vault/Shared")
            write(review / "vault" / "Shared", "a file where the folder was\n")
            git(review, "add", "vault/Shared")

        self.push_to_main(change)

        result = self.publish()

        self.assert_reconciled(result, before, ["Shared", *sorted(before)])
        self.assert_clean_rerun()

    def test_pushed_gitignore_cannot_hide_a_restored_file(self) -> None:
        before = self.published_baseline()

        def change(review: Path) -> None:
            git(review, "rm", "-q", "vault/Shared/gone.md")
            write(review / ".gitignore", "vault/Shared/gone.md\nvault/Shared/fresh-*.md\n")
            git(review, "add", ".gitignore")

        self.push_to_main(change)
        write(self.vault / "Shared" / "fresh-note.md", "new in the vault\n")
        before["Shared/fresh-note.md"] = "new in the vault\n"

        result = self.publish()

        self.assert_reconciled(result, before, ["Shared/gone.md"])
        self.assert_clean_rerun()
        self.assertEqual(self.main_vault(), before)

    def test_pushed_gitattributes_cannot_rewrite_published_bytes(self) -> None:
        crlf = b"line one\r\nline two\r\n"
        write(self.vault / "Shared" / "crlf.md", crlf)
        before = self.published_baseline()

        def change(review: Path) -> None:
            write(review / ".gitattributes", "vault/** text eol=lf\n")
            git(review, "add", ".gitattributes")

        self.push_to_main(change)
        write(self.vault / "Shared" / "edit.md", "vault edit\r\n")

        result = self.publish()

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertEqual(self.remote_head(), self.head())
        published = self.main_vault_bytes()
        self.assertEqual(
            published,
            {path: ("100644", (self.vault / path).read_bytes()) for path in before},
        )
        self.assertEqual(published["Shared/crlf.md"][1], crlf)
        self.assert_clean_rerun()

    def test_failed_run_after_a_link_on_main_leaves_a_clean_worktree(self) -> None:
        before = self.published_baseline()
        outside = self.root / "outside.md"
        write(outside, "outside\n")

        def change(review: Path) -> None:
            (review / "vault" / "Shared" / "link.md").symlink_to(outside)
            git(review, "add", "vault/Shared/link.md")

        self.push_to_main(change)

        failed = self.publish(env={"STUB_GITLEAKS_MODE": "error"})

        self.assertEqual(failed.returncode, 2, self.output(failed))
        # The failed run fast-forwarded, so it is the one that reports the reverted path.
        self.assertEqual(self.audit_lines()[-1]["result_category"], "scanner-error")
        self.assertEqual(self.audit_lines()[-1]["reverted_remote"], ["Shared/link.md"])
        self.assertEqual(
            git(self.worktree, "status", "--porcelain=v1", "--untracked-files=all", "--", "vault").stdout,
            "",
        )
        result = self.publish()
        self.assert_reconciled(result, before, [])
        self.assertEqual(outside.read_text(), "outside\n")

    def test_reverted_links_and_modes_are_counted(self) -> None:
        before = self.published_baseline()

        def change(review: Path) -> None:
            (review / "vault" / "Shared" / "link.md").symlink_to("keep.md")
            (review / "vault" / "Shared" / "edit.md").chmod(0o755)
            git(review, "add", "vault")

        self.push_to_main(change)

        result = self.publish()

        self.assert_reconciled(result, before, ["Shared/edit.md", "Shared/link.md"])
        line = self.audit_lines()[-1]
        self.assertEqual(line["files"]["modified"], ["Shared/edit.md"])
        self.assertEqual(line["files"]["deleted"], ["Shared/link.md"])
        self.assertEqual(line["counts"], {"added": 0, "modified": 1, "deleted": 1})

    def test_index_that_differs_from_the_vault_is_never_committed(self) -> None:
        write(self.vault / "Shared" / "note.md", "vault text\n")
        wrappers = self.root / "tamper-wrappers"
        write(wrappers / "git", TAMPER_ADD_WRAPPER)
        (wrappers / "git").chmod(0o755)
        local, remote = self.head(), self.remote_head()

        result = self.publish(env={"PATH": f"{wrappers}:{os.environ['PATH']}"})

        self.assertEqual(result.returncode, 2, self.output(result))
        self.assertEqual(self.audit_lines()[-1]["result_category"], "publish-verify-failed")
        self.assertEqual(self.head(), local)
        self.assertEqual(self.remote_head(), remote)
        self.assertEqual(
            git(self.worktree, "status", "--porcelain=v1", "--untracked-files=all", "--", "vault").stdout,
            "",
        )
        retried = self.publish()
        self.assertEqual(retried.returncode, 0, self.output(retried))
        self.assertEqual(self.main_vault(), {"Shared/note.md": "vault text\n"})

    # A push that loses a race with another push to main is rebuilt, not a hard stop.

    def test_push_race_with_a_concurrent_main_commit_heals_on_the_next_run(self) -> None:
        before = self.published_baseline()
        race = self.root / "race-clone"
        git(self.root, "clone", str(self.remote), str(race))
        git(race, "config", "user.name", "the assistant for the operator")
        git(race, "config", "user.email", "assistant@invalid")
        write(race / "README.md", "raced onto main\n")
        git(race, "commit", "-q", "-am", "Race the publisher")
        write(self.vault / "Shared" / "edit.md", "vault edited\n")
        before["Shared/edit.md"] = "vault edited\n"
        wrappers = self.root / "race-wrappers"
        write(wrappers / "git", RACE_PUSH_WRAPPER)
        (wrappers / "git").chmod(0o755)

        lost = self.publish(
            env={
                "PATH": f"{wrappers}:{os.environ['PATH']}",
                "BRIDGE_RACE_CLONE": str(race),
                "BRIDGE_RACE_SEEN": str(self.root / "race-seen"),
            }
        )

        self.assertEqual(lost.returncode, 2, self.output(lost))
        self.assertEqual(self.audit_lines()[-1]["result_category"], "push-failed")
        unpushed = self.head()
        raced = self.remote_head()
        self.assertEqual(raced, self.head(race))

        result = self.publish()

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertEqual(self.remote_head(), self.head())
        self.assertEqual(git(self.worktree, "rev-parse", "HEAD^").stdout.strip(), raced)
        self.assertEqual(self.main_vault(), before)
        self.assertEqual((self.worktree / "README.md").read_text(), "raced onto main\n")
        line = self.audit_lines()[-1]
        self.assertEqual(line["result_category"], "success")
        self.assertEqual(line["dropped_unpushed"], unpushed)
        self.assertEqual(json.loads(self.push_state.read_text())["status"], "clear")

    def test_pending_publish_that_landed_is_settled_when_main_moves_on(self) -> None:
        self.published_baseline()
        landed = self.head()
        parent = git(self.worktree, "rev-parse", f"{landed}^").stdout.strip()
        # The push landed but its check failed, and main then moved on top of it.
        write(
            self.push_state,
            json.dumps({"version": 1, "status": "pending", "commit": landed, "remote_parent": parent}),
        )
        self.commit_remote_path("README.md", "moved on\n")

        first = self.publish()

        self.assertEqual(first.returncode, 0, self.output(first))
        self.assertEqual(json.loads(self.push_state.read_text())["status"], "clear")
        self.assertIsNone(self.audit_lines()[-1]["dropped_unpushed"])
        self.assert_clean_rerun()

    def test_unpushed_commit_outside_vault_is_never_dropped(self) -> None:
        parent = self.head()
        write(self.worktree / "LOCAL.md", "unreviewed")
        git(self.worktree, "add", "LOCAL.md")
        git(self.worktree, "commit", "-m", "Local unrelated commit")
        local = self.head()
        write(
            self.push_state,
            json.dumps({"version": 1, "status": "pending", "commit": local, "remote_parent": parent}),
        )
        remote = self.commit_remote_path("README.md", "remote moved\n")

        result = self.publish()

        self.assertEqual(result.returncode, 2, self.output(result))
        self.assertEqual(self.audit_lines()[-1]["result_category"], "local-ahead-unverified")
        self.assertEqual(self.head(), local)
        self.assertEqual(self.remote_head(), remote)

    def test_diverged_history_after_force_push_still_stops(self) -> None:
        self.published_baseline()
        local = self.head()
        review = self.root / "force-review"
        git(self.root, "clone", str(self.remote), str(review))
        git(review, "config", "user.name", "the assistant for the operator")
        git(review, "config", "user.email", "assistant@invalid")
        git(review, "reset", "--hard", "-q", "HEAD^")
        write(review / "vault" / "Shared" / "rewritten.md", "history rewritten")
        git(review, "add", "vault")
        git(review, "commit", "-m", "Rewrite history")
        git(review, "push", "--force", "origin", "main")
        remote = self.remote_head()

        result = self.publish()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("diverged", self.output(result).lower())
        self.assertEqual(self.head(), local)
        self.assertEqual(self.remote_head(), remote)
        line = self.audit_lines()[-1]
        self.assertEqual(line["result_category"], "remote-history-changed")
        self.assertEqual(line["reverted_remote"], [])
        self.assertFalse((self.worktree / "vault" / "Shared" / "rewritten.md").exists())

    def test_pushed_gitleaksignore_cannot_suppress_the_scanner(self) -> None:
        self.commit_remote_path(".gitleaksignore", "vault/Shared/secret.md:test-credential:1\n")
        write(self.gitleaks, CWD_IGNORE_GITLEAKS)
        self.gitleaks.chmod(0o755)
        write(self.vault / "Shared" / "secret.md", self.secret)
        before = self.remote_head()

        # systemd runs publish with the worktree as its working directory.
        result = run(self.publish_args(), cwd=self.worktree, env=self.env)

        self.assertNotEqual(result.returncode, 0, self.output(result))
        self.assertIn("secret detected", self.output(result))
        self.assertNotIn(self.secret, self.output(result))
        self.assertEqual(self.remote_head(), before)
        self.assertNotIn("Shared/secret.md", self.main_vault())

    # Policy location decides whether a policy change on main may be fast-forwarded.

    def deployed_policy(self, text: str | None = None) -> Path:
        deployed = self.root / "etc" / "bridge-policy.toml"
        write(deployed, text if text is not None else policy_text())
        deployed.chmod(0o644)
        return deployed

    def publish_with_policy(self, policy: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        args = self.publish_args(*extra)
        args[args.index("--policy") + 1] = str(policy)
        return run(args, cwd=self.root, env=self.env)

    def test_remote_policy_change_stops_publish_with_worktree_policy(self) -> None:
        # Rewritten from the old policy stop test: the stop now applies only when the
        # policy is read from inside the worktree, where it would follow main.
        before = self.head()
        self.commit_remote_path("bridge-policy.toml", policy_text() + "# widened\n")
        write(self.vault / "Shared" / "note.md", "safe")

        result = self.publish()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("policy", self.output(result).lower())
        self.assertEqual(self.head(), before)
        self.assertEqual(self.audit_lines()[-1]["result_category"], "remote-history-changed")

    def assert_policy_change_stopped(self, result, local: str, trusted: str) -> None:
        """A stop that leaves the policy the sibling jobs load untouched.

        bridge-apply, bridge-import and bridge-restore read the worktree's
        bridge-policy.toml pinned to local main, so neither may move.
        """
        self.assertEqual(result.returncode, 2, self.output(result))
        self.assertIn("policy-drift", result.stdout)
        self.assertEqual(self.head(), local)
        self.assertEqual((self.worktree / "bridge-policy.toml").read_text(), trusted)
        self.assertEqual(git(self.worktree, "show", "HEAD:bridge-policy.toml").stdout, trusted)
        line = self.audit_lines()[-1]
        self.assertEqual(line["result_category"], "policy-drift")
        self.assertIs(line["policy_drift"], True)
        self.assertEqual(line["policy_source"], "deployed")
        self.assertEqual(line["reverted_remote"], [])

    def test_policy_change_on_main_stops_with_a_deployed_policy(self) -> None:
        # Rewritten from the drift-continues test after review: fast-forwarding a policy
        # the owner has not deployed would hand it to every job that reads the worktree
        # copy, so a policy change on main now stops unless it matches the deployed bytes.
        deployed = self.deployed_policy()
        local = self.head()
        widened = policy_text().replace('roots = ["Shared", "Single.md"]', 'roots = ["Shared", "Single.md", "Private"]')
        self.assertNotEqual(widened, policy_text())
        self.commit_remote_path("bridge-policy.toml", widened)
        write(self.vault / "Shared" / "note.md", "safe")
        write(self.vault / "Private" / "plan.md", "only the pushed policy allows this")

        result = self.publish_with_policy(deployed)

        self.assert_policy_change_stopped(result, local, policy_text())
        self.assertNotIn("Shared/note.md", self.main_vault())

    def test_policy_drift_without_a_policy_change_on_main_continues(self) -> None:
        # The deployed policy governs and drift is recorded when main's copy differs but
        # the fast-forward leaves the worktree policy as it was.
        narrowed = policy_text().replace('roots = ["Shared", "Single.md"]', 'roots = ["Shared"]')
        deployed = self.deployed_policy(narrowed)
        advance = self.commit_remote_path("README.md", "docs changed on main\n")
        write(self.vault / "Shared" / "note.md", "safe")
        write(self.vault / "Single.md", "only the repository policy allows this")

        result = self.publish_with_policy(deployed)

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertEqual(git(self.worktree, "rev-parse", "HEAD^").stdout.strip(), advance)
        self.assertEqual(self.remote_head(), self.head())
        self.assertEqual((self.worktree / "bridge-policy.toml").read_text(), policy_text())
        self.assertEqual(self.main_vault(), {"Shared/note.md": "safe"})
        self.assertIn("policy-drift", result.stdout)
        line = self.audit_lines()[-1]
        self.assertEqual(line["result_category"], "success")
        self.assertIs(line["policy_drift"], True)
        self.assertEqual(line["policy_source"], "deployed")

    def test_identical_deployed_policy_records_no_drift(self) -> None:
        amended = policy_text() + "# reviewed and deployed\n"
        deployed = self.deployed_policy(amended)
        self.commit_remote_path("bridge-policy.toml", amended)
        write(self.vault / "Shared" / "note.md", "safe")

        result = self.publish_with_policy(deployed)

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertEqual(self.remote_head(), self.head())
        self.assertEqual((self.worktree / "bridge-policy.toml").read_text(), amended)
        self.assertNotIn("policy-drift", result.stdout)
        line = self.audit_lines()[-1]
        self.assertIs(line["policy_drift"], False)
        self.assertEqual(line["policy_source"], "deployed")

    def test_policy_change_on_main_resumes_once_deployed(self) -> None:
        # Rewritten from the drift-persists test: the stop lasts until root deploys the
        # same bytes, then the next run fast-forwards without drift.
        deployed = self.deployed_policy()
        local = self.head()
        changed = policy_text() + "# changed on main\n"
        self.commit_remote_path("bridge-policy.toml", changed)
        write(self.vault / "Shared" / "note.md", "first")
        first = self.publish_with_policy(deployed)
        self.assert_policy_change_stopped(first, local, policy_text())

        write(deployed, changed)
        second = self.publish_with_policy(deployed)

        self.assertEqual(second.returncode, 0, self.output(second))
        self.assertEqual(self.remote_head(), self.head())
        self.assertEqual((self.worktree / "bridge-policy.toml").read_text(), changed)
        self.assertIs(self.audit_lines()[-1]["policy_drift"], False)
        self.assertEqual(self.main_vault(), {"Shared/note.md": "first"})

    def test_deleted_repository_policy_stops_as_drift(self) -> None:
        # Rewritten from the deletion-counts-as-drift test: deleting the policy on main
        # is a policy change that differs from the deployed bytes, so it stops.
        deployed = self.deployed_policy()
        local = self.head()

        def change(review: Path) -> None:
            git(review, "rm", "-q", "bridge-policy.toml")

        self.push_to_main(change, "Remove policy")
        write(self.vault / "Shared" / "note.md", "safe")

        result = self.publish_with_policy(deployed)

        self.assert_policy_change_stopped(result, local, policy_text())

    def test_untrusted_deployed_policy_stops_publish(self) -> None:
        deployed = self.deployed_policy()
        link = deployed.with_name("linked-policy.toml")
        link.symlink_to(deployed)
        write(self.vault / "Shared" / "note.md", "safe")
        before = self.remote_head()

        for candidate, prepare in ((link, None), (deployed, 0o664)):
            with self.subTest(candidate=candidate.name, mode=prepare):
                if prepare is not None:
                    deployed.chmod(prepare)
                result = self.publish_with_policy(candidate)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("deployed bridge policy", self.output(result))
                self.assertEqual(self.remote_head(), before)
                self.assertEqual(self.audit_lines()[-1]["result_category"], "policy-untrusted")

    def test_diverged_remote_stops_publish(self) -> None:
        write(self.worktree / "LOCAL.md", "unreviewed")
        git(self.worktree, "add", "LOCAL.md")
        git(self.worktree, "commit", "-m", "Local unrelated commit")
        local = self.head()
        remote = self.commit_remote_path("README.md", "remote moved\n")
        write(self.vault / "Shared" / "note.md", "safe")

        result = self.publish()

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("diverged", self.output(result).lower())
        self.assertEqual(self.head(), local)
        self.assertEqual(self.remote_head(), remote)


if __name__ == "__main__":
    import unittest

    unittest.main()
