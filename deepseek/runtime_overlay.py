#!/usr/bin/env python3
"""Create one exclusive DSH runtime overlay for an authorized primary run."""

from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path
import stat
from typing import Any, Never


MODELS = frozenset({"deepseek-v4-flash", "deepseek-v4-pro"})


def reject_json_constant(value: str) -> Never:
    raise ValueError(f"non-finite JSON number: {value}")


def finite_json_float(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite JSON number: {value}")
    return parsed


def reject_duplicate_json_keys(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def overlay_data(sessions: Path, model: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "agent-default-model",
            "config": {"provider": "deepseek-official", "model": model},
        },
        {"id": "session-persistence-jsonl", "config": {"root": str(sessions)}},
    ]


def copy_static_overlay(source: Path, destination: Path) -> None:
    """Copy one managed static overlay into an exclusive per-run inode."""
    if not source.is_absolute() or not destination.is_absolute():
        raise ValueError("static overlay source and destination must be absolute")
    if destination.parent.is_symlink() or not destination.parent.is_dir():
        raise ValueError(
            f"static overlay parent is not a regular directory: {destination.parent}"
        )
    read_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        source_descriptor = os.open(source, read_flags)
    except OSError as exc:
        raise ValueError(f"static overlay is not a regular file: {source}: {exc}") from exc
    try:
        before = os.fstat(source_descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise ValueError(f"static overlay is not a regular file: {source}")
        with os.fdopen(os.dup(source_descriptor), "rb") as source_handle:
            content = source_handle.read()
        after = os.fstat(source_descriptor)
    finally:
        os.close(source_descriptor)
    identity = lambda value: (  # noqa: E731 - compact immutable stat projection.
        value.st_dev,
        value.st_ino,
        value.st_mode,
        value.st_size,
        value.st_mtime_ns,
    )
    if identity(before) != identity(after):
        raise ValueError(f"static overlay changed while being copied: {source}")
    try:
        current = source.lstat()
    except OSError as exc:
        raise ValueError(f"static overlay changed while being copied: {source}") from exc
    if (current.st_dev, current.st_ino) != (after.st_dev, after.st_ino):
        raise ValueError(f"static overlay changed while being copied: {source}")

    write_flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    destination_descriptor = os.open(destination, write_flags, 0o600)
    with os.fdopen(destination_descriptor, "wb") as destination_handle:
        destination_handle.write(content)


def read_overlay(path: Path, model: str) -> Path:
    """Validate the exact launcher-generated overlay and return its session root."""
    if model not in MODELS:
        raise ValueError(f"unsupported DeepSeek model: {model}")
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"runtime overlay is not a regular file: {path}")
    sessions = path.parent / "sessions"
    try:
        data = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=reject_json_constant,
            parse_float=finite_json_float,
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (OSError, UnicodeError, ValueError) as exc:
        raise ValueError(f"runtime overlay is unreadable: {path}: {exc}") from exc
    if data != overlay_data(sessions, model):
        raise ValueError(
            "runtime overlay does not match the exact official provider, model, "
            "and per-run session contract"
        )
    return sessions


def write_overlay(destination: Path, sessions: Path, model: str) -> None:
    if model not in MODELS:
        raise ValueError(f"unsupported DeepSeek model: {model}")
    if not destination.is_absolute() or not sessions.is_absolute():
        raise ValueError("runtime overlay and session paths must be absolute")
    if destination.parent.is_symlink() or not destination.parent.is_dir():
        raise ValueError(
            f"runtime overlay parent is not a regular directory: {destination.parent}"
        )
    flags = (
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )
    descriptor = os.open(destination, flags, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
        json.dump(overlay_data(sessions, model), handle, indent=2, allow_nan=False)
        handle.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--sessions", type=Path, required=True)
    parser.add_argument("--model", choices=sorted(MODELS), required=True)
    parser.add_argument("--static-source", type=Path)
    parser.add_argument("--static-destination", type=Path)
    arguments = parser.parse_args()
    try:
        if (arguments.static_source is None) != (
            arguments.static_destination is None
        ):
            raise ValueError(
                "static source and destination must be supplied together"
            )
        if arguments.static_source is not None:
            copy_static_overlay(
                arguments.static_source, arguments.static_destination
            )
        write_overlay(arguments.destination, arguments.sessions, arguments.model)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
