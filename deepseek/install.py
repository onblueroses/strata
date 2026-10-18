#!/usr/bin/env python3
"""Install the isolated DeepSeek primary operating layer."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tempfile
from collections.abc import Iterator
from typing import Any


MANIFEST_NAME = ".managed-deepseek-primary.json"
MANIFEST_SCHEMA = 1
PRIMARY_HOME_TOKEN = "__DSH_PRIMARY_HOME__"
SHA256_DIGEST = re.compile(r"^[0-9a-f]{64}$", re.ASCII)
NATIVE_CHILD_SURFACES = (
    "subagent",
    "subagent-spawn-in-process",
    "subagent-fork-in-process",
    "tool-subagent-control",
    "tool-subagent-list-agents",
    "tool-subagent",
    "tool-subagent-fork",
    "tool-subagent-report",
    "workflow-worker-thread",
    "tool-workflow",
    "tool-ralph",
)


@dataclass(frozen=True)
class Artifact:
    source: Path
    target: Path
    mode: int = 0o600
    render_primary_home: bool = False


@dataclass(frozen=True)
class Snapshot:
    exists: bool
    digest: str | None = None
    device: int | None = None
    inode: int | None = None
    mode: int | None = None
    size: int | None = None
    modified_ns: int | None = None


@dataclass
class Commit:
    destination: Path
    backup: Path | None
    before: Snapshot
    desired_digest: str
    installed: Snapshot | None = None


def source_artifacts(source_root: Path) -> list[Artifact]:
    repo_root = source_root.parent
    return [
        Artifact(source_root / "AGENTS.md", Path("AGENTS.md")),
        Artifact(source_root / "README.md", Path("README.md")),
        Artifact(source_root / "startup.py", Path("startup.py"), 0o700),
        Artifact(
            source_root / "runtime_overlay.py", Path("runtime_overlay.py"), 0o700
        ),
        Artifact(source_root / "doctor.py", Path("doctor.py"), 0o700),
        Artifact(source_root / "install.py", Path("install.py"), 0o700),
        Artifact(
            source_root / "primary-overlay.yml",
            Path("primary-overlay.yml"),
            render_primary_home=True,
        ),
        Artifact(
            source_root / "profile" / "headless" / "package.json",
            Path("profiles/headless/package.json"),
        ),
        Artifact(
            source_root / "profile" / "headless" / "cordis.patch.yml",
            Path("profiles/headless/cordis.patch.yml"),
        ),
        Artifact(
            source_root / "profile" / "headless" / "pnpm-workspace.yaml",
            Path("profiles/headless/pnpm-workspace.yaml"),
        ),
        Artifact(
            repo_root / "delegation" / "wrappers" / "dsh-primary",
            Path("bin/dsh-primary"),
            0o700,
        ),
        Artifact(
            source_root / "skills" / "pickup-context" / "SKILL.md",
            Path("skills/pickup-context/SKILL.md"),
        ),
        Artifact(
            source_root / "skills" / "close-session" / "SKILL.md",
            Path("skills/close-session/SKILL.md"),
        ),
    ]


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def artifact_bytes(artifact: Artifact, target_root: Path) -> bytes:
    content = artifact.source.read_bytes()
    if not artifact.render_primary_home:
        return content
    text = content.decode("utf-8")
    if text.count(PRIMARY_HOME_TOKEN) != 3:
        raise RuntimeError(
            f"primary overlay must contain exactly three home tokens: {artifact.source}"
        )
    # The placeholder sits inside YAML single quotes. Doubling an apostrophe is
    # YAML's literal-string escape and keeps a caller-supplied target as data.
    rendered_home = str(target_root).replace("'", "''")
    return text.replace(PRIMARY_HOME_TOKEN, rendered_home).encode("utf-8")


def lexists(path: Path) -> bool:
    return os.path.lexists(path)


def snapshot(path: Path) -> Snapshot:
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except FileNotFoundError:
        return Snapshot(exists=False)
    except OSError as exc:
        raise RuntimeError(f"managed path is not safely readable: {path}: {exc}") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise RuntimeError(f"managed path is not a regular file: {path}")
        with os.fdopen(os.dup(descriptor), "rb") as handle:
            digest = hashlib.file_digest(handle, "sha256").hexdigest()
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    def identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
        return (
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_size,
            value.st_mtime_ns,
        )
    if identity(before) != identity(after):
        raise RuntimeError(f"managed path changed while being read: {path}")
    try:
        current = path.lstat()
    except FileNotFoundError as exc:
        raise RuntimeError(f"managed path changed while being read: {path}") from exc
    if (current.st_dev, current.st_ino) != (after.st_dev, after.st_ino):
        raise RuntimeError(f"managed path changed while being read: {path}")
    return Snapshot(
        exists=True,
        digest=digest,
        device=after.st_dev,
        inode=after.st_ino,
        mode=after.st_mode,
        size=after.st_size,
        modified_ns=after.st_mtime_ns,
    )


def require_snapshot(path: Path, expected: Snapshot) -> None:
    if snapshot(path) != expected:
        raise RuntimeError(f"managed path changed after preflight: {path}")


def require_desired_artifacts(
    target_root: Path, artifacts: list[Artifact], desired: dict[str, str]
) -> None:
    for artifact in artifacts:
        destination = target_root / artifact.target
        current = snapshot(destination)
        relative = artifact.target.as_posix()
        if (
            not current.exists
            or current.digest != desired[relative]
            or current.mode is None
            or stat.S_IMODE(current.mode) != artifact.mode
        ):
            raise RuntimeError(f"managed path changed after preflight: {destination}")


def validate_target_root(target_root: Path) -> None:
    if target_root in {Path("/"), Path.home()}:
        raise RuntimeError(f"refusing broad target root: {target_root}")
    if any(ord(character) < 32 for character in str(target_root)):
        raise RuntimeError("target root contains a control character")
    if lexists(target_root) and (target_root.is_symlink() or not target_root.is_dir()):
        raise RuntimeError(f"target root is not a regular directory: {target_root}")


def validate_existing_ancestors(path: Path, label: str) -> None:
    current = path
    while True:
        if lexists(current) and current.is_symlink():
            raise RuntimeError(f"{label} has a symlink ancestor: {current}")
        if current == current.parent:
            return
        current = current.parent


def validate_parent(root: Path, relative: Path, *, create: bool) -> None:
    current = root
    for part in relative.parts:
        if part in {"", ".", ".."}:
            raise RuntimeError(f"invalid managed path component: {relative}")
        current = current / part
        if create and not lexists(current):
            try:
                current.mkdir()
            except FileExistsError:
                pass
        if lexists(current) and (current.is_symlink() or not current.is_dir()):
            raise RuntimeError(f"managed parent is not a regular directory: {current}")


def validate_sources(source_root: Path, artifacts: list[Artifact]) -> None:
    errors: list[str] = []
    targets: set[str] = set()
    for artifact in artifacts:
        relative = artifact.target.as_posix()
        if artifact.target.is_absolute() or ".." in artifact.target.parts:
            errors.append(f"invalid target: {relative}")
        if relative in targets:
            errors.append(f"duplicate target: {relative}")
        targets.add(relative)
        if artifact.source.is_symlink() or not artifact.source.is_file():
            errors.append(f"source is not a regular file: {artifact.source}")
    if errors:
        raise RuntimeError("source validation failed:\n- " + "\n- ".join(errors))

    agents = (source_root / "AGENTS.md").read_text(encoding="utf-8")
    overlay = (source_root / "primary-overlay.yml").read_text(encoding="utf-8")
    launcher = (source_root.parent / "delegation" / "wrappers" / "dsh-primary").read_text(
        encoding="utf-8"
    )
    if "user-facing primary DeepSeek" not in agents:
        errors.append("AGENTS.md lacks the primary authority marker")
    if "Delegated DeepSeek agents never call `memo note`" not in agents:
        errors.append("AGENTS.md lacks the delegated OptMem boundary")
    if "deepseek-official" not in overlay:
        errors.append("primary overlay does not pin the official provider")
    overlay_lines = {line.strip() for line in overlay.splitlines()}
    for endpoint in (
        "baseURL: https://api.deepseek.com",
        "baseURL: https://api.deepseek.com/anthropic/v1",
    ):
        if endpoint not in overlay_lines:
            errors.append(f"primary overlay does not pin the official endpoint: {endpoint}")
    if overlay.count(PRIMARY_HOME_TOKEN) != 3:
        errors.append("primary overlay has the wrong home-token count")
    for identifier in NATIVE_CHILD_SURFACES:
        marker = f"- id: {identifier}\n  disabled: true"
        if marker not in overlay:
            errors.append(f"primary overlay does not disable {identifier}")
    if "--confirm-spend" not in launcher:
        errors.append("launcher lacks the pre-spend confirmation gate")
    # The constitution names the forbidden provider in a negative policy. Only
    # executable launch/configuration surfaces must contain no selector for it.
    executable_surfaces = "\n".join([overlay, launcher])
    if "prime-inference" in executable_surfaces.lower():
        errors.append("DeepSeek primary launch surface references the forbidden provider")
    if errors:
        raise RuntimeError("source validation failed:\n- " + "\n- ".join(errors))


def reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def reject_duplicate_json_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_manifest(path: Path) -> dict[str, str]:
    if not lexists(path):
        return {}
    try:
        data = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=reject_json_constant,
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise RuntimeError(f"managed manifest is unreadable: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"managed manifest has an unsupported shape: {path}")
    files = data.get("files")
    if (
        type(data.get("schema")) is not int
        or data.get("schema") != MANIFEST_SCHEMA
        or not isinstance(files, dict)
    ):
        raise RuntimeError(f"managed manifest has an unsupported shape: {path}")
    if not all(
        isinstance(key, str)
        and isinstance(value, str)
        and SHA256_DIGEST.fullmatch(value)
        for key, value in files.items()
    ):
        raise RuntimeError(f"managed manifest has invalid file hashes: {path}")
    for relative in files:
        candidate = Path(relative)
        if (
            not relative
            or candidate.is_absolute()
            or candidate.as_posix() != relative
            or any(part in {"", ".", ".."} for part in candidate.parts)
        ):
            raise RuntimeError(f"managed manifest has an invalid managed path: {relative}")
    return dict(files)


def manifest_bytes(source_root: Path, desired: dict[str, str]) -> bytes:
    data = {
        "schema": MANIFEST_SCHEMA,
        "source": str(source_root),
        "installed_at": datetime.now().astimezone().isoformat(),
        "files": dict(sorted(desired.items())),
    }
    return (
        json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n"
    ).encode("utf-8")


@contextmanager
def install_lock(target_root: Path) -> Iterator[None]:
    target_root.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = target_root.parent / ".dsh-primary-install.lock"
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    descriptor = os.open(lock_path, flags, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)


def launcher_state(launcher_link: Path, expected_target: Path) -> tuple[str, str | None]:
    if not lexists(launcher_link):
        return ("absent", None)
    if not launcher_link.is_symlink():
        return ("invalid", None)
    target = os.readlink(launcher_link)
    if target != str(expected_target):
        return ("other", target)
    return ("managed", target)


def clean_created_directories(
    target_root: Path, artifacts: list[Artifact]
) -> list[str]:
    """Remove only empty directories created for managed artifacts."""
    directories = {target_root}
    for artifact in artifacts:
        parent = (target_root / artifact.target).parent
        while parent != target_root:
            directories.add(parent)
            parent = parent.parent

    failures: list[str] = []
    for directory in sorted(directories, key=lambda path: len(path.parts), reverse=True):
        try:
            directory.rmdir()
        except FileNotFoundError:
            continue
        except OSError as exc:
            if exc.errno not in {errno.EEXIST, errno.ENOTEMPTY}:
                failures.append(
                    f"{directory}: rollback directory cleanup failed: {exc}"
                )
    if lexists(target_root):
        failures.append(
            f"{target_root}: contains unowned or concurrently changed content after rollback"
        )
    return failures


def preflight(
    target_root: Path,
    source_root: Path,
    artifacts: list[Artifact],
    launcher_link: Path,
) -> tuple[dict[str, str], list[Artifact], dict[str, Snapshot], Snapshot]:
    manifest_path = target_root / MANIFEST_NAME
    manifest_before = snapshot(manifest_path)
    previous = load_manifest(manifest_path)
    require_snapshot(manifest_path, manifest_before)
    if manifest_before.exists:
        root_mode = stat.S_IMODE(target_root.lstat().st_mode)
        manifest_mode = (
            stat.S_IMODE(manifest_before.mode)
            if manifest_before.mode is not None
            else None
        )
        if root_mode != 0o700:
            raise RuntimeError(
                f"managed target root mode has local modifications: {target_root}"
            )
        if manifest_mode != 0o600:
            raise RuntimeError(
                f"managed manifest mode has local modifications: {manifest_path}"
            )
    desired = {
        artifact.target.as_posix(): sha256_bytes(artifact_bytes(artifact, target_root))
        for artifact in artifacts
    }
    retired_targets = set(previous) - set(desired)
    if retired_targets:
        raise RuntimeError(
            "managed manifest contains retired targets that require an explicit migration:\n- "
            + "\n- ".join(sorted(retired_targets))
        )

    changes: list[Artifact] = []
    snapshots: dict[str, Snapshot] = {}
    collisions: list[str] = []
    for artifact in artifacts:
        relative = artifact.target.as_posix()
        destination = target_root / artifact.target
        current = snapshot(destination)
        snapshots[relative] = current
        if not current.exists:
            changes.append(artifact)
        elif relative not in previous:
            if (
                current.digest != desired[relative]
                or current.mode is None
                or stat.S_IMODE(current.mode) != artifact.mode
            ):
                collisions.append(f"{relative}: unmanaged target already exists")
        elif current.digest != previous[relative]:
            collisions.append(f"{relative}: installed target has local modifications")
        elif current.mode is None or stat.S_IMODE(current.mode) != artifact.mode:
            collisions.append(f"{relative}: installed target mode has local modifications")
        elif current.digest != desired[relative]:
            changes.append(artifact)
    if collisions:
        raise RuntimeError("preflight refused installation:\n- " + "\n- ".join(collisions))

    expected_launcher = target_root / "bin" / "dsh-primary"
    state, existing_target = launcher_state(launcher_link, expected_launcher)
    if state in {"invalid", "other"}:
        detail = "not a symlink" if state == "invalid" else f"points to {existing_target}"
        raise RuntimeError(f"launcher path is unmanaged: {launcher_link} {detail}")
    return desired, changes, snapshots, manifest_before


def install(
    target_root: Path,
    source_root: Path,
    launcher_link: Path,
    *,
    check_only: bool,
) -> int:
    target_root = target_root.expanduser().absolute()
    source_root = source_root.expanduser().absolute()
    launcher_link = launcher_link.expanduser().absolute()
    validate_target_root(target_root)
    validate_existing_ancestors(target_root.parent, "target root")
    validate_existing_ancestors(launcher_link.parent, "launcher path")
    artifacts = source_artifacts(source_root)
    validate_sources(source_root, artifacts)
    for artifact in artifacts:
        validate_parent(target_root, artifact.target.parent, create=False)

    with install_lock(target_root):
        desired, changes, destination_snapshots, manifest_before = preflight(
            target_root, source_root, artifacts, launcher_link
        )
        expected_launcher = target_root / "bin" / "dsh-primary"
        launcher_needs_install = launcher_state(launcher_link, expected_launcher)[0] == "absent"
        previous = load_manifest(target_root / MANIFEST_NAME)
        if not changes and previous == desired and not launcher_needs_install:
            print(f"DeepSeek primary layer already current at {target_root}")
            return 0
        if check_only:
            print(
                f"Preflight passed: {len(changes)} managed file changes; "
                f"launcher change={str(launcher_needs_install).lower()}"
            )
            return 0

        transaction = Path(
            tempfile.mkdtemp(prefix=".dsh-primary-install-", dir=str(target_root.parent))
        )
        staged_root = transaction / "staged"
        backup_root = transaction / "backup"
        commits: list[Commit] = []
        target_created = not target_root.exists()
        launcher_committed = False
        preserve_transaction = False
        try:
            for artifact in changes:
                staged = staged_root / artifact.target
                staged.parent.mkdir(parents=True, exist_ok=True)
                staged.write_bytes(artifact_bytes(artifact, target_root))
                staged.chmod(artifact.mode)
                if snapshot(staged).digest != desired[artifact.target.as_posix()]:
                    raise RuntimeError(f"staged hash mismatch: {artifact.target}")

            target_root.mkdir(parents=True, exist_ok=True, mode=0o700)
            target_root.chmod(0o700)
            for artifact in changes:
                relative = artifact.target.as_posix()
                destination = target_root / artifact.target
                before = destination_snapshots[relative]
                require_snapshot(destination, before)
                validate_parent(target_root, artifact.target.parent, create=True)
                backup: Path | None = None
                if before.exists:
                    backup = backup_root / artifact.target
                    backup.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(destination, backup)
                    require_snapshot(destination, before)
                record = Commit(destination, backup, before, desired[relative])
                commits.append(record)
                os.replace(staged_root / artifact.target, destination)
                installed = snapshot(destination)
                if installed.digest != desired[relative]:
                    raise RuntimeError(f"destination changed during commit: {destination}")
                record.installed = installed

            manifest_path = target_root / MANIFEST_NAME
            require_snapshot(manifest_path, manifest_before)
            staged_manifest = staged_root / MANIFEST_NAME
            staged_manifest.parent.mkdir(parents=True, exist_ok=True)
            staged_manifest.write_bytes(manifest_bytes(source_root, desired))
            staged_manifest.chmod(0o600)
            manifest_backup: Path | None = None
            if manifest_before.exists:
                manifest_backup = backup_root / MANIFEST_NAME
                manifest_backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(manifest_path, manifest_backup)
                require_snapshot(manifest_path, manifest_before)
            for record in commits:
                if record.installed is None:
                    raise RuntimeError(f"commit was not observed: {record.destination}")
                require_snapshot(record.destination, record.installed)
            require_desired_artifacts(target_root, artifacts, desired)
            manifest_digest = sha256_bytes(staged_manifest.read_bytes())
            manifest_record = Commit(
                manifest_path,
                manifest_backup,
                manifest_before,
                manifest_digest,
            )
            commits.append(manifest_record)
            os.replace(staged_manifest, manifest_path)
            installed_manifest = snapshot(manifest_path)
            if installed_manifest.digest != manifest_digest:
                raise RuntimeError(f"manifest changed during commit: {manifest_path}")
            manifest_record.installed = installed_manifest

            if launcher_needs_install:
                launcher_link.parent.mkdir(parents=True, exist_ok=True)
                if launcher_link.parent.is_symlink():
                    raise RuntimeError(f"launcher parent is a symlink: {launcher_link.parent}")
                temporary_link = launcher_link.parent / f".dsh-primary-link-{os.getpid()}"
                if lexists(temporary_link):
                    raise RuntimeError(f"temporary launcher path already exists: {temporary_link}")
                os.symlink(expected_launcher, temporary_link)
                if lexists(launcher_link):
                    temporary_link.unlink()
                    raise RuntimeError(f"launcher path changed after preflight: {launcher_link}")
                os.replace(temporary_link, launcher_link)
                launcher_committed = True

            for record in commits:
                if record.installed is None:
                    raise RuntimeError(f"commit was not observed: {record.destination}")
                require_snapshot(record.destination, record.installed)
            require_desired_artifacts(target_root, artifacts, desired)
            if launcher_state(launcher_link, expected_launcher)[0] != "managed":
                raise RuntimeError(f"launcher changed during commit: {launcher_link}")
        except BaseException as error:
            rollback_conflicts: list[str] = []
            if launcher_committed:
                state = launcher_state(launcher_link, expected_launcher)[0]
                if state == "managed":
                    try:
                        launcher_link.unlink()
                    except OSError as rollback_error:
                        rollback_conflicts.append(
                            f"{launcher_link}: rollback failed: {rollback_error}"
                        )
                elif state != "absent":
                    rollback_conflicts.append(
                        f"{launcher_link}: changed after the installer committed it"
                    )
            for record in reversed(commits):
                try:
                    current = snapshot(record.destination)
                    if record.installed is not None:
                        installer_bytes_are_live = current == record.installed
                    elif current == record.before:
                        continue
                    else:
                        installer_bytes_are_live = (
                            current.exists and current.digest == record.desired_digest
                        )
                    if not installer_bytes_are_live:
                        rollback_conflicts.append(
                            f"{record.destination}: changed after the installer committed it"
                        )
                        continue
                    if record.backup is None:
                        record.destination.unlink()
                    else:
                        os.replace(record.backup, record.destination)
                except (OSError, RuntimeError) as rollback_error:
                    rollback_conflicts.append(
                        f"{record.destination}: rollback failed: {rollback_error}"
                    )
            if target_created:
                rollback_conflicts.extend(
                    clean_created_directories(target_root, artifacts)
                )
            if rollback_conflicts:
                preserve_transaction = True
                raise RuntimeError(
                    "installation failed and rollback incomplete; live bytes were preserved "
                    f"where ownership was uncertain; recovery artifacts remain at {transaction}:\n- "
                    + "\n- ".join(rollback_conflicts)
                ) from error
            raise
        finally:
            if not preserve_transaction:
                shutil.rmtree(transaction, ignore_errors=True)

        print(f"Installed {len(changes)} managed files under {target_root}")
        return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target",
        type=Path,
        default=Path.home() / ".local" / "share" / "dsh-primary",
        help="isolated DeepSeek primary root",
    )
    parser.add_argument(
        "--launcher-link",
        type=Path,
        default=Path.home() / ".local" / "bin" / "dsh-primary",
        help="managed launcher symlink",
    )
    parser.add_argument("--check", action="store_true", help="validate without writing")
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    try:
        return install(
            arguments.target,
            Path(__file__).resolve().parent,
            arguments.launcher_link,
            check_only=arguments.check,
        )
    except (OSError, RuntimeError, UnicodeError) as exc:
        print(f"sync-deepseek-primary: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
