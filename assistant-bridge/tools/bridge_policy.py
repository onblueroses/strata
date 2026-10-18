#!/usr/bin/env python3
"""Load and enforce the assistant bridge's path policy.

The module deliberately separates policy denials from policy-loading failures:
callers can include a denial's category in a safe file-level summary, while a
missing, unreadable, or malformed policy fails the entire operation.
"""

import argparse
import fnmatch
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import stat
import sys
import tomllib
from typing import Any, NoReturn


class PolicyError(ValueError):
    """The policy cannot be trusted or evaluated safely."""


class PathPolicyError(PolicyError):
    """A path was rejected by an otherwise valid policy."""

    def __init__(self, decision: "PolicyDecision") -> None:
        super().__init__(
            f"{decision.relative_path}: {decision.category}: {decision.detail}"
        )
        self.decision = decision


@dataclass(frozen=True, slots=True)
class PolicyDecision:
    """A non-sensitive result for one vault-relative file path."""

    relative_path: str
    allowed: bool
    category: str
    detail: str
    size: int | None = None

    @property
    def path(self) -> str:
        """Compatibility name for consumers that display the relative path."""

        return self.relative_path

    def require_allowed(self) -> "PolicyDecision":
        """Return this decision, or raise when it represents a denial."""

        if not self.allowed:
            raise PathPolicyError(self)
        return self


@dataclass(frozen=True, slots=True)
class SecretScanPolicy:
    tool: str
    on_failure: str


@dataclass(frozen=True, slots=True)
class InboundPolicy:
    mode: str
    enabled: bool
    propagate_deletions: bool
    on_conflict: str
    backup_before_write: str


@dataclass(frozen=True, slots=True)
class BridgePolicy:
    """Validated version-1 bridge policy."""

    source: Path
    version: int
    publish_root: str
    allowed_roots: tuple[PurePosixPath, ...]
    allowed_extensions: frozenset[str]
    denied_paths: tuple[PurePosixPath, ...]
    denied_names: tuple[str, ...]
    special_files: str
    max_file_bytes: int
    max_total_bytes: int
    secret_scan: SecretScanPolicy
    inbound: InboundPolicy

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> "BridgePolicy":
        """Load *path*, rejecting missing, unreadable, or invalid policies."""

        policy_path = Path(path)
        try:
            descriptor = os.open(
                policy_path,
                os.O_RDONLY
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_NONBLOCK", 0),
            )
            try:
                info = os.fstat(descriptor)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise OSError("policy is not a regular file")
            except OSError:
                os.close(descriptor)
                raise
            with os.fdopen(descriptor, "rb") as policy_file:
                document = tomllib.load(policy_file)
        except FileNotFoundError as exc:
            raise PolicyError("policy missing") from exc
        except PermissionError as exc:
            raise PolicyError("policy unreadable") from exc
        except OSError as exc:
            raise PolicyError("policy unreadable") from exc
        except tomllib.TOMLDecodeError as exc:
            raise PolicyError("policy parse error") from exc

        return cls._from_document(policy_path, document)

    @classmethod
    def from_bytes(cls, source: Path, data: bytes) -> "BridgePolicy":
        """Parse a caller-pinned policy snapshot rather than reopening its path."""
        try:
            document = tomllib.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
            raise PolicyError("policy parse error") from exc
        return cls._from_document(source, document)

    @classmethod
    def _from_document(cls, source: Path, document: dict[str, Any]) -> "BridgePolicy":
        _require_table_keys(
            document,
            "policy",
            {
                "version",
                "publish_root",
                "allow",
                "deny",
                "limits",
                "secret_scan",
                "inbound",
            },
        )

        version = _require_exact_int(document["version"], "version", minimum=1)
        if version != 1:
            raise PolicyError("unsupported policy version")
        publish_root = _policy_path(
            document["publish_root"], "publish_root"
        ).as_posix()
        if publish_root != "vault":
            raise PolicyError("publish_root must be vault")

        allow = _require_table(document["allow"], "allow")
        _require_table_keys(allow, "allow", {"roots", "extensions"})
        allowed_roots = _path_list(allow["roots"], "allow.roots", nonempty=True)
        extensions = _string_list(
            allow["extensions"], "allow.extensions", nonempty=True
        )
        normalized_extensions: list[str] = []
        for extension in extensions:
            if (
                extension.startswith(".")
                or "/" in extension
                or "\\" in extension
                or any(character in extension for character in "*?[")
                or any(ord(character) < 32 for character in extension)
            ):
                raise PolicyError("allow.extensions contains an invalid extension")
            normalized_extensions.append(extension.casefold())
        if len(set(normalized_extensions)) != len(normalized_extensions):
            raise PolicyError("allow.extensions contains duplicates")

        deny = _require_table(document["deny"], "deny")
        _require_table_keys(deny, "deny", {"paths", "names", "special_files"})
        denied_paths = _path_list(deny["paths"], "deny.paths", nonempty=False)
        denied_names = _string_list(deny["names"], "deny.names", nonempty=False)
        for pattern in denied_names:
            if (
                pattern in {".", ".."}
                or "/" in pattern
                or "\\" in pattern
                or any(ord(character) < 32 for character in pattern)
            ):
                raise PolicyError("deny.names contains an invalid pattern")
        special_files = _require_string(deny["special_files"], "deny.special_files")
        if special_files != "reject":
            raise PolicyError("deny.special_files must be reject")

        limits = _require_table(document["limits"], "limits")
        _require_table_keys(limits, "limits", {"max_file_bytes", "max_total_bytes"})
        max_file_bytes = _require_exact_int(
            limits["max_file_bytes"], "limits.max_file_bytes", minimum=1
        )
        max_total_bytes = _require_exact_int(
            limits["max_total_bytes"], "limits.max_total_bytes", minimum=1
        )
        if max_file_bytes > max_total_bytes:
            raise PolicyError("limits.max_file_bytes exceeds max_total_bytes")

        secret_scan_table = _require_table(document["secret_scan"], "secret_scan")
        _require_table_keys(secret_scan_table, "secret_scan", {"tool", "on_failure"})
        secret_tool = _require_string(secret_scan_table["tool"], "secret_scan.tool")
        if secret_tool != "gitleaks":
            raise PolicyError("secret_scan.tool must be gitleaks")
        secret_failure = _require_string(
            secret_scan_table["on_failure"], "secret_scan.on_failure"
        )
        if secret_failure != "stop":
            raise PolicyError("secret_scan.on_failure must be stop")

        inbound_table = _require_table(document["inbound"], "inbound")
        _require_table_keys(
            inbound_table,
            "inbound",
            {
                "mode",
                "enabled",
                "propagate_deletions",
                "on_conflict",
                "backup_before_write",
            },
        )
        inbound_mode = _require_string(inbound_table["mode"], "inbound.mode")
        if inbound_mode not in {"one-way", "review-gated", "continuous"}:
            raise PolicyError("inbound.mode is unsupported")
        inbound_enabled = _require_bool(inbound_table["enabled"], "inbound.enabled")
        propagate_deletions = _require_bool(
            inbound_table["propagate_deletions"], "inbound.propagate_deletions"
        )
        if propagate_deletions:
            raise PolicyError("inbound.propagate_deletions must be false")
        on_conflict = _require_string(
            inbound_table["on_conflict"], "inbound.on_conflict"
        )
        if on_conflict != "stop":
            raise PolicyError("inbound.on_conflict must be stop")
        backup_before_write = _require_string(
            inbound_table["backup_before_write"], "inbound.backup_before_write"
        )
        if backup_before_write != "required":
            raise PolicyError("inbound.backup_before_write must be required")

        return cls(
            source=source,
            version=version,
            publish_root=publish_root,
            allowed_roots=allowed_roots,
            allowed_extensions=frozenset(normalized_extensions),
            denied_paths=denied_paths,
            denied_names=denied_names,
            special_files=special_files,
            max_file_bytes=max_file_bytes,
            max_total_bytes=max_total_bytes,
            secret_scan=SecretScanPolicy(secret_tool, secret_failure),
            inbound=InboundPolicy(
                inbound_mode,
                inbound_enabled,
                propagate_deletions,
                on_conflict,
                backup_before_write,
            ),
        )

    def evaluate(
        self,
        vault_root: str | os.PathLike[str],
        relative_path: str | os.PathLike[str],
        *,
        size: int | None = None,
        require_exists: bool = True,
    ) -> PolicyDecision:
        """Evaluate one vault-relative file without reading its contents.

        ``size`` should be the incoming blob size for import checks.  Otherwise
        an existing file's ``st_size`` is used.  A nonexistent import target is
        accepted only when its incoming size is supplied.
        """

        raw_path = _path_argument(relative_path)
        relative = _runtime_path(raw_path)
        if relative is None:
            return _deny(
                "<invalid>",
                "invalid-path",
                "path is not a safe relative path",
            )
        relative_text = relative.as_posix()

        if self._matches_denied_path(relative):
            return _deny(relative_text, "denied-path", "path matches a deny rule")
        if self._matches_denied_name(relative):
            return _deny(relative_text, "denied-name", "name matches a deny rule")

        allowed_root = self._matching_allowed_root(relative)
        if allowed_root is None:
            return _deny(
                relative_text,
                "outside-allowed-root",
                "path is outside the allowed roots",
            )

        extension = relative.suffix[1:].casefold() if relative.suffix else ""
        if extension not in self.allowed_extensions:
            return _deny(
                relative_text,
                "denied-extension",
                "file type is not allowed",
            )

        if size is not None and (type(size) is not int or size < 0):
            return _deny(relative_text, "invalid-size", "file size is invalid")

        try:
            root = Path(vault_root).resolve(strict=True)
        except (FileNotFoundError, RuntimeError, OSError):
            raise PolicyError("vault root is missing or unreadable") from None
        try:
            root_stat = root.stat()
        except OSError:
            raise PolicyError("vault root is missing or unreadable") from None
        if not stat.S_ISDIR(root_stat.st_mode):
            raise PolicyError("vault root is not a directory")

        target = root.joinpath(*relative.parts)
        component_decision, target_stat = _inspect_components(root, target, relative_text)
        if component_decision is not None:
            return component_decision

        try:
            resolved_target = target.resolve(strict=False)
        except (RuntimeError, OSError):
            return _deny(relative_text, "invalid-path", "path cannot be resolved")
        if not _is_relative_to(resolved_target, root):
            return _deny(relative_text, "outside-vault", "resolved path escapes vault")

        allowed_path = root.joinpath(*allowed_root.parts)
        try:
            resolved_allowed_path = allowed_path.resolve(strict=False)
        except (RuntimeError, OSError):
            return _deny(
                relative_text,
                "outside-allowed-root",
                "allowed root cannot be resolved",
            )
        if not _is_relative_to(resolved_allowed_path, root):
            return _deny(
                relative_text,
                "outside-allowed-root",
                "allowed root escapes vault",
            )
        if self._allowed_root_is_file(allowed_root, allowed_path):
            under_allowed_root = resolved_target == resolved_allowed_path
        else:
            under_allowed_root = _is_relative_to(resolved_target, resolved_allowed_path)
        if not under_allowed_root:
            return _deny(
                relative_text,
                "outside-allowed-root",
                "resolved path escapes allowed root",
            )

        if target_stat is None:
            if require_exists:
                return _deny(relative_text, "missing", "file does not exist")
            if size is None:
                return _deny(
                    relative_text,
                    "invalid-size",
                    "incoming file size is required",
                )
        else:
            if not stat.S_ISREG(target_stat.st_mode):
                return _deny(
                    relative_text,
                    "special-file",
                    "non-regular files are rejected",
                )
            if target_stat.st_nlink != 1:
                return _deny(
                    relative_text,
                    "special-file",
                    "multiply-linked files are rejected",
                )
            if size is None:
                size = target_stat.st_size

        assert size is not None
        if size > self.max_file_bytes:
            return PolicyDecision(
                relative_text,
                False,
                "oversized",
                "file exceeds the per-file size limit",
                size,
            )
        return PolicyDecision(relative_text, True, "allowed", "path is allowed", size)

    def evaluate_path(
        self,
        vault_root: str | os.PathLike[str],
        relative_path: str | os.PathLike[str],
        *,
        size: int | None = None,
        require_exists: bool = True,
    ) -> PolicyDecision:
        """Named alias used by the publish and import jobs."""

        return self.evaluate(
            vault_root,
            relative_path,
            size=size,
            require_exists=require_exists,
        )

    def total_size_allowed(self, total_bytes: int) -> bool:
        """Return whether an already selected set fits the aggregate limit."""

        if type(total_bytes) is not int or total_bytes < 0:
            raise PolicyError("total size is invalid")
        return total_bytes <= self.max_total_bytes

    def _matches_denied_path(self, relative: PurePosixPath) -> bool:
        # Deny rules match case-insensitively so `.Obsidian` cannot slip past `.obsidian`.
        folded = PurePosixPath(*(part.casefold() for part in relative.parts))
        for denied in self.denied_paths:
            denied_folded = PurePosixPath(*(part.casefold() for part in denied.parts))
            if len(denied_folded.parts) == 1 and denied_folded.parts[0] in folded.parts:
                return True
            if folded == denied_folded or _pure_is_relative_to(folded, denied_folded):
                return True
        return False

    def _matches_denied_name(self, relative: PurePosixPath) -> bool:
        return any(
            fnmatch.fnmatchcase(component.casefold(), pattern.casefold())
            or (pattern.casefold() == ".env" and component.casefold().startswith(".env."))
            for component in relative.parts
            for pattern in self.denied_names
        )

    def _matching_allowed_root(self, relative: PurePosixPath) -> PurePosixPath | None:
        matches = (
            root
            for root in self.allowed_roots
            if relative == root or _pure_is_relative_to(relative, root)
        )
        return max(matches, key=lambda root: len(root.parts), default=None)

    def _allowed_root_is_file(self, root: PurePosixPath, path: Path) -> bool:
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            extension = root.suffix[1:].casefold() if root.suffix else ""
            return extension in self.allowed_extensions
        except OSError:
            return False
        return stat.S_ISREG(mode) or stat.S_ISLNK(mode)


def load_policy(path: str | os.PathLike[str]) -> BridgePolicy:
    """Convenience wrapper for :meth:`BridgePolicy.load`."""

    return BridgePolicy.load(path)


def load_policy_bytes(source: Path, data: bytes) -> BridgePolicy:
    """Load policy from bytes already pinned to a verified Git commit."""

    return BridgePolicy.from_bytes(source, data)


def _inspect_components(
    root: Path, target: Path, relative_text: str
) -> tuple[PolicyDecision | None, os.stat_result | None]:
    current = root
    target_stat: os.stat_result | None = None
    relative_parts = target.relative_to(root).parts
    for index, part in enumerate(relative_parts):
        current = current / part
        try:
            current_stat = current.lstat()
        except FileNotFoundError:
            return None, None
        except OSError:
            return (
                _deny(relative_text, "unreadable", "path cannot be inspected"),
                None,
            )
        if stat.S_ISLNK(current_stat.st_mode):
            return (
                _deny(relative_text, "special-file", "symbolic links are rejected"),
                None,
            )
        is_final = index == len(relative_parts) - 1
        if not is_final and not stat.S_ISDIR(current_stat.st_mode):
            return (
                _deny(relative_text, "special-file", "path parent is not a directory"),
                None,
            )
        if is_final:
            target_stat = current_stat
    return None, target_stat


def _deny(relative_path: str, category: str, detail: str) -> PolicyDecision:
    return PolicyDecision(relative_path, False, category, detail)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _pure_is_relative_to(path: PurePosixPath, parent: PurePosixPath) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _path_argument(value: str | os.PathLike[str]) -> str:
    try:
        raw = os.fspath(value)
    except TypeError:
        return "<invalid>"
    if not isinstance(raw, str):
        return "<invalid>"
    return raw


def _runtime_path(raw: str) -> PurePosixPath | None:
    if (
        not raw
        or raw.startswith("/")
        or raw.endswith("/")
        or "\\" in raw
        or "\x00" in raw
        or any(ord(character) < 32 or ord(character) == 127 for character in raw)
    ):
        return None
    raw_parts = raw.split("/")
    if any(part in {"", ".", ".."} for part in raw_parts):
        return None
    relative = PurePosixPath(raw)
    if relative.is_absolute() or not relative.parts:
        return None
    return relative


def _policy_path(value: object, field: str) -> PurePosixPath:
    text = _require_string(value, field)
    path = _runtime_path(text)
    if path is None:
        raise PolicyError(f"{field} contains an invalid relative path")
    return path


def _path_list(value: object, field: str, *, nonempty: bool) -> tuple[PurePosixPath, ...]:
    items = _string_list(value, field, nonempty=nonempty)
    paths = tuple(_policy_path(item, field) for item in items)
    if len(set(paths)) != len(paths):
        raise PolicyError(f"{field} contains duplicates")
    return paths


def _string_list(value: object, field: str, *, nonempty: bool) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise PolicyError(f"{field} must be an array")
    if nonempty and not value:
        raise PolicyError(f"{field} must not be empty")
    result: list[str] = []
    for item in value:
        result.append(_require_string(item, field))
    if len(set(result)) != len(result):
        raise PolicyError(f"{field} contains duplicates")
    return tuple(result)


def _require_table(value: object, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PolicyError(f"{field} must be a table")
    return value


def _require_table_keys(
    table: dict[str, Any], field: str, expected: set[str]
) -> None:
    actual = set(table)
    missing = expected - actual
    unknown = actual - expected
    if missing:
        raise PolicyError(f"{field} is missing required fields")
    if unknown:
        raise PolicyError(f"{field} contains unknown fields")


def _require_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or value != value.strip():
        raise PolicyError(f"{field} must be a non-empty string")
    if "\x00" in value or any(ord(character) < 32 for character in value):
        raise PolicyError(f"{field} contains control characters")
    return value


def _require_bool(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise PolicyError(f"{field} must be a boolean")
    return value


def _require_exact_int(value: object, field: str, *, minimum: int) -> int:
    if type(value) is not int or value < minimum:
        raise PolicyError(f"{field} must be an integer of at least {minimum}")
    return value


def _exit_error(message: str) -> NoReturn:
    print(message.replace("\n", " "), file=sys.stderr)
    raise SystemExit(2)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="validate and query bridge-policy.toml")
    parser.add_argument("--policy", default="bridge-policy.toml")
    parser.add_argument("--vault")
    parser.add_argument("--size", type=int)
    parser.add_argument("path", nargs="?")
    arguments = parser.parse_args(argv)

    try:
        policy = load_policy(arguments.policy)
    except PolicyError as exc:
        _exit_error(f"policy error: {exc}")

    if arguments.path is None:
        print("policy ok")
        return 0
    if arguments.vault is None:
        _exit_error("policy error: --vault is required when checking a path")

    try:
        decision = policy.evaluate(
            arguments.vault,
            arguments.path,
            size=arguments.size,
            require_exists=arguments.size is None,
        )
    except PolicyError as exc:
        _exit_error(f"policy error: {exc}")
    if decision.allowed:
        print(f"{decision.relative_path}: allowed")
        return 0
    print(
        f"{decision.relative_path}: denied ({decision.category})",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(_main())
