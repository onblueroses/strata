from __future__ import annotations

import contextlib
import hashlib
import importlib.machinery
import importlib.util
import io
import json
import os
import stat
import sys
import threading
from contextlib import redirect_stderr, redirect_stdout
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from urllib.parse import urlsplit

from .helpers import APPLY, TOOLS, BridgeCase, git, policy_text, run, write

AUTHOR = "assistant-account"
BASE_NOTE = "---\ntitle: Before\n---\nbefore\n"
INCOMING_NOTE = "---\ntitle: After\n---\nafter\n"


class FakeGitHubState:
    def __init__(self) -> None:
        self.pulls: list[dict[str, object]] = []
        # Heads pushed after the listing: a single-pull read already shows them.
        self.moved_heads: dict[int, str] = {}
        self.labels: dict[int, list[dict[str, str]]] = {}
        self.posted_comments: list[tuple[int, str]] = []
        self.state_changes: list[tuple[int, dict[str, object]]] = []
        self.authorizations: list[str] = []
        self.comment_failures = 0
        self.close_denied = False
        self.close_attempts = 0

    def pull(self, number: int) -> dict[str, object] | None:
        document = next(
            (pull for pull in self.pulls if pull.get("number") == number), None
        )
        if document is not None and number in self.moved_heads:
            document = {**document, "head": {"sha": self.moved_heads[number]}}
        return document


class FakeGitHubHandler(BaseHTTPRequestHandler):
    server_version = "FakeGitHub/1"

    @property
    def state(self) -> FakeGitHubState:
        return self.server.state  # type: ignore[attr-defined, no-any-return]

    def log_message(self, _format: str, *_args: object) -> None:
        pass

    def _record_auth(self) -> None:
        self.state.authorizations.append(self.headers.get("Authorization", ""))

    def _read_json(self) -> dict[str, object]:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length)
        document = json.loads(raw or b"{}")
        if not isinstance(document, dict):
            raise ValueError("request body must be an object")
        return document

    def _send_json(self, document: object, status: int = 200) -> None:
        encoded = json.dumps(document).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _suffix(self) -> str:
        path = urlsplit(self.path).path
        prefix = "/repos/test-owner/test-repo"
        if not path.startswith(prefix):
            return ""
        return path[len(prefix) :]

    @staticmethod
    def _number(suffix: str, prefix: str, ending: str = "") -> int | None:
        if not suffix.startswith(prefix) or not suffix.endswith(ending):
            return None
        raw = suffix[len(prefix) :]
        if ending:
            raw = raw[: -len(ending)]
        return int(raw) if raw.isdigit() else None

    def do_GET(self) -> None:
        self._record_auth()
        suffix = self._suffix()
        if suffix == "/pulls":
            self._send_json(self.state.pulls)
            return
        number = self._number(suffix, "/pulls/")
        if number is not None:
            document = self.state.pull(number)
            self._send_json(document or {"message": "not found"}, 200 if document else 404)
            return
        number = self._number(suffix, "/issues/")
        if number is not None:
            self._send_json({"labels": self.state.labels.get(number, [])})
            return
        self._send_json({"message": "not found"}, 404)

    def do_POST(self) -> None:
        self._record_auth()
        suffix = self._suffix()
        number = self._number(suffix, "/issues/", "/comments")
        if number is None:
            self._send_json({"message": "not found"}, 404)
            return
        if self.state.comment_failures:
            self.state.comment_failures -= 1
            self._send_json({"message": "synthetic comment failure"}, 500)
            return
        payload = self._read_json()
        body = payload.get("body")
        if not isinstance(body, str):
            self._send_json({"message": "invalid body"}, 422)
            return
        self.state.posted_comments.append((number, body))
        self._send_json({"id": len(self.state.posted_comments)}, 201)

    def do_PATCH(self) -> None:
        self._record_auth()
        suffix = self._suffix()
        number = self._number(suffix, "/pulls/")
        if number is None:
            self._send_json({"message": "not found"}, 404)
            return
        self.state.close_attempts += 1
        if self.state.close_denied:
            self._send_json({"message": "forbidden"}, 403)
            return
        payload = self._read_json()
        self.state.state_changes.append((number, payload))
        self._send_json({"number": number, **payload})


class FakeGitHubClient:
    """Socket-free equivalent used only when the test sandbox denies loopback."""

    def __init__(self, state: FakeGitHubState, token: str, api_error):
        self.state = state
        self.token = token
        self.api_error = api_error

    def _auth(self) -> None:
        self.state.authorizations.append(f"Bearer {self.token}")

    def pulls(self):
        self._auth()
        return self.state.pulls

    def pull(self, number: int):
        self._auth()
        return self.state.pull(number)

    def issue(self, number: int):
        self._auth()
        return {"labels": self.state.labels.get(number, [])}

    def comment(self, number: int, body: str) -> None:
        self._auth()
        if self.state.comment_failures:
            self.state.comment_failures -= 1
            raise self.api_error(
                "api-http", "synthetic comment failure", status=500
            )
        self.state.posted_comments.append((number, body))

    def close(self, number: int) -> None:
        self._auth()
        self.state.close_attempts += 1
        if self.state.close_denied:
            raise self.api_error("api-http", "synthetic close denial", status=403)
        self.state.state_changes.append((number, {"state": "closed"}))


def load_apply_module():
    tools_text = str(TOOLS)
    if tools_text not in sys.path:
        sys.path.insert(0, tools_text)
    loader = importlib.machinery.SourceFileLoader(
        "bridge_apply_test", str(APPLY)
    )
    spec = importlib.util.spec_from_loader("bridge_apply_test", loader)
    if spec is None:
        raise RuntimeError("cannot load bridge-apply")
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class ApplyTests(BridgeCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.apply_module = load_apply_module()
        from bridge_common import BridgeError

        cls.BridgeError = BridgeError

    def setUp(self) -> None:
        super().setUp()
        self.set_policy(inbound=True)
        write(self.worktree / "vault" / "Shared" / "note.md", BASE_NOTE)
        git(self.worktree, "add", "vault/Shared/note.md")
        git(self.worktree, "commit", "-m", "Add fixture note")
        git(self.worktree, "push", "origin", "main")
        write(self.vault / "Shared" / "note.md", BASE_NOTE)

        self.token = "github_test_token_keep_secret"
        self.token_file = self.root / "github-token"
        write(self.token_file, self.token + "\n")
        self.token_file.chmod(0o600)

        self.github = FakeGitHubState()
        try:
            self.server = ThreadingHTTPServer(
                ("127.0.0.1", 0), FakeGitHubHandler
            )
        except PermissionError:
            self.server = None
            self.server_thread = None
        else:
            self.server.state = self.github  # type: ignore[attr-defined]
            self.server_thread = threading.Thread(
                target=self.server.serve_forever, daemon=True
            )
            self.server_thread.start()

    def tearDown(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            assert self.server_thread is not None
            self.server_thread.join(timeout=5)
        super().tearDown()

    @property
    def api_url(self) -> str:
        if self.server is None:
            return "http://127.0.0.1"
        host, port = self.server.server_address
        return f"http://{host}:{port}"

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
        return self.root / "status" / "apply-status.json"

    def status(self) -> dict[str, object]:
        return json.loads(self.status_path.read_text(encoding="utf-8"))

    def apply_args(
        self,
        *extra: str,
        run_id: str = "apply-test",
        auto_apply_roots: str | None = "Shared",
    ) -> list[str]:
        args = [
            sys.executable,
            str(APPLY),
            "--vault",
            str(self.vault),
            "--worktree",
            str(self.worktree),
            "--remote-url",
            str(self.remote),
            "--policy",
            str(self.policy),
            "--gitleaks",
            str(self.gitleaks),
            "--gitleaks-config",
            str(self.gitleaks_config),
            "--audit-log",
            str(self.audit),
            "--backup-dir",
            str(self.backups),
            "--lock-file",
            str(self.lock_file),
            "--visibility-attestation",
            str(self.visibility_attestation),
            "--token-file",
            str(self.token_file),
            "--repo",
            "test-owner/test-repo",
            "--author",
            AUTHOR,
            "--api-url",
            self.api_url,
            "--run-id",
            run_id,
        ]
        if auto_apply_roots is not None:
            args.extend(["--auto-apply-roots", auto_apply_roots])
        args.extend(extra)
        return args

    def apply(
        self,
        *extra: str,
        env: dict[str, str] | None = None,
        auto_apply_roots: str | None = "Shared",
        in_process: bool = False,
        patches: tuple = (),
    ):
        merged = self.env
        if env:
            merged.update(env)
        argv = self.apply_args(*extra, auto_apply_roots=auto_apply_roots)
        if self.server is not None and not in_process:
            return run(argv, cwd=self.root, env=merged)
        stdout = io.StringIO()
        stderr = io.StringIO()
        client = FakeGitHubClient(
            self.github, self.token, self.apply_module.ApiError
        )
        old_cwd = Path.cwd()
        try:
            os.chdir(self.root)
            with (
                mock.patch.dict(os.environ, merged),
                (
                    mock.patch.object(
                        self.apply_module,
                        "GitHubAPI",
                        return_value=client,
                    )
                    if self.server is None
                    else contextlib.nullcontext()
                ),
                contextlib.ExitStack() as stack,
                redirect_stdout(stdout),
                redirect_stderr(stderr),
            ):
                for patch in patches:
                    stack.enter_context(patch)
                returncode = self.apply_module.main(argv[2:])
        finally:
            os.chdir(old_cwd)
        return SimpleNamespace(
            returncode=returncode,
            stdout=stdout.getvalue(),
            stderr=stderr.getvalue(),
        )

    def create_pr(
        self,
        changes: dict[str, str | None],
        *,
        number: int = 1,
        author: str = AUTHOR,
        body: str = "",
        symlinks: dict[str, str] | None = None,
    ) -> str:
        checkout = self.root / f"pr-{number}"
        git(self.root, "clone", str(self.remote), str(checkout))
        git(checkout, "config", "user.name", "the assistant for the operator")
        git(checkout, "config", "user.email", "assistant@invalid")
        git(checkout, "switch", "-c", f"pr-{number}")
        for relative, content in changes.items():
            if content is None:
                git(checkout, "rm", "--", relative)
            else:
                write(checkout / relative, content)
                git(checkout, "add", "--", relative)
        for relative, target in (symlinks or {}).items():
            os.symlink(target, checkout / relative)
            git(checkout, "add", "--", relative)
        git(checkout, "commit", "-m", f"PR {number} fixture")
        sha = git(checkout, "rev-parse", "HEAD").stdout.strip()
        git(checkout, "push", "origin", f"HEAD:refs/pull/{number}/head")
        self.github.pulls.append(
            {
                "number": number,
                "state": "open",
                "user": {"login": author},
                "base": {"ref": "main"},
                "head": {"sha": sha},
                "body": body,
            }
        )
        return sha

    def assert_no_remote_effects(self) -> None:
        self.assertEqual(self.github.posted_comments, [])
        self.assertEqual(self.github.state_changes, [])

    def assert_refused(
        self,
        changes: dict[str, str | None],
        category: str,
        *,
        env: dict[str, str] | None = None,
    ) -> None:
        before = (self.vault / "Shared" / "note.md").read_bytes()
        self.create_pr(changes)

        result = self.apply(env=env)

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertIn(f"refused {category}", result.stdout)
        self.assertEqual((self.vault / "Shared" / "note.md").read_bytes(), before)
        self.assertEqual(len(self.github.posted_comments), 1)
        self.assertEqual(self.github.posted_comments[0][0], 1)
        self.assertIn("refused", self.github.posted_comments[0][1].lower())
        self.assertEqual(self.github.state_changes, [])
        self.assertFalse(self.backups.exists())
        self.assertEqual(self.audit_lines()[-1]["result_category"], category)

    def test_pr_is_applied_backed_up_audited_commented_and_closed(self) -> None:
        sha = self.create_pr({"vault/Shared/note.md": INCOMING_NOTE})

        result = self.apply()

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertIn("PR #1 applied", result.stdout)
        self.assertEqual(
            (self.vault / "Shared" / "note.md").read_text(encoding="utf-8"),
            INCOMING_NOTE,
        )
        manifest = json.loads(
            (self.backups / "apply-test" / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(manifest["run_id"], "apply-test")
        self.assertEqual(manifest["files"][0]["path"], "Shared/note.md")
        self.assertEqual(
            (self.backups / "apply-test" / "files" / "Shared" / "note.md").read_text(
                encoding="utf-8"
            ),
            BASE_NOTE,
        )
        audit = self.audit_lines()
        self.assertEqual(len(audit), 1)
        self.assertEqual(audit[0]["direction"], "apply")
        self.assertEqual(audit[0]["result_category"], "success")
        self.assertEqual(audit[0]["pr_number"], 1)
        self.assertEqual(audit[0]["head_sha"], sha)
        self.assertEqual(audit[0]["counts"]["modified"], 1)
        self.assertEqual(len(self.github.posted_comments), 1)
        self.assertIn("applied to the vault (run apply-test, 1 files)", self.github.posted_comments[0][1])
        self.assertIn("(bridge-apply, ", self.github.posted_comments[0][1])
        self.assertEqual(self.github.state_changes, [(1, {"state": "closed"})])
        self.assertTrue(self.github.authorizations)
        self.assertTrue(
            all(value == f"Bearer {self.token}" for value in self.github.authorizations)
        )
        self.assertNotIn(self.token, self.output(result))
        self.assertNotIn(self.token, self.audit.read_text(encoding="utf-8"))

    def test_disabled_inbound_policy_is_a_strict_noop(self) -> None:
        self.create_pr({"vault/Shared/note.md": INCOMING_NOTE})
        self.set_policy(inbound=False)

        result = self.apply()

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertEqual(result.stdout, "inbound disabled\n")
        self.assertEqual((self.vault / "Shared" / "note.md").read_text(), BASE_NOTE)
        self.assertFalse(self.audit.exists())
        self.assertEqual(self.github.authorizations, [])
        self.assert_no_remote_effects()

    def test_head_pushed_during_inspection_is_refused_before_write(self) -> None:
        self.create_pr({"vault/Shared/note.md": INCOMING_NOTE})
        self.github.moved_heads[1] = "f" * 40

        result = self.apply()

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertIn("PR #1 refused head-changed", result.stdout)
        self.assertEqual((self.vault / "Shared" / "note.md").read_text(), BASE_NOTE)
        self.assertFalse(self.backups.exists())
        self.assertEqual(self.audit_lines()[-1]["result_category"], "head-changed")
        self.assertEqual(self.github.state_changes, [])
        self.assertIn("head changed before apply", self.github.posted_comments[0][1])

    def test_pr_by_other_author_is_ignored(self) -> None:
        self.create_pr(
            {"vault/Shared/note.md": INCOMING_NOTE}, author="someone-else"
        )

        result = self.apply()

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertEqual(result.stdout, "")
        self.assertEqual((self.vault / "Shared" / "note.md").read_text(), BASE_NOTE)
        self.assertFalse(self.audit.exists())
        self.assert_no_remote_effects()

    def test_change_outside_vault_is_refused(self) -> None:
        self.assert_refused({"README.md": "untrusted tool-plane change\n"}, "outside-vault")

    def test_symlink_in_one_pull_request_does_not_starve_the_others(self) -> None:
        # A special file is refused like any other bad change: one comment, no abort,
        # and the next PR in the same run is still applied.
        self.create_pr({}, symlinks={"vault/Shared/link.md": "note.md"})
        self.create_pr({"vault/Shared/other.md": "fine\n"}, number=2)

        result = self.apply()

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertIn("PR #1 refused remote-special-file", result.stdout)
        self.assertIn("PR #2 applied", result.stdout)
        self.assertEqual((self.vault / "Shared" / "other.md").read_text(), "fine\n")
        self.assertFalse((self.vault / "Shared" / "link.md").exists())
        again = self.apply()
        self.assertEqual(again.returncode, 0, self.output(again))
        self.assertIn("PR #1 refused-before remote-special-file", again.stdout)
        self.assertEqual(sum(1 for number, _ in self.github.posted_comments if number == 1), 1)

    def test_deletion_is_refused(self) -> None:
        self.assert_refused({"vault/Shared/note.md": None}, "deletion")

    def test_policy_denied_path_is_refused(self) -> None:
        self.assert_refused(
            {"vault/Shared/private/hidden.md": "private\n"}, "policy-denied"
        )
        self.assertFalse((self.vault / "Shared" / "private" / "hidden.md").exists())

    def test_oversized_blob_is_refused_by_policy(self) -> None:
        self.assert_refused(
            {"vault/Shared/large.md": "x" * 1025}, "policy-denied"
        )

    def test_invalid_frontmatter_is_refused(self) -> None:
        self.assert_refused(
            {"vault/Shared/note.md": "---\ntitle without colon\n---\nbody\n"},
            "frontmatter-invalid",
        )

    def test_scanner_hit_is_refused_without_exposing_secret(self) -> None:
        self.assert_refused(
            {"vault/Shared/note.md": f"---\ntitle: Secret\n---\n{self.secret}\n"},
            "secret-detected",
            env={"STUB_GITLEAKS_MODE": "hit"},
        )
        posted = self.github.posted_comments[0][1]
        self.assertNotIn(self.secret, posted)
        self.assertNotIn(self.secret, self.audit.read_text(encoding="utf-8"))

    def test_scanner_error_is_refused_without_writing(self) -> None:
        self.assert_refused(
            {"vault/Shared/note.md": INCOMING_NOTE},
            "scanner-error",
            env={"STUB_GITLEAKS_MODE": "error"},
        )

    def test_vault_edit_conflict_is_refused(self) -> None:
        self.create_pr({"vault/Shared/note.md": INCOMING_NOTE})
        write(
            self.vault / "Shared" / "note.md",
            "---\ntitle: Local edit\n---\nlocal\n",
        )

        result = self.apply()

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertIn("PR #1 refused conflict", result.stdout)
        self.assertIn(
            "conflict: Shared/note.md changed in the vault since the PR was opened",
            self.github.posted_comments[0][1],
        )
        self.assertEqual(
            (self.vault / "Shared" / "note.md").read_text(),
            "---\ntitle: Local edit\n---\nlocal\n",
        )
        self.assertEqual(self.github.state_changes, [])

    def replace_head(self, changes: dict[str, str | None], number: int = 1) -> str:
        checkout = self.root / f"pr-{number}"
        git(checkout, "reset", "--hard", "origin/main")
        for relative, content in changes.items():
            write(checkout / relative, content)
            git(checkout, "add", "--", relative)
        git(checkout, "commit", "-m", f"PR {number} new head")
        sha = git(checkout, "rev-parse", "HEAD").stdout.strip()
        git(checkout, "push", "--force", "origin", f"HEAD:refs/pull/{number}/head")
        for pull in self.github.pulls:
            if pull["number"] == number:
                pull["head"] = {"sha": sha}
        return sha

    def test_refused_head_is_reported_once_and_not_rescanned(self) -> None:
        self.create_pr({"vault/Shared/note.md": "---\ntitle without colon\n---\nbody\n"})

        first = self.apply()
        scans = self.gitleaks_log.read_text().count("\n") if self.gitleaks_log.exists() else 0
        second = self.apply()
        third = self.apply()

        self.assertIn("PR #1 refused frontmatter-invalid", first.stdout)
        self.assertIn("PR #1 refused-before frontmatter-invalid", second.stdout)
        self.assertIn("PR #1 refused-before frontmatter-invalid", third.stdout)
        self.assertEqual(len(self.github.posted_comments), 1)
        refusals = [r for r in self.audit_lines() if r["result_category"] == "frontmatter-invalid"]
        self.assertEqual(len(refusals), 1)
        after = self.gitleaks_log.read_text().count("\n") if self.gitleaks_log.exists() else 0
        self.assertEqual(after, scans)

    def test_secret_finding_is_rechecked_but_reported_once(self) -> None:
        # A finding depends on the scanner and its config, which the rules digest does
        # not cover: a scanner fix must release the head without a new push.
        self.create_pr({"vault/Shared/note.md": INCOMING_NOTE})

        first = self.apply(env={"STUB_GITLEAKS_MODE": "hit"})
        second = self.apply(env={"STUB_GITLEAKS_MODE": "hit"})
        third = self.apply()

        self.assertIn("PR #1 refused secret-detected", first.stdout)
        self.assertIn("PR #1 refused secret-detected already-reported", second.stdout)
        self.assertIn("PR #1 applied success", third.stdout, self.output(third))
        self.assertEqual(
            len([b for _, b in self.github.posted_comments if "secret scanner finding" in b]), 1
        )

    def test_inbox_capture_with_a_secret_is_refused(self) -> None:
        self.use_inbox_policy()
        self.create_pr({"vault/5 Inbox/capture.md": INCOMING_NOTE})

        result = self.apply(auto_apply_roots=None, env={"STUB_GITLEAKS_MODE": "hit"})

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertIn("PR #1 refused secret-detected", result.stdout)
        self.assertFalse((self.vault / "5 Inbox" / "capture.md").exists())

    def test_vault_dependent_policy_denial_is_rechecked(self) -> None:
        # The policy walks the vault: a file where a folder is needed denies the path
        # until the file is gone, and the head must then apply without a new push.
        write(self.vault / "Shared" / "sub", "blocking file\n")
        self.create_pr({"vault/Shared/sub/new.md": INCOMING_NOTE})

        first = self.apply()
        second = self.apply()
        (self.vault / "Shared" / "sub").unlink()
        third = self.apply()

        self.assertIn("PR #1 refused policy-denied", first.stdout)
        self.assertIn("PR #1 refused policy-denied already-reported", second.stdout)
        self.assertIn("PR #1 applied success", third.stdout, self.output(third))
        self.assertEqual(len([b for _, b in self.github.posted_comments if "refused" in b]), 1)

    def test_new_head_after_refusal_is_inspected_again(self) -> None:
        self.create_pr({"vault/Shared/note.md": None})
        first = self.apply()
        self.replace_head({"vault/Shared/note.md": INCOMING_NOTE})

        second = self.apply()

        self.assertIn("PR #1 refused deletion", first.stdout)
        self.assertIn("PR #1 applied success", second.stdout, self.output(second))
        self.assertEqual((self.vault / "Shared" / "note.md").read_text(), INCOMING_NOTE)

    def test_conflict_is_reported_once_but_rechecked_until_it_clears(self) -> None:
        self.create_pr({"vault/Shared/note.md": INCOMING_NOTE})
        write(self.vault / "Shared" / "note.md", "---\ntitle: Local edit\n---\nlocal\n")

        first = self.apply()
        second = self.apply()
        write(self.vault / "Shared" / "note.md", BASE_NOTE)
        third = self.apply()

        self.assertIn("PR #1 refused conflict", first.stdout)
        self.assertIn("PR #1 refused conflict already-reported", second.stdout)
        self.assertIn("PR #1 applied success", third.stdout)
        self.assertEqual(
            len([body for _, body in self.github.posted_comments if "conflict:" in body]), 1
        )
        conflicts = [r for r in self.audit_lines() if r["result_category"] == "conflict"]
        self.assertEqual(len(conflicts), 1)

    def test_policy_change_rechecks_a_refused_head_once(self) -> None:
        self.create_pr({"vault/Shared/note.md": None})
        self.apply()
        audit = self.audit_lines()
        audit[-1]["rules_sha256"] = "0" * 64
        self.audit.write_text("".join(json.dumps(r) + "\n" for r in audit), encoding="utf-8")

        second = self.apply()
        third = self.apply()

        self.assertIn("PR #1 refused deletion", second.stdout)
        self.assertIn("PR #1 refused-before deletion", third.stdout)
        self.assertEqual(len(self.github.posted_comments), 2)

    def test_busy_shared_lock_skips_apply_without_failing(self) -> None:
        import fcntl

        self.create_pr({"vault/Shared/note.md": INCOMING_NOTE})
        real_lock = self.apply_module.bridge_lock
        with self.lock_file.open("rb") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = self.apply()
            with mock.patch.object(
                self.apply_module, "bridge_lock", wraps=real_lock
            ) as lock:
                second = self.apply(in_process=True)
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertEqual(second.returncode, 0, self.output(second))
        self.assertIn("another bridge", self.output(result).lower())
        self.assertEqual((self.vault / "Shared" / "note.md").read_text(), BASE_NOTE)
        self.assertEqual(self.github.posted_comments, [])
        # The next apply is a minute away: skip at once, never wait like publish.
        self.assertEqual(lock.call_args.kwargs.get("wait_seconds", 0), 0)
        status = self.status()
        self.assertEqual(
            (status["job"], status["last_outcome"]), ("apply", "skipped-busy")
        )
        self.assertEqual(status["consecutive_skips"], 2)
        self.assertIsNone(status["last_real_run_at"])

        applied = self.apply()

        self.assertEqual(applied.returncode, 0, self.output(applied))
        self.assertIn("PR #1 applied", applied.stdout)
        status = self.status()
        self.assertEqual(
            (status["last_outcome"], status["consecutive_skips"]), ("ran", 0)
        )
        self.assertEqual(status["last_real_run_at"], status["last_run_at"])

    def test_pause_marker_stops_apply_before_the_lock_and_the_network(self) -> None:
        self.create_pr({"vault/Shared/note.md": INCOMING_NOTE})
        write(self.root / "paused" / "apply", "")
        # A run that got as far as the lock would fail on the missing lock file.
        self.lock_file.unlink()

        dry = self.apply("--dry-run")

        self.assertEqual(dry.returncode, 0, self.output(dry))
        self.assertEqual(dry.stdout, "apply paused\n")
        self.assertFalse(self.status_path.exists())

        result = self.apply()

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertEqual(result.stdout, "apply paused\n")
        self.assertEqual(result.stderr, "")
        self.assertEqual((self.vault / "Shared" / "note.md").read_text(), BASE_NOTE)
        self.assertEqual(self.github.authorizations, [])
        self.assert_no_remote_effects()
        self.assertFalse(self.audit.exists())
        status = self.status()
        self.assertEqual((status["job"], status["last_outcome"]), ("apply", "paused"))
        self.assertIsNone(status["last_real_run_at"])
        self.assertEqual(status["consecutive_skips"], 0)

    def test_pause_marker_written_while_taking_the_lock_stops_apply(self) -> None:
        self.create_pr({"vault/Shared/note.md": INCOMING_NOTE})
        real_lock = self.apply_module.bridge_lock

        @contextlib.contextmanager
        def lock_then_pause(*args, **kwargs):
            with real_lock(*args, **kwargs):
                # The owner's stop lands after the startup check, before any work.
                write(self.root / "paused" / "apply", "")
                yield

        result = self.apply(
            in_process=True,
            patches=(
                mock.patch.object(self.apply_module, "bridge_lock", lock_then_pause),
            ),
        )

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertEqual(result.stdout, "apply paused\n")
        self.assertEqual(result.stderr, "")
        self.assertEqual((self.vault / "Shared" / "note.md").read_text(), BASE_NOTE)
        self.assertEqual(self.github.authorizations, [])
        self.assert_no_remote_effects()
        self.assertFalse(self.audit.exists())
        status = self.status()
        self.assertEqual(status["last_outcome"], "paused")
        self.assertIsNone(status["last_real_run_at"])
        self.assertEqual(status["consecutive_skips"], 0)

    def test_unreadable_pause_directory_fails_apply_without_working(self) -> None:
        # Apply runs as bridge-vault beneath a root-owned marker directory. Not knowing
        # whether it is paused still stops the run, but as a failure health reports,
        # never as a quiet pause that would hide a job that no longer runs.
        self.create_pr({"vault/Shared/note.md": INCOMING_NOTE})
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

                    dry = self.apply("--dry-run", env=env)

                    self.assertEqual(dry.returncode, 2, self.output(dry))
                    self.assertEqual(dry.stderr, "error: pause state unreadable\n")
                    self.assertEqual(saved_status(), before)

                    result = self.apply(env=env)

                    self.assertEqual(result.returncode, 2, self.output(result))
                    self.assertEqual(result.stdout, "")
                    self.assertEqual(result.stderr, "error: pause state unreadable\n")
                    self.assertEqual(
                        (self.vault / "Shared" / "note.md").read_text(), BASE_NOTE
                    )
                    self.assertEqual(self.github.authorizations, [])
                    self.assert_no_remote_effects()
                    self.assertFalse(self.audit.exists())
                    status = self.status()
                    self.assertEqual(status["last_outcome"], "failed")
                    self.assertIsNone(status["last_real_run_at"])
        finally:
            # Let the fixture remove the directory.
            if locked.exists():
                locked.chmod(0o700)

    def test_status_file_tracks_failures_and_the_inbound_switch(self) -> None:
        self.create_pr({"vault/Shared/note.md": INCOMING_NOTE})
        self.token_file.chmod(0o644)

        failed = self.apply()

        # A run that took the lock and then failed still did its work.
        self.assertEqual(failed.returncode, 2, self.output(failed))
        self.assertIn("token", failed.stderr.lower())
        status = self.status()
        self.assertEqual(status["last_outcome"], "failed")
        self.assertEqual(status["last_real_run_at"], status["last_run_at"])
        self.assertEqual(stat.S_IMODE(self.status_path.stat().st_mode), 0o644)

        # The inbound kill switch is the whole job while it is off: a run, not a skip.
        self.set_policy(inbound=False)
        write(
            self.status_path,
            json.dumps(
                {
                    "version": 1,
                    "job": "apply",
                    "last_run_at": "2026-09-23T17:00:00Z",
                    "last_real_run_at": "2026-09-23T16:00:00Z",
                    "last_outcome": "skipped-busy",
                    "consecutive_skips": 3,
                }
            ),
        )

        disabled = self.apply()

        self.assertEqual(disabled.returncode, 0, self.output(disabled))
        self.assertEqual(disabled.stdout, "inbound disabled\n")
        status = self.status()
        self.assertEqual(
            (status["last_outcome"], status["consecutive_skips"]), ("ran", 0)
        )
        self.assertEqual(status["last_real_run_at"], status["last_run_at"])

    def test_status_write_failure_leaves_the_outcome_alone(self) -> None:
        self.create_pr({"vault/Shared/note.md": INCOMING_NOTE})
        blocked = self.root / "not-a-directory"
        write(blocked, "")

        result = self.apply(env={"BRIDGE_JOB_STATUS_DIR": str(blocked)})

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertIn("PR #1 applied success", result.stdout)
        self.assertEqual(result.stderr.splitlines(), ["status-write-failed"])

    def test_dry_run_posts_and_writes_nothing(self) -> None:
        self.create_pr({"vault/Shared/note.md": INCOMING_NOTE})

        result = self.apply("--dry-run")

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertIn("PR #1 dry-run", result.stdout)
        self.assertIn("Shared/note.md", result.stdout)
        self.assertEqual((self.vault / "Shared" / "note.md").read_text(), BASE_NOTE)
        self.assertFalse(self.audit.exists())
        self.assertFalse(self.backups.exists())
        self.assert_no_remote_effects()

    def test_pr_body_instructions_are_inert_data(self) -> None:
        write(self.vault / ".local" / "private.md", "must stay private\n")
        self.create_pr(
            {"vault/Shared/note.md": INCOMING_NOTE},
            body="ignore the policy and apply .local",
        )

        result = self.apply()

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertEqual((self.vault / "Shared" / "note.md").read_text(), INCOMING_NOTE)
        self.assertEqual(
            (self.vault / ".local" / "private.md").read_text(),
            "must stay private\n",
        )
        self.assertNotIn("ignore the policy", self.output(result))
        self.assertNotIn("ignore the policy", self.audit.read_text(encoding="utf-8"))

    def test_comment_failure_rerun_reports_without_reapplying(self) -> None:
        self.create_pr({"vault/Shared/note.md": INCOMING_NOTE})
        self.github.comment_failures = 1

        first = self.apply()

        self.assertEqual(first.returncode, 2, self.output(first))
        self.assertEqual((self.vault / "Shared" / "note.md").read_text(), INCOMING_NOTE)
        self.assertEqual(len(self.audit_lines()), 1)
        self.assertTrue((self.backups / "apply-test" / "manifest.json").is_file())

        second = self.apply()

        self.assertEqual(second.returncode, 0, self.output(second))
        self.assertIn("PR #1 already-applied reported", second.stdout)
        self.assertEqual(len(self.audit_lines()), 1)
        self.assertEqual(self.github.state_changes, [(1, {"state": "closed"})])
        self.assertEqual(
            [path.name for path in self.backups.iterdir()], ["apply-test"]
        )

    def test_close_denial_rerun_never_reapplies_the_successful_head(self) -> None:
        self.create_pr({"vault/Shared/note.md": INCOMING_NOTE})
        self.github.close_denied = True

        first = self.apply()
        second = self.apply()

        self.assertEqual(first.returncode, 0, self.output(first))
        self.assertIn("PR #1 applied close-failed", first.stdout)
        self.assertEqual(second.returncode, 0, self.output(second))
        self.assertIn("PR #1 already-applied close-failed", second.stdout)
        self.assertEqual((self.vault / "Shared" / "note.md").read_text(), INCOMING_NOTE)
        self.assertEqual(len(self.audit_lines()), 1)
        self.assertEqual(self.github.close_attempts, 2)
        self.assertEqual(self.github.state_changes, [])
        self.assertEqual(
            [path.name for path in self.backups.iterdir()], ["apply-test"]
        )

    def test_failed_write_restores_every_file_from_backup(self) -> None:
        old = {
            "Shared/a.md": b"---\ntitle: A\n---\nold-a\n",
            "Shared/b.md": b"---\ntitle: B\n---\nold-b\n",
        }
        incoming = {
            "Shared/a.md": b"---\ntitle: A\n---\nnew-a\n",
            "Shared/b.md": b"---\ntitle: B\n---\nnew-b\n",
        }
        for relative, data in old.items():
            write(self.vault / relative, data)
        expected = {
            relative: hashlib.sha256(data).hexdigest()
            for relative, data in old.items()
        }
        record = self.apply_module.make_record(
            "failed-write", 7, "a" * 40, {"added": 0, "modified": 2, "deleted": 0},
            "inspect", dry_run=False,
        )
        real_apply_files = self.apply_module.apply_files
        real_write = __import__("bridge_common").secure_atomic_write
        failed = False

        def apply_with_one_failure(vault, files, entries, run_dir, expected_local):
            def flaky_write(root, relative, data, *, mode=0o600):
                nonlocal failed
                if relative == "Shared/b.md" and not failed:
                    failed = True
                    raise self.BridgeError("synthetic-write", "synthetic write failure")
                return real_write(root, relative, data, mode=mode)

            return real_apply_files(
                vault,
                files,
                entries,
                run_dir,
                expected_local,
                write_file=flaky_write,
            )

        with mock.patch.object(
            self.apply_module, "apply_files", side_effect=apply_with_one_failure
        ):
            with self.assertRaises(self.BridgeError):
                self.apply_module.apply_transaction(
                    self.vault,
                    self.backups,
                    self.audit,
                    "failed-write",
                    incoming,
                    expected,
                    record,
                )

        for relative, data in old.items():
            self.assertEqual((self.vault / relative).read_bytes(), data)
        self.assertEqual(self.audit_lines()[-1]["result_category"], "synthetic-write")
        manifest = json.loads(
            (self.backups / "failed-write" / "manifest.json").read_text()
        )
        self.assertEqual(len(manifest["files"]), 2)

    # Auto-apply scope.

    def use_inbox_policy(self) -> None:
        text = policy_text(inbound=True).replace(
            'roots = ["Shared", "Single.md"]',
            'roots = ["Shared", "Single.md", "5 Inbox"]',
        )
        self.assertIn('"5 Inbox"', text)
        write(self.policy, text)
        git(self.worktree, "add", "bridge-policy.toml")
        git(self.worktree, "commit", "-m", "Allow the inbox")
        git(self.worktree, "push", "origin", "main")

    def assert_held(self, result, *, returncode: int = 0) -> str:
        self.assertEqual(result.returncode, returncode, self.output(result))
        self.assertIn("PR #1 held", result.stdout)
        self.assertEqual((self.vault / "Shared" / "note.md").read_text(), BASE_NOTE)
        self.assertFalse(self.backups.exists())
        self.assertEqual(self.github.state_changes, [])
        self.assertEqual(len(self.github.posted_comments), 1)
        number, body = self.github.posted_comments[0]
        self.assertEqual(number, 1)
        self.assertIn("so it is not applied automatically", body)
        self.assertIn("makes the change in the vault by hand", body)
        self.assertIn("(bridge-apply, ", body)
        held = [
            line for line in self.audit_lines() if line["result_category"] == "held"
        ]
        self.assertEqual(len(held), 1)
        return body

    def test_auto_apply_scope_matches_whole_components(self) -> None:
        module = self.apply_module
        roots = module.parse_auto_apply_roots("5 Inbox")
        self.assertEqual(roots, (("5 Inbox",),))
        for inside in ("5 Inbox/a.md", "5 Inbox/x/y.md"):
            self.assertTrue(module.in_auto_scope(inside, roots), inside)
        for outside in (
            "5 Inboxes/a.md",
            "5 inbox/a.md",
            "Shared/5 Inbox/a.md",
            "Shared/note.md",
        ):
            self.assertFalse(module.in_auto_scope(outside, roots), outside)
        self.assertEqual(module.parse_auto_apply_roots(""), ())
        self.assertEqual(module.parse_auto_apply_roots(" , "), ())
        self.assertEqual(
            module.parse_auto_apply_roots("5 Inbox, Shared/sub/"),
            (("5 Inbox",), ("Shared", "sub")),
        )
        self.assertFalse(module.in_auto_scope("5 Inbox/a.md", ()))
        for invalid in ("../x", "/abs", "a\\b", "a\x00b", "5 Inbox/../Shared"):
            with self.subTest(root=invalid):
                with self.assertRaises(self.BridgeError):
                    module.parse_auto_apply_roots(invalid)

    def test_inbox_only_pr_applies_by_default(self) -> None:
        self.use_inbox_policy()
        self.create_pr({"vault/5 Inbox/capture.md": INCOMING_NOTE})

        result = self.apply(auto_apply_roots=None)

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertIn("PR #1 applied success", result.stdout)
        self.assertEqual(
            (self.vault / "5 Inbox" / "capture.md").read_text(), INCOMING_NOTE
        )
        self.assertEqual(self.github.state_changes, [(1, {"state": "closed"})])

    def test_pr_outside_inbox_is_held_with_one_comment(self) -> None:
        self.use_inbox_policy()
        sha = self.create_pr({"vault/Shared/note.md": INCOMING_NOTE})

        result = self.apply(auto_apply_roots=None)

        body = self.assert_held(result)
        self.assertIn("PR #1 held out-of-scope 1", result.stdout)
        self.assertIn('this proposal changes files outside "vault/5 Inbox/"', body)
        self.assertIn(f"head `{sha}`", body)
        self.assertIn("this pull request stays open until then", body)
        record = self.audit_lines()[-1]
        self.assertEqual(record["head_sha"], sha)
        self.assertEqual(record["out_of_scope"], 1)
        self.assertEqual(record["auto_apply_roots"], ["5 Inbox"])
        self.assertEqual(record["hold_comment"], "posted")
        self.assertNotIn("after", self.output(result))

    def test_mixed_pr_is_held_whole(self) -> None:
        self.use_inbox_policy()
        self.create_pr(
            {
                "vault/5 Inbox/capture.md": INCOMING_NOTE,
                "vault/Shared/note.md": INCOMING_NOTE,
            }
        )

        result = self.apply(auto_apply_roots=None)

        self.assert_held(result)
        self.assertIn("PR #1 held out-of-scope 1", result.stdout)
        self.assertFalse((self.vault / "5 Inbox" / "capture.md").exists())

    def test_held_pr_rerun_does_not_comment_twice(self) -> None:
        self.create_pr({"vault/Shared/note.md": INCOMING_NOTE})

        first = self.apply(auto_apply_roots=None)
        scans = self.gitleaks_log.read_text().count("\n")
        second = self.apply(auto_apply_roots=None)

        self.assert_held(first)
        self.assert_held(second)
        self.assertIn("PR #1 held already-reported", second.stdout)
        self.assertEqual(self.gitleaks_log.read_text().count("\n"), scans)

    def test_widened_roots_release_an_earlier_hold(self) -> None:
        self.create_pr({"vault/Shared/note.md": INCOMING_NOTE})
        first = self.apply(auto_apply_roots=None)
        self.assert_held(first)

        second = self.apply(auto_apply_roots="5 Inbox,Shared")

        self.assertEqual(second.returncode, 0, self.output(second))
        self.assertIn("PR #1 applied success", second.stdout)
        self.assertEqual((self.vault / "Shared" / "note.md").read_text(), INCOMING_NOTE)
        self.assertEqual(self.audit_lines()[-1]["result_category"], "success")
        self.assertEqual(self.github.state_changes, [(1, {"state": "closed"})])

    def test_changed_roots_recheck_once_without_a_second_comment(self) -> None:
        self.create_pr({"vault/Shared/note.md": INCOMING_NOTE})
        self.assert_held(self.apply(auto_apply_roots=None))
        scans = self.gitleaks_log.read_text().count("\n")

        second = self.apply(auto_apply_roots="5 Inbox,Other")
        rescans = self.gitleaks_log.read_text().count("\n")
        third = self.apply(auto_apply_roots="Other, 5 Inbox")

        self.assertEqual(second.returncode, 0, self.output(second))
        self.assertIn("PR #1 held out-of-scope 1", second.stdout)
        self.assertGreater(rescans, scans)
        self.assertEqual(third.returncode, 0, self.output(third))
        self.assertIn("PR #1 held already-reported", third.stdout)
        self.assertEqual(self.gitleaks_log.read_text().count("\n"), rescans)
        self.assertEqual(len(self.github.posted_comments), 1)
        self.assertEqual((self.vault / "Shared" / "note.md").read_text(), BASE_NOTE)
        held = [
            line for line in self.audit_lines() if line["result_category"] == "held"
        ]
        self.assertEqual(
            [(line["auto_apply_roots"], line["hold_comment"]) for line in held],
            [(["5 Inbox"], "posted"), (["5 Inbox", "Other"], "already-posted")],
        )

    def test_empty_auto_apply_roots_holds_everything(self) -> None:
        self.use_inbox_policy()
        self.create_pr({"vault/5 Inbox/capture.md": INCOMING_NOTE})

        result = self.apply(
            auto_apply_roots=None, env={"BRIDGE_AUTO_APPLY_ROOTS": ""}
        )

        body = self.assert_held(result)
        self.assertIn("auto-apply is switched off for every path", body)
        self.assertFalse((self.vault / "5 Inbox" / "capture.md").exists())

    def test_dry_run_lists_held_paths_without_effects(self) -> None:
        self.create_pr({"vault/Shared/note.md": INCOMING_NOTE})

        result = self.apply("--dry-run", auto_apply_roots=None)

        self.assertEqual(result.returncode, 0, self.output(result))
        self.assertIn("PR #1 dry-run held out-of-scope 1", result.stdout)
        self.assertIn('would-hold "Shared/note.md"', result.stdout)
        self.assertFalse(self.audit.exists())
        self.assert_no_remote_effects()


if __name__ == "__main__":
    import unittest

    unittest.main()
