#!/usr/bin/env python3
"""Shared, content-safe helpers for the bridge jobs."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import time
import uuid
from collections.abc import Callable, Iterable, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path, PurePosixPath
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

RUN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")
FRONTMATTER_KEY_RE = re.compile(r"^[A-Za-z0-9_.-]+:\s*.*$")
GITHUB_REMOTE_RE = re.compile(
    r"^git@github-assistant-bridge:(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)\.git$"
)


class BridgeError(Exception):
    """A categorized failure whose message is safe to show to an operator."""

    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category
        self.message = message


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: bytes
    stderr: bytes


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def validate_run_id(value: str) -> str:
    if not RUN_ID_RE.fullmatch(value):
        raise BridgeError("invalid-run-id", "invalid run id; use letters, digits, dot, dash, or underscore")
    return value


def safe_rel(value: str) -> str:
    """Return a canonical vault-relative POSIX path or fail before I/O."""
    if not value or "\\" in value or any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise BridgeError("path-invalid", "invalid relative path")
    path = PurePosixPath(value)
    if path.is_absolute() or any(part in ("", ".", "..") for part in path.parts):
        raise BridgeError("path-traversal", "path traversal rejected")
    return path.as_posix()


def iter_allowed_candidates(vault: Path, roots: Sequence[str | PurePosixPath]):
    """Walk only explicit allow roots and never follow directory links."""
    seen: set[str] = set()
    for root_value in roots:
        rel_root = safe_rel(str(root_value))
        root = vault.joinpath(*rel_root.split("/"))
        if not root.exists() and not root.is_symlink():
            continue
        if root.is_symlink() or not root.is_dir():
            if rel_root not in seen:
                seen.add(rel_root)
                yield rel_root
            continue

        def walk_error(_error: OSError) -> None:
            raise BridgeError(
                "source-unreadable",
                "an allowed directory is unreadable; correct permissions and retry",
            )

        for directory, dirnames, filenames in os.walk(
            root, topdown=True, followlinks=False, onerror=walk_error
        ):
            base = Path(directory)
            dirnames.sort()
            filenames.sort()
            kept: list[str] = []
            for name in dirnames:
                path = base / name
                rel = path.relative_to(vault).as_posix()
                if path.is_symlink():
                    if rel not in seen:
                        seen.add(rel)
                        yield rel
                else:
                    kept.append(name)
            dirnames[:] = kept
            for name in filenames:
                rel = (base / name).relative_to(vault).as_posix()
                if rel not in seen:
                    seen.add(rel)
                    yield rel


def shown_path(value: str) -> str:
    """Quote paths so control characters can never forge a log line."""
    return json.dumps(value, ensure_ascii=True)


def is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fsync_directory(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except OSError as exc:
        raise BridgeError("durability-failed", "directory durability check failed") from exc


def run_command(
    argv: Sequence[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    input_data: bytes | None = None,
    pass_fds: tuple[int, ...] = (),
) -> CommandResult:
    try:
        result = subprocess.run(
            list(argv),
            cwd=cwd,
            env=env,
            input=input_data,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            pass_fds=pass_fds,
        )
    except (OSError, ValueError) as exc:
        raise BridgeError("command-unavailable", f"required command unavailable: {Path(argv[0]).name}") from exc
    return CommandResult(result.returncode, result.stdout, result.stderr)


def git(
    worktree: Path,
    args: Sequence[str],
    *,
    input_data: bytes | None = None,
    category: str = "git-failed",
    message: str = "git operation failed",
) -> bytes:
    result = run_command(["git", *args], cwd=worktree, input_data=input_data)
    if result.returncode != 0:
        raise BridgeError(category, message)
    return result.stdout


def git_text(worktree: Path, args: Sequence[str], **kwargs: Any) -> str:
    data = git(worktree, args, **kwargs)
    try:
        return data.decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise BridgeError("git-invalid-output", "git returned invalid text") from exc


def check_repo(worktree: Path, expected_remote: str, *, require_clean_vault: bool) -> str:
    if not worktree.is_dir():
        raise BridgeError("repo-missing", "worktree is missing or unreadable")
    inside = git_text(
        worktree,
        ["rev-parse", "--is-inside-work-tree"],
        category="repo-invalid",
        message="worktree is not a git repository",
    )
    if inside != "true":
        raise BridgeError("repo-invalid", "worktree is not a git repository")
    origin_urls = git_text(
        worktree,
        ["remote", "get-url", "--all", "origin"],
        category="remote-unverifiable",
        message="origin remote cannot be verified",
    ).splitlines()
    if origin_urls != [expected_remote]:
        raise BridgeError("remote-mismatch", "origin URL does not match the configured repository")
    push_urls = git_text(
        worktree,
        ["remote", "get-url", "--push", "--all", "origin"],
        category="remote-unverifiable",
        message="origin push URL cannot be verified",
    ).splitlines()
    if push_urls != [expected_remote]:
        raise BridgeError("remote-mismatch", "origin push URL does not match the configured repository")
    branch = git_text(
        worktree,
        ["branch", "--show-current"],
        category="branch-unverifiable",
        message="checked-out branch cannot be verified",
    )
    if branch != "main":
        raise BridgeError("branch-mismatch", "main must be checked out")
    if require_clean_vault:
        status = git(
            worktree,
            ["status", "--porcelain=v1", "--untracked-files=all", "--", "vault", "bridge-policy.toml"],
            category="status-failed",
            message="worktree status cannot be verified",
        )
        if status:
            raise BridgeError("worktree-dirty", "worktree must be clean under vault/ and bridge-policy.toml")
    return git_text(worktree, ["rev-parse", "HEAD"], category="commit-unverifiable", message="current commit cannot be verified")


def check_disjoint(vault: Path, worktree: Path) -> tuple[Path, Path]:
    try:
        vault_real = vault.resolve(strict=True)
        worktree_real = worktree.resolve(strict=True)
    except OSError as exc:
        raise BridgeError("path-unreadable", "vault or worktree path cannot be resolved") from exc
    if is_within(worktree_real, vault_real) or is_within(vault_real, worktree_real):
        raise BridgeError("path-overlap", "vault and worktree must be outside each other")
    return vault_real, worktree_real


def ensure_external(path: Path, vault: Path, worktree: Path, label: str) -> None:
    try:
        resolved = path.resolve(strict=False)
    except OSError as exc:
        raise BridgeError("state-path-unreadable", f"{label} path cannot be resolved") from exc
    if is_within(resolved, vault) or is_within(resolved, worktree):
        raise BridgeError("state-path-overlap", f"{label} must be outside the vault and worktree")


def require_regular_file(path: Path, expected: Path, label: str) -> Path:
    try:
        if path.resolve(strict=True) != expected.resolve(strict=True):
            raise BridgeError("path-mismatch", f"{label} must be the repository file")
        info = path.lstat()
    except BridgeError:
        raise
    except OSError as exc:
        raise BridgeError("path-unreadable", f"{label} is missing or unreadable") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise BridgeError("path-special", f"{label} must be a regular, singly linked file")
    return path.resolve(strict=True)


def read_regular_file(path: Path, label: str, *, max_bytes: int = 1024 * 1024) -> bytes:
    try:
        fd = os.open(
            path,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
        )
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > max_bytes:
                raise OSError("not a bounded regular file")
            chunks: list[bytes] = []
            total = 0
            while chunk := os.read(fd, 64 * 1024):
                total += len(chunk)
                if total > max_bytes:
                    raise OSError("file grew beyond limit")
                chunks.append(chunk)
            after = os.fstat(fd)
            if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                after.st_dev,
                after.st_ino,
                after.st_size,
                after.st_mtime_ns,
            ):
                raise OSError("file changed during read")
            return b"".join(chunks)
        finally:
            os.close(fd)
    except OSError as exc:
        raise BridgeError("path-unreadable", f"{label} is not a stable regular file") from exc


def read_secret_file(
    path: Path,
    label: str,
    *,
    max_bytes: int = 4096,
    additional_owner_uids: Iterable[int] = (),
) -> bytes:
    """Read a small owner-controlled secret without following links."""
    try:
        info = path.lstat()
    except OSError as exc:
        raise BridgeError("secret-invalid", f"{label} file is missing") from exc
    allowed_owners = {0, os.geteuid(), *additional_owner_uids}
    if (
        stat.S_ISLNK(info.st_mode)
        or not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or stat.S_IMODE(info.st_mode) != 0o600
        or info.st_uid not in allowed_owners
    ):
        raise BridgeError(
            "secret-invalid",
            f"{label} file must be singly linked, owner-controlled, and mode 0600",
        )
    value = read_regular_file(path, label, max_bytes=max_bytes).rstrip(b"\r\n")
    if not value or len(value) > max_bytes:
        raise BridgeError("secret-invalid", f"{label} file is invalid")
    return value


def verify_private_attestation(path: Path, expected_remote: str) -> None:
    try:
        info = path.lstat()
        local_test_remote = expected_remote.startswith("/") or expected_remote.startswith("file://")
        allowed_owners = {0, os.geteuid()} if local_test_remote else {0}
        if info.st_mode & 0o022 or info.st_uid not in allowed_owners:
            raise OSError("unsafe ownership or mode")
        document = json.loads(read_regular_file(path, "repository visibility attestation", max_bytes=16 * 1024))
    except (OSError, json.JSONDecodeError) as exc:
        raise BridgeError(
            "visibility-unverifiable",
            "private-repository visibility attestation is missing or invalid",
        ) from exc
    required = {
        "version": 1,
        "remote_url": expected_remote,
        "visibility": "private",
    }
    if not isinstance(document, dict) or any(document.get(key) != value for key, value in required.items()):
        raise BridgeError(
            "visibility-mismatch",
            "repository visibility is not attested private for the configured origin",
        )
    repository_id = document.get("repository_id")
    verified_via = document.get("verified_via")
    verified_at = document.get("verified_at")
    if (
        not isinstance(repository_id, (str, int))
        or isinstance(repository_id, bool)
        or not str(repository_id).strip()
        or not isinstance(verified_via, str)
        or verified_via not in ({"local-test", "github-settings"} if local_test_remote else {"github-settings"})
        or not isinstance(verified_at, str)
    ):
        raise BridgeError(
            "visibility-unverifiable",
            "private-repository visibility attestation lacks verification provenance",
        )
    try:
        verified_time = datetime.fromisoformat(verified_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BridgeError(
            "visibility-unverifiable",
            "private-repository visibility attestation has an invalid verification time",
        ) from exc
    if verified_time.tzinfo is None:
        raise BridgeError(
            "visibility-unverifiable",
            "private-repository visibility attestation has an invalid verification time",
        )
    now = datetime.now(timezone.utc)
    verified_utc = verified_time.astimezone(timezone.utc)
    if verified_utc > now + timedelta(minutes=5) or now - verified_utc > timedelta(days=31):
        raise BridgeError(
            "visibility-unverifiable",
            "private-repository visibility attestation is stale or future-dated",
        )
    if not local_test_remote:
        if not isinstance(repository_id, int) or isinstance(repository_id, bool) or repository_id <= 0:
            raise BridgeError(
                "visibility-unverifiable",
                "private-repository visibility attestation has an invalid repository id",
            )
        verify_github_not_public(expected_remote, repository_id)


def verify_github_not_public(expected_remote: str, repository_id: int) -> None:
    """Fail closed unless GitHub's anonymous API says the attested repo is not public."""
    match = GITHUB_REMOTE_RE.fullmatch(expected_remote)
    if match is None:
        raise BridgeError(
            "visibility-unverifiable",
            "configured repository is not a verifiable GitHub repository",
        )
    owner = match.group("owner")
    repo = match.group("repo")
    request = urlrequest.Request(
        f"https://api.github.com/repos/{owner}/{repo}",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "assistant-bridge-privacy-check/1",
            "X-GitHub-Api-Version": "2022-11-28",
        },
        method="GET",
    )
    try:
        with urlrequest.urlopen(request, timeout=15) as response:
            raw = response.read(64 * 1024 + 1)
    except urlerror.HTTPError as exc:
        if exc.code == 404:
            return
        raise BridgeError(
            "visibility-unverifiable",
            "GitHub repository visibility could not be verified",
        ) from exc
    except (urlerror.URLError, TimeoutError, OSError) as exc:
        raise BridgeError(
            "visibility-unverifiable",
            "GitHub repository visibility could not be verified",
        ) from exc
    if len(raw) > 64 * 1024:
        raise BridgeError(
            "visibility-unverifiable",
            "GitHub repository visibility response is invalid",
        )
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BridgeError(
            "visibility-unverifiable",
            "GitHub repository visibility response is invalid",
        ) from exc
    if not isinstance(document, dict) or not isinstance(document.get("private"), bool):
        raise BridgeError(
            "visibility-unverifiable",
            "GitHub repository visibility response is invalid",
        )
    if document["private"] is False:
        raise BridgeError(
            "visibility-mismatch",
            "GitHub reports that the configured repository is public",
        )
    if document.get("id") != repository_id:
        raise BridgeError(
            "visibility-mismatch",
            "GitHub repository id does not match the private-repository attestation",
        )


def require_directory(path: Path, parent: Path, label: str) -> Path:
    try:
        info = path.lstat()
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise BridgeError("path-unreadable", f"{label} is missing or unreadable") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode) or not is_within(resolved, parent):
        raise BridgeError("path-special", f"{label} must be a real directory inside the worktree")
    return resolved


def require_control_file(path: Path, label: str, *, executable: bool = False) -> Path:
    try:
        info = path.lstat()
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise BridgeError("control-file-invalid", f"{label} is missing or unreadable") from exc
    if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise BridgeError("control-file-invalid", f"{label} must be a regular, singly linked file")
    if info.st_mode & 0o022:
        raise BridgeError("control-file-invalid", f"{label} must not be group- or world-writable")
    if executable and not os.access(path, os.X_OK):
        raise BridgeError("control-file-invalid", f"{label} is not executable")
    return resolved


def check_disk(path: Path, required: int) -> None:
    try:
        free = shutil.disk_usage(path).free
    except OSError as exc:
        raise BridgeError("disk-unverifiable", "free disk space cannot be verified") from exc
    if free < required:
        raise BridgeError("disk-space", "insufficient free disk space")


def preflight_audit(path: Path) -> None:
    """Prove the audit directory is writable before any write-capable operation."""
    parent = path.parent
    if not parent.is_dir():
        raise BridgeError("audit-unwritable", "audit-log directory is missing")
    if path.exists() or path.is_symlink():
        try:
            info = path.lstat()
        except OSError as exc:
            raise BridgeError("audit-unwritable", "audit log is not writable") from exc
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or not os.access(path, os.W_OK):
            raise BridgeError("audit-unwritable", "audit log is not a writable regular file")
    try:
        fd, probe = tempfile.mkstemp(prefix=".bridge-audit-", dir=parent)
        os.close(fd)
        os.unlink(probe)
    except OSError as exc:
        raise BridgeError("audit-unwritable", "audit log is not writable") from exc


def append_audit(path: Path, record: dict[str, Any]) -> None:
    public = {key: value for key, value in record.items() if not key.startswith("_")}
    line = json.dumps(public, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n"
    fd: int | None = None
    offset: int | None = None
    try:
        fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise OSError("audit target is not a regular file")
            fcntl.flock(fd, fcntl.LOCK_EX)
            offset = os.lseek(fd, 0, os.SEEK_END)
            pending = memoryview(line.encode("utf-8"))
            while pending:
                written = os.write(fd, pending)
                if written <= 0:
                    raise OSError("short audit write")
                pending = pending[written:]
            os.fsync(fd)
            parent_fd = os.open(
                path.parent,
                os.O_RDONLY
                | getattr(os, "O_DIRECTORY", 0)
                | getattr(os, "O_NOFOLLOW", 0),
            )
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
        except BaseException:
            if offset is not None:
                try:
                    os.ftruncate(fd, offset)
                    os.fsync(fd)
                except OSError:
                    pass
            raise
        finally:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            os.close(fd)
    except OSError as exc:
        raise BridgeError("audit-write-failed", "audit log write failed") from exc


@dataclass
class AuditReservation:
    fd: int
    offset: int
    size: int

    def finalize(self, record: dict[str, Any]) -> None:
        public = {key: value for key, value in record.items() if not key.startswith("_")}
        encoded = json.dumps(public, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
        if len(encoded) + 1 > self.size:
            raise BridgeError("audit-write-failed", "audit record exceeded its reserved slot")
        line = encoded + (b" " * (self.size - len(encoded) - 1)) + b"\n"
        try:
            pending = memoryview(line)
            position = 0
            while pending:
                written = os.pwrite(self.fd, pending, self.offset + position)
                if written <= 0:
                    raise OSError("short audit write")
                position += written
                pending = pending[written:]
            os.fsync(self.fd)
        except OSError as exc:
            raise BridgeError("audit-write-failed", "audit log finalization failed; pending record retained") from exc

    def close(self) -> None:
        try:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
        finally:
            os.close(self.fd)


def reserve_audit(path: Path, record: dict[str, Any]) -> AuditReservation:
    """Durably append one fixed-size pending record before an irreversible write."""
    public = {key: value for key, value in record.items() if not key.startswith("_")}
    encoded = json.dumps(public, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("utf-8")
    size = len(encoded) + 512
    fd: int | None = None
    offset: int | None = None
    try:
        fd = os.open(path, os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0), 0o600)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise OSError("audit target is not a regular file")
        fcntl.flock(fd, fcntl.LOCK_EX)
        offset = os.lseek(fd, 0, os.SEEK_END)
        line = encoded + (b" " * (size - len(encoded) - 1)) + b"\n"
        pending = memoryview(line)
        while pending:
            written = os.write(fd, pending)
            if written <= 0:
                raise OSError("short audit write")
            pending = pending[written:]
        os.fsync(fd)
        parent_fd = os.open(
            path.parent,
            os.O_RDONLY
            | getattr(os, "O_DIRECTORY", 0)
            | getattr(os, "O_NOFOLLOW", 0),
        )
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
        return AuditReservation(fd, offset, size)
    except OSError as exc:
        if fd is not None and offset is not None:
            try:
                os.ftruncate(fd, offset)
                os.fsync(fd)
            except OSError:
                pass
        try:
            os.close(fd)
        except (OSError, TypeError):
            pass
        raise BridgeError("audit-write-failed", "audit reservation failed") from exc


def atomic_write(path: Path, data: bytes, *, mode: int = 0o600) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        temp = Path(temp_name)
        try:
            os.fchmod(fd, mode)
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp, path)
            directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
        except BaseException:
            try:
                temp.unlink(missing_ok=True)
            except OSError:
                pass
            raise
    except OSError as exc:
        raise BridgeError("atomic-write-failed", f"atomic write failed for {shown_path(path.name)}") from exc


DEFAULT_PAUSE_DIR = Path("/etc/assistant-bridge/paused")
JOB_STATUS_MAX_BYTES = 64 * 1024


def job_paused(job: str, pause_dir: Path | None = None) -> bool:
    """True when the owner's pause marker for `job` exists (checked before any work).

    The marker directory is root-owned; a job that cannot tell whether it is paused
    treats itself as paused, so an unreadable directory never lets a held job run.
    """
    directory = pause_dir or Path(os.environ.get("BRIDGE_PAUSE_DIR") or DEFAULT_PAUSE_DIR)
    try:
        os.lstat(directory / job)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return True


def write_job_status(path: Path, fields: dict[str, Any]) -> None:
    """Record a job's liveness for operators; nothing reads it automatically."""
    document = {"version": 1, "updated_at": utc_now(), **fields}
    data = json.dumps(document, ensure_ascii=True, sort_keys=True, indent=1).encode("utf-8") + b"\n"
    atomic_write(path, data, mode=0o644)


def read_job_status(path: Path) -> dict[str, Any] | None:
    """A job's status document, or None when it is missing. Its content is data, never trusted."""
    try:
        raw = read_regular_file(path, "job status", max_bytes=JOB_STATUS_MAX_BYTES)
    except BridgeError:
        if not os.path.lexists(path):
            return None
        raise
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BridgeError("job-status-invalid", "job status is not valid JSON") from exc
    if not isinstance(document, dict) or document.get("version") != 1:
        raise BridgeError("job-status-invalid", "job status has an unknown shape")
    return document


LOCK_POLL_SECONDS = 0.5


@contextmanager
def bridge_lock(lock_path: Path, *, wait_seconds: float = 0):
    """Serialize bridge jobs on one stable, pre-created external lock file.

    A busy lock raises bridge-busy at once, or after *wait_seconds* of polling. The
    poll never blocks in flock, so the wait cannot outlast its deadline.
    """
    try:
        fd = os.open(
            lock_path,
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0),
        )
        try:
            info = os.fstat(fd)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise OSError("lock target is not a regular file")
            deadline = time.monotonic() + max(wait_seconds, 0)
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError as exc:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise BridgeError(
                            "bridge-busy", "another bridge operation is running; retry later"
                        ) from exc
                    time.sleep(min(LOCK_POLL_SECONDS, remaining))
        except BaseException:
            os.close(fd)
            raise
        try:
            yield
        finally:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
    except BridgeError:
        raise
    except OSError as exc:
        raise BridgeError("bridge-lock-failed", "bridge lock file cannot be acquired") from exc


@contextmanager
def secure_parent(root: Path, relative: str, *, create: bool = False):
    """Yield a no-follow directory descriptor and final name beneath *root*."""
    rel = safe_rel(relative)
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | nofollow
    descriptors: list[int] = []
    try:
        current = os.open(root, directory_flags)
        descriptors.append(current)
        parts = rel.split("/")
        for component in parts[:-1]:
            try:
                child = os.open(component, directory_flags, dir_fd=current)
            except FileNotFoundError:
                if not create:
                    raise
                os.mkdir(component, 0o700, dir_fd=current)
                child = os.open(component, directory_flags, dir_fd=current)
            descriptors.append(child)
            current = child
        yield current, parts[-1]
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def secure_read_file(
    root: Path,
    relative: str,
    *,
    missing_ok: bool = False,
    max_bytes: int | None = None,
) -> tuple[bytes, int] | None:
    try:
        with secure_parent(root, relative) as (parent_fd, name):
            fd = os.open(
                name,
                os.O_RDONLY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_NONBLOCK", 0),
                dir_fd=parent_fd,
            )
            try:
                before = os.fstat(fd)
                if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
                    raise BridgeError("special-file", f"special file rejected: {shown_path(relative)}")
                if max_bytes is not None and before.st_size > max_bytes:
                    raise BridgeError("oversized", f"file exceeds the policy limit: {shown_path(relative)}")
                chunks: list[bytes] = []
                total = 0
                while chunk := os.read(fd, 1024 * 1024):
                    total += len(chunk)
                    if max_bytes is not None and total > max_bytes:
                        raise BridgeError("oversized", f"file exceeds the policy limit: {shown_path(relative)}")
                    chunks.append(chunk)
                after = os.fstat(fd)
                if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
                    after.st_dev,
                    after.st_ino,
                    after.st_size,
                    after.st_mtime_ns,
                ):
                    raise BridgeError("source-changed", f"file changed during read: {shown_path(relative)}")
                return b"".join(chunks), stat.S_IMODE(before.st_mode)
            finally:
                os.close(fd)
    except FileNotFoundError:
        if missing_ok:
            return None
        raise BridgeError("source-unreadable", f"file is missing: {shown_path(relative)}") from None
    except BridgeError:
        raise
    except OSError as exc:
        raise BridgeError("source-unreadable", f"file is unreadable: {shown_path(relative)}") from exc


def secure_atomic_write(root: Path, relative: str, data: bytes, *, mode: int = 0o600) -> None:
    temp_name = f".bridge-write-{uuid.uuid4().hex}"
    try:
        with secure_parent(root, relative, create=True) as (parent_fd, name):
            try:
                current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            except FileNotFoundError:
                current = None
            if current is not None and (
                not stat.S_ISREG(current.st_mode) or stat.S_ISLNK(current.st_mode) or current.st_nlink != 1
            ):
                raise BridgeError("special-file", f"special file rejected: {shown_path(relative)}")
            temp_exists = False
            try:
                fd = os.open(
                    temp_name,
                    os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                    mode,
                    dir_fd=parent_fd,
                )
                temp_exists = True
                try:
                    view = memoryview(data)
                    while view:
                        written = os.write(fd, view)
                        view = view[written:]
                    os.fchmod(fd, mode)
                    os.fsync(fd)
                finally:
                    os.close(fd)
                os.replace(temp_name, name, src_dir_fd=parent_fd, dst_dir_fd=parent_fd)
                temp_exists = False
                os.fsync(parent_fd)
            finally:
                if temp_exists:
                    try:
                        os.unlink(temp_name, dir_fd=parent_fd)
                    except OSError:
                        pass
    except BridgeError:
        raise
    except OSError as exc:
        raise BridgeError("atomic-write-failed", f"atomic write failed for {shown_path(relative)}") from exc


def secure_move_out(root: Path, relative: str, destination: Path) -> None:
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() or destination.is_symlink():
            raise BridgeError("quarantine-exists", f"quarantine already exists: {shown_path(relative)}")
        with secure_parent(root, relative) as (parent_fd, name):
            current = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            if not stat.S_ISREG(current.st_mode) or stat.S_ISLNK(current.st_mode):
                raise BridgeError("special-file", f"special file rejected: {shown_path(relative)}")
            if current.st_dev != destination.parent.stat().st_dev:
                raise BridgeError("quarantine-filesystem", "quarantine must be on the vault filesystem")
            os.replace(name, destination, src_dir_fd=parent_fd)
            fsync_directory(destination.parent)
            os.fsync(parent_fd)
    except BridgeError:
        raise
    except OSError as exc:
        raise BridgeError("quarantine-failed", f"quarantine failed for {shown_path(relative)}") from exc


def parse_gitleaks_report(report_path: Path, source_root: Path) -> list[dict[str, str]]:
    try:
        raw = report_path.read_text(encoding="utf-8") if report_path.exists() else "[]"
        items = json.loads(raw or "[]")
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BridgeError("scanner-report-invalid", "secret scanner report is invalid") from exc
    if not isinstance(items, list):
        raise BridgeError("scanner-report-invalid", "secret scanner report is invalid")
    findings: list[dict[str, str]] = []
    root = source_root.resolve()
    for item in items:
        if not isinstance(item, dict):
            continue
        raw_file = str(item.get("File", item.get("file", "unknown")))
        rule = str(item.get("RuleID", item.get("ruleID", item.get("rule_id", "unknown"))))
        candidate = Path(raw_file)
        if candidate.is_absolute():
            try:
                raw_file = candidate.resolve().relative_to(root).as_posix()
            except (OSError, ValueError):
                raw_file = "unknown"
        else:
            raw_file = PurePosixPath(raw_file).as_posix()
            prefix = source_root.name + "/"
            raw_file = raw_file.removeprefix(prefix)
        try:
            rel = safe_rel(raw_file)
        except BridgeError:
            rel = "unknown"
        safe_rule = re.sub(r"[^A-Za-z0-9._:-]", "?", rule)[:128] or "unknown"
        findings.append({"path": rel, "rule": safe_rule})
    return findings


def scan_gitleaks(executable: Path, config: Path, source: Path) -> tuple[str, list[dict[str, str]]]:
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise BridgeError("scanner-unavailable", "secret scanner is missing or not executable")
    if not config.is_file():
        raise BridgeError("scanner-config-missing", "secret scanner configuration is missing")
    with tempfile.TemporaryDirectory(prefix="bridge-gitleaks-") as temp_dir:
        report = Path(temp_dir) / "report.json"
        result = run_command(
            [
                str(executable),
                "detect",
                "--no-git",
                "--source",
                str(source),
                "--redact",
                "--exit-code",
                "2",
                "--config",
                str(config),
                "--ignore-gitleaks-allow",
                "--report-format",
                "json",
                "--report-path",
                str(report),
            ]
        )
        if result.returncode == 0:
            return "clean", []
        if result.returncode == 2:
            findings = parse_gitleaks_report(report, source)
            if not findings:
                findings = [{"path": "unknown", "rule": "secret-detected"}]
            return "hit", findings
        raise BridgeError("scanner-error", "secret scanner failed; correct the scanner and retry")


def rsync_tree(source: Path, destination: Path) -> None:
    try:
        source_info = source.lstat()
        destination_info = destination.lstat()
    except OSError as exc:
        raise BridgeError("rsync-path-invalid", "mirror source or destination is missing") from exc
    if (
        stat.S_ISLNK(source_info.st_mode)
        or not stat.S_ISDIR(source_info.st_mode)
        or stat.S_ISLNK(destination_info.st_mode)
        or not stat.S_ISDIR(destination_info.st_mode)
    ):
        raise BridgeError("rsync-path-invalid", "mirror source and destination must be real directories")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory_flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | nofollow
    try:
        source_fd = os.open(source, directory_flags)
        destination_fd = os.open(destination, directory_flags)
    except OSError as exc:
        try:
            os.close(source_fd)
        except (OSError, UnboundLocalError):
            pass
        raise BridgeError("rsync-path-invalid", "mirror directories cannot be opened safely") from exc
    try:
        proc_fd = f"/proc/{os.getpid()}/fd"
        result = run_command(
            [
                "rsync",
                "--archive",
                "--delete",
                "--safe-links",
                "--",
                f"{proc_fd}/{source_fd}/",
                f"{proc_fd}/{destination_fd}/",
            ],
            pass_fds=(source_fd, destination_fd),
        )
    finally:
        os.close(source_fd)
        os.close(destination_fd)
    if result.returncode != 0:
        raise BridgeError("rsync-failed", "mirror update failed; check permissions and disk space")


def summarize_trees(staged: Path, current: Path) -> dict[str, list[str]]:
    def regular_files(root: Path) -> dict[str, Path]:
        if not root.exists():
            return {}
        result: dict[str, Path] = {}
        for directory, dirnames, filenames in os.walk(root, followlinks=False):
            dirnames.sort()
            filenames.sort()
            base = Path(directory)
            for name in filenames:
                path = base / name
                rel = path.relative_to(root).as_posix()
                if path.is_file() and not path.is_symlink():
                    result[rel] = path
        return result

    new = regular_files(staged)
    old = regular_files(current)
    added = sorted(new.keys() - old.keys())
    deleted = sorted(old.keys() - new.keys())
    modified = sorted(rel for rel in new.keys() & old.keys() if sha256_file(new[rel]) != sha256_file(old[rel]))
    return {"added": added, "modified": modified, "deleted": deleted}


def print_summary(summary: dict[str, Iterable[str]]) -> None:
    for category in ("added", "modified", "deleted", "denied", "oversized", "conflicts", "proposed_deletions"):
        for value in summary.get(category, []):
            print(f"{category.replace('_', '-')} {shown_path(str(value))}")
    counts = " ".join(f"{key}={len(list(summary.get(key, [])))}" for key in summary)
    print(f"summary {counts}")


def validate_frontmatter(relative: str, data: bytes) -> None:
    """Validate the bridge's deliberately small YAML-frontmatter contract."""
    if not relative.lower().endswith(".md"):
        return
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BridgeError(
            "frontmatter-invalid",
            f"markdown is not valid UTF-8: {shown_path(relative)}",
        ) from exc
    lines = text.splitlines()
    if not lines or lines[0] != "---":
        return
    try:
        close = lines.index("---", 1)
    except ValueError as exc:
        raise BridgeError(
            "frontmatter-invalid",
            f"frontmatter does not close: {shown_path(relative)}",
        ) from exc
    for line in lines[1:close]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not FRONTMATTER_KEY_RE.fullmatch(line):
            raise BridgeError(
                "frontmatter-invalid",
                f"frontmatter must use key: value lines: {shown_path(relative)}",
            )


def pinned_policy(worktree: Path, policy_path: Path, commit: str):
    """Load the exact policy bytes committed at *commit*."""
    from bridge_policy import PolicyError, load_policy_bytes

    expected = worktree / "bridge-policy.toml"
    require_regular_file(policy_path, expected, "bridge policy")
    current = read_regular_file(policy_path, "bridge policy")
    committed = git(
        worktree,
        ["show", f"{commit}:bridge-policy.toml"],
        category="policy-unverifiable",
        message="committed bridge policy cannot be verified",
    )
    if current != committed:
        raise BridgeError(
            "policy-changed",
            "bridge policy differs from the checked-out commit",
        )
    try:
        return load_policy_bytes(expected, current), current
    except PolicyError as exc:
        raise BridgeError("policy-invalid", f"policy invalid: {exc}") from exc


def git_blob_info(
    worktree: Path,
    commit: str,
    prefix: str,
    relative: str,
) -> tuple[str, int]:
    """Return a regular Git blob's object id and byte size."""
    tree_path = f"{prefix.rstrip('/')}/{relative}"
    raw = git(
        worktree,
        ["ls-tree", "-z", commit, "--", tree_path],
        category="blob-unreadable",
        message=f"remote file metadata is unreadable: {shown_path(relative)}",
    )
    entries = [entry for entry in raw.split(b"\0") if entry]
    if len(entries) != 1 or b"\t" not in entries[0]:
        raise BridgeError(
            "blob-unreadable",
            f"remote file metadata is invalid: {shown_path(relative)}",
        )
    metadata, _path = entries[0].split(b"\t", 1)
    fields = metadata.split()
    if (
        len(fields) != 3
        or fields[0] not in {b"100644", b"100755"}
        or fields[1] != b"blob"
    ):
        raise BridgeError(
            "remote-special-file",
            f"remote special file rejected: {shown_path(relative)}",
        )
    try:
        object_id = fields[2].decode("ascii")
        size = int(git_text(worktree, ["cat-file", "-s", object_id]))
    except (UnicodeDecodeError, ValueError) as exc:
        raise BridgeError(
            "blob-unreadable",
            f"remote file metadata is invalid: {shown_path(relative)}",
        ) from exc
    return object_id, size


def git_blob(worktree: Path, object_id: str, relative: str) -> bytes:
    """Read one already-identified Git blob without putting content in logs."""
    return git(
        worktree,
        ["cat-file", "blob", object_id],
        category="blob-unreadable",
        message=f"remote file is unreadable: {shown_path(relative)}",
    )


def build_backup(
    vault: Path,
    backup_root: Path,
    run_id: str,
    incoming: dict[str, bytes],
    expected_local: dict[str, str | None],
    *,
    read_file: Callable[..., tuple[bytes, int] | None] = secure_read_file,
) -> tuple[Path, list[dict[str, object]]]:
    """Create and verify a bridge-restore-compatible backup manifest."""
    try:
        backup_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise BridgeError("backup-failed", "backup directory cannot be created") from exc
    run_dir = backup_root / run_id
    if run_dir.exists() or run_dir.is_symlink():
        raise BridgeError(
            "backup-exists",
            "backup run id already exists; choose a fresh run id",
        )
    try:
        run_dir.mkdir(mode=0o700)
        fsync_directory(backup_root)
    except OSError as exc:
        raise BridgeError("backup-failed", "backup run directory cannot be created") from exc

    entries: list[dict[str, object]] = []
    try:
        for relative, data in sorted(incoming.items()):
            after_hash = sha256_bytes(data)
            current = read_file(vault, relative, missing_ok=True)
            expected_hash = expected_local[relative]
            if (current is None) != (expected_hash is None) or (
                current is not None and sha256_bytes(current[0]) != expected_hash
            ):
                raise BridgeError(
                    "conflict",
                    f"local file changed during import: {shown_path(relative)}",
                )
            if current is not None:
                current_data, current_mode = current
                backup_rel = f"files/{relative}"
                backup = run_dir.joinpath(*backup_rel.split("/"))
                before_hash = sha256_bytes(current_data)
                atomic_write(backup, current_data, mode=current_mode)
                if sha256_file(backup) != before_hash:
                    raise BridgeError(
                        "backup-verify-failed",
                        f"backup verification failed: {shown_path(relative)}",
                    )
                entries.append(
                    {
                        "path": relative,
                        "existed": True,
                        "backup": backup_rel,
                        "before_sha256": before_hash,
                        "after_sha256": after_hash,
                    }
                )
            else:
                entries.append(
                    {
                        "path": relative,
                        "existed": False,
                        "backup": None,
                        "before_sha256": None,
                        "after_sha256": after_hash,
                    }
                )
        manifest = {"version": 1, "run_id": run_id, "files": entries}
        encoded = (
            json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n"
        ).encode("utf-8")
        atomic_write(run_dir / "manifest.json", encoded, mode=0o600)
        if json.loads((run_dir / "manifest.json").read_text(encoding="utf-8")) != manifest:
            raise BridgeError(
                "backup-verify-failed",
                "backup manifest verification failed",
            )
    except BridgeError:
        raise
    except OSError as exc:
        raise BridgeError(
            "backup-failed",
            "backup failed; source files were not changed",
        ) from exc
    return run_dir, entries


def rollback_files(
    vault: Path,
    run_dir: Path,
    entries: list[dict[str, object]],
    applied: list[str],
    *,
    write_file: Callable[..., None] = secure_atomic_write,
    read_file: Callable[..., tuple[bytes, int] | None] = secure_read_file,
    move_file: Callable[[Path, str, Path], None] = secure_move_out,
) -> None:
    """Restore every attempted target after a failed multi-file write."""
    entry_map = {str(entry["path"]): entry for entry in entries}
    for relative in reversed(applied):
        entry = entry_map[relative]
        try:
            if entry["existed"]:
                backup = run_dir.joinpath(*str(entry["backup"]).split("/"))
                mode = stat.S_IMODE(backup.stat().st_mode)
                write_file(vault, relative, backup.read_bytes(), mode=mode)
            elif read_file(vault, relative, missing_ok=True) is not None:
                quarantine = run_dir.joinpath(
                    "failed-quarantine", *relative.split("/")
                )
                move_file(vault, relative, quarantine)
        except (OSError, BridgeError) as exc:
            raise BridgeError(
                "import-rollback-failed",
                f"failed import could not restore {shown_path(relative)}; use its verified backup",
            ) from exc


def apply_files(
    vault: Path,
    incoming: dict[str, bytes],
    entries: list[dict[str, object]],
    run_dir: Path,
    expected_local: dict[str, str | None],
    *,
    write_file: Callable[..., None] = secure_atomic_write,
    read_file: Callable[..., tuple[bytes, int] | None] = secure_read_file,
    move_file: Callable[[Path, str, Path], None] = secure_move_out,
) -> list[str]:
    """Atomically apply files, rolling every attempted target back on failure."""
    entry_map = {str(entry["path"]): entry for entry in entries}
    applied: list[str] = []
    try:
        for relative, data in sorted(incoming.items()):
            entry = entry_map[relative]
            current = read_file(vault, relative, missing_ok=True)
            expected_hash = expected_local[relative]
            if (current is None) != (expected_hash is None) or (
                current is not None and sha256_bytes(current[0]) != expected_hash
            ):
                raise BridgeError(
                    "conflict",
                    f"local file changed during import: {shown_path(relative)}",
                )
            if entry["existed"]:
                backup = run_dir.joinpath(*str(entry["backup"]).split("/"))
                mode = stat.S_IMODE(backup.stat().st_mode)
            else:
                mode = 0o600
            applied.append(relative)
            write_file(vault, relative, data, mode=mode)
            written = read_file(vault, relative, max_bytes=len(data))
            if written is None or sha256_bytes(written[0]) != entry["after_sha256"]:
                raise BridgeError(
                    "import-verify-failed",
                    f"import verification failed: {shown_path(relative)}",
                )
    except BaseException:
        rollback_files(
            vault,
            run_dir,
            entries,
            applied,
            write_file=write_file,
            read_file=read_file,
            move_file=move_file,
        )
        raise
    return applied
