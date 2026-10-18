from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


TOOLS = Path(__file__).resolve().parents[1]
PUBLISH = TOOLS / "bridge-publish"
IMPORT = TOOLS / "bridge-import"
APPLY = TOOLS / "bridge-apply"
RESTORE = TOOLS / "bridge-restore"


POLICY = """\
version = 1
publish_root = "vault"

[allow]
roots = ["Shared", "Single.md"]
extensions = ["md", "json", "png"]

[deny]
paths = ["Shared/private", ".local", ".git"]
names = [".env", ".env.*", "*.key", ".gitleaks.toml", ".gitleaksignore"]
special_files = "reject"

[limits]
max_file_bytes = 1024
max_total_bytes = 4096

[secret_scan]
tool = "gitleaks"
on_failure = "stop"

[inbound]
mode = "{inbound_mode}"
enabled = {inbound_enabled}
propagate_deletions = false
on_conflict = "stop"
backup_before_write = "required"
"""


STUB_GITLEAKS = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

args = sys.argv[1:]
log = os.environ.get("STUB_GITLEAKS_LOG")
if log:
    with open(log, "a", encoding="utf-8") as stream:
        stream.write(json.dumps(args) + "\n")

mode = os.environ.get("STUB_GITLEAKS_MODE", "clean")
source = Path(args[args.index("--source") + 1]) if "--source" in args else None
source_files = ([source] if source and source.is_file() else list(source.rglob("*"))) if source else []
if mode == "auto" and source is not None:
    mode = "hit" if any(p.is_file() and b"TEST_CREDENTIAL_VALUE" in p.read_bytes() for p in source_files) else "clean"

if mode == "clean":
    raise SystemExit(0)
if mode == "error":
    print("scanner unavailable", file=sys.stderr)
    raise SystemExit(7)

reported = next((p for p in source_files if p.is_file()), (source or Path("vault")) / "Shared" / "secret.md")
finding = [{
    "RuleID": "test-credential",
    "File": str(reported),
    "Secret": "TEST_CREDENTIAL_VALUE",
}]
if "--report-path" in args:
    Path(args[args.index("--report-path") + 1]).write_text(json.dumps(finding), encoding="utf-8")
else:
    print(json.dumps(finding))
raise SystemExit(2)
'''


def run(
    args: list[os.PathLike[str] | str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run(
        [str(arg) for arg in args],
        cwd=cwd,
        env=merged,
        text=True,
        capture_output=True,
        check=check,
    )


def git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run(["git", *args], cwd=cwd, check=check)


def write(path: Path, content: str | bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, bytes):
        path.write_bytes(content)
    else:
        path.write_text(content, encoding="utf-8")


def policy_text(*, inbound: bool = False, mode: str = "review-gated") -> str:
    return POLICY.format(inbound_enabled=str(inbound).lower(), inbound_mode=mode)


class BridgeCase(unittest.TestCase):
    secret = "TEST_CREDENTIAL_VALUE"

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="bridge-test-")
        self.root = Path(self.temp.name)
        self.vault = self.root / "private-vault"
        self.remote = self.root / "origin.git"
        self.worktree = self.root / "bridge-worktree"
        self.audit = self.root / "audit.jsonl"
        self.state = self.root / "import-state"
        self.backups = self.root / "backups"
        self.gitleaks = self.root / "gitleaks"
        self.gitleaks_config = self.root / "gitleaks.toml"
        self.gitleaks_log = self.root / "gitleaks-invocations.jsonl"
        self.push_state = self.root / "publish-state.json"
        self.lock_file = self.root / "bridge.lock"
        self.visibility_attestation = self.root / "repository.json"
        self.policy = self.worktree / "bridge-policy.toml"

        self.vault.mkdir()
        git(self.root, "init", "--bare", "--initial-branch=main", str(self.remote))
        git(self.root, "clone", str(self.remote), str(self.worktree))
        git(self.worktree, "switch", "-c", "main")
        git(self.worktree, "config", "user.name", "Bridge Test")
        git(self.worktree, "config", "user.email", "bridge@invalid")
        write(self.policy, policy_text())
        write(self.worktree / "README.md", "fixture\n")
        write(self.worktree / "vault" / ".gitkeep", "")
        git(self.worktree, "add", "README.md", "bridge-policy.toml", "vault/.gitkeep")
        git(self.worktree, "commit", "-m", "Initial fixture")
        git(self.worktree, "push", "-u", "origin", "main")

        write(self.gitleaks, STUB_GITLEAKS)
        self.gitleaks.chmod(0o755)
        write(self.gitleaks_config, "# synthetic config\n")
        write(self.lock_file, "")
        write(
            self.visibility_attestation,
            json.dumps({
                "version": 1,
                "remote_url": str(self.remote),
                "visibility": "private",
                "repository_id": "synthetic-origin",
                "verified_via": "local-test",
                "verified_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }),
        )
        self.visibility_attestation.chmod(0o600)

    def tearDown(self) -> None:
        self.temp.cleanup()

    @property
    def env(self) -> dict[str, str]:
        return {
            "STUB_GITLEAKS_MODE": "clean",
            "STUB_GITLEAKS_LOG": str(self.gitleaks_log),
            "GIT_AUTHOR_NAME": "Bridge Job",
            "GIT_AUTHOR_EMAIL": "bridge-job@invalid",
            "GIT_COMMITTER_NAME": "Bridge Job",
            "GIT_COMMITTER_EMAIL": "bridge-job@invalid",
            "BRIDGE_GIT_NAME": "Bridge Job",
            "BRIDGE_GIT_EMAIL": "bridge-job@invalid",
            "LC_ALL": "C.UTF-8",
            # Never the host defaults: /etc/assistant-bridge/paused and the vault user's state.
            "BRIDGE_JOB_STATUS_DIR": str(self.root / "job-status"),
            "BRIDGE_PAUSE_DIR": str(self.root / "paused"),
        }

    def set_policy(self, *, inbound: bool = False, mode: str = "review-gated") -> None:
        write(self.policy, policy_text(inbound=inbound, mode=mode))
        git(self.worktree, "add", "bridge-policy.toml")
        git(self.worktree, "commit", "-m", "Configure fixture policy")
        git(self.worktree, "push", "origin", "main")

    def publish_args(self, *extra: str) -> list[str]:
        return [
            sys.executable, str(PUBLISH),
            "--vault", str(self.vault),
            "--worktree", str(self.worktree),
            "--remote-url", str(self.remote),
            "--policy", str(self.policy),
            "--gitleaks", str(self.gitleaks),
            "--gitleaks-config", str(self.gitleaks_config),
            "--audit-log", str(self.audit),
            "--push-state", str(self.push_state),
            "--lock-file", str(self.lock_file),
            "--visibility-attestation", str(self.visibility_attestation),
            "--run-id", "publish-test",
            *extra,
        ]

    def import_args(self, *extra: str, run_id: str = "import-test") -> list[str]:
        return [
            sys.executable, str(IMPORT),
            "--vault", str(self.vault),
            "--worktree", str(self.worktree),
            "--remote-url", str(self.remote),
            "--policy", str(self.policy),
            "--gitleaks", str(self.gitleaks),
            "--gitleaks-config", str(self.gitleaks_config),
            "--audit-log", str(self.audit),
            "--state-file", str(self.state),
            "--backup-dir", str(self.backups),
            "--lock-file", str(self.lock_file),
            "--visibility-attestation", str(self.visibility_attestation),
            "--run-id", run_id,
            *extra,
        ]

    def restore_args(self, run_id: str) -> list[str]:
        return [
            sys.executable, str(RESTORE), run_id,
            "--vault", str(self.vault),
            "--backup-dir", str(self.backups),
            "--worktree", str(self.worktree),
            "--policy", str(self.policy),
            "--lock-file", str(self.lock_file),
        ]

    def publish(self, *extra: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        merged = self.env
        if env:
            merged.update(env)
        return run(self.publish_args(*extra), cwd=self.root, env=merged)

    def import_(
        self,
        *extra: str,
        env: dict[str, str] | None = None,
        run_id: str = "import-test",
    ) -> subprocess.CompletedProcess[str]:
        merged = self.env
        if env:
            merged.update(env)
        return run(self.import_args(*extra, run_id=run_id), cwd=self.root, env=merged)

    def head(self, repo: Path | None = None) -> str:
        return git(repo or self.worktree, "rev-parse", "HEAD").stdout.strip()

    def remote_head(self) -> str:
        return git(self.root, "--git-dir", str(self.remote), "rev-parse", "main").stdout.strip()

    def commit_remote_file(self, relative: str, content: str, *, delete: bool = False) -> str:
        review = self.root / f"review-{len(list(self.root.glob('review-*')))}"
        git(self.root, "clone", str(self.remote), str(review))
        git(review, "config", "user.name", "the assistant for the operator")
        git(review, "config", "user.email", "assistant@invalid")
        target = review / "vault" / relative
        if delete:
            target.unlink()
            git(review, "add", "-u", "--", f"vault/{relative}")
        else:
            write(target, content)
            git(review, "add", "--", f"vault/{relative}")
        git(review, "commit", "-m", "the assistant reviewed change")
        git(review, "push", "origin", "main")
        return self.remote_head()

    def audit_lines(self) -> list[dict[str, object]]:
        if not self.audit.exists():
            return []
        return [json.loads(line) for line in self.audit.read_text(encoding="utf-8").splitlines()]

    @staticmethod
    def output(result: subprocess.CompletedProcess[str]) -> str:
        return result.stdout + result.stderr
