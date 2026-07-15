#!/usr/bin/env python3
"""Incrementally reconcile retrieval telemetry into a compact access log."""

from __future__ import annotations

import argparse
import contextlib
import fcntl
import hashlib
import json
import os
import re
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from memory.config import MemoryConfig, load_config

ACCESS_LOG_VERSION = 1
TELEMETRY_HEAD_FINGERPRINT_BYTES = 512
SAFE_CARD_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")


@dataclass(frozen=True)
class TelemetryIdentity:
    inode: int
    head_sha1: str
    head_bytes: int


@dataclass
class AccessCardEntry:
    last_ts: str
    count: int


@dataclass
class AccessLogState:
    telemetry_offset: int
    cards: dict[str, AccessCardEntry]
    telemetry_identity: TelemetryIdentity | None = None


def write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=path.name, suffix=".tmp"
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def write_json_atomic(path: Path, data: Any) -> None:
    write_text_atomic(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def card_id_from_any(value: Any, config: MemoryConfig | None = None) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if "/" in raw or raw.endswith(".md"):
        raw = Path(raw).stem
    if raw == "MEMORY" or raw.startswith(".") or not SAFE_CARD_ID_RE.fullmatch(raw):
        return None
    cfg = config or load_config()
    return raw if (cfg.cards_dir / f"{raw}.md").is_file() else None


def empty_access_log_state() -> AccessLogState:
    return AccessLogState(telemetry_offset=0, cards={})


def telemetry_identity(config: MemoryConfig | None = None) -> TelemetryIdentity | None:
    cfg = config or load_config()
    try:
        stat = cfg.telemetry_file.stat()
        with cfg.telemetry_file.open("rb") as handle:
            head = handle.readline(TELEMETRY_HEAD_FINGERPRINT_BYTES)
    except OSError:
        return None
    return TelemetryIdentity(
        inode=stat.st_ino,
        head_sha1=hashlib.sha1(head).hexdigest(),
        head_bytes=len(head),
    )


def telemetry_identity_to_json(
    identity: TelemetryIdentity | None,
) -> dict[str, Any] | None:
    if identity is None:
        return None
    return {
        "inode": identity.inode,
        "head_sha1": identity.head_sha1,
        "head_bytes": identity.head_bytes,
    }


def telemetry_identity_from_json(value: Any) -> TelemetryIdentity | None:
    if not isinstance(value, dict):
        return None
    try:
        inode = int(value["inode"])
        head_bytes = int(value["head_bytes"])
    except (KeyError, TypeError, ValueError):
        return None
    head_sha1 = value.get("head_sha1")
    if (
        not isinstance(head_sha1, str)
        or not re.fullmatch(r"[a-f0-9]{40}", head_sha1)
        or head_bytes < 0
    ):
        return None
    return TelemetryIdentity(inode=inode, head_sha1=head_sha1, head_bytes=head_bytes)


def update_access_card(
    state: AccessLogState, card_id: str, timestamp: datetime
) -> None:
    formatted = timestamp.isoformat(timespec="milliseconds").replace("+00:00", "Z")
    entry = state.cards.get(card_id)
    if entry is None:
        state.cards[card_id] = AccessCardEntry(last_ts=formatted, count=1)
        return
    latest = parse_ts(entry.last_ts)
    if latest is None or timestamp > latest:
        entry.last_ts = formatted
    entry.count += 1


def _compact_legacy_rows(rows: list[Any], config: MemoryConfig) -> AccessLogState:
    state = empty_access_log_state()
    seen: set[tuple[str, str, str]] = set()
    for item in rows:
        if not isinstance(item, dict):
            continue
        card_id = card_id_from_any(item.get("card"), config)
        sid, timestamp = item.get("sid"), item.get("ts")
        if not card_id or not isinstance(sid, str) or not isinstance(timestamp, str):
            continue
        parsed = parse_ts(timestamp)
        key = (card_id, sid, timestamp)
        if parsed is not None and key not in seen:
            seen.add(key)
            update_access_card(state, card_id, parsed)
    return state


def access_log_state_to_json(state: AccessLogState) -> dict[str, Any]:
    return {
        "version": ACCESS_LOG_VERSION,
        "telemetry_offset": max(0, int(state.telemetry_offset)),
        "telemetry_identity": telemetry_identity_to_json(state.telemetry_identity),
        "cards": {
            card_id: {"last_ts": entry.last_ts, "count": max(0, int(entry.count))}
            for card_id, entry in sorted(state.cards.items())
            if parse_ts(entry.last_ts) is not None
        },
    }


def load_access_log_state(
    path: Path | None = None, config: MemoryConfig | None = None
) -> tuple[AccessLogState, bool]:
    cfg = config or load_config()
    target = path if path is not None else cfg.access_log
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except OSError:
        return empty_access_log_state(), False
    except json.JSONDecodeError:
        return empty_access_log_state(), True
    if isinstance(data, list):
        return _compact_legacy_rows(data, cfg), False
    if not isinstance(data, dict) or not isinstance(data.get("cards"), dict):
        return empty_access_log_state(), True
    try:
        offset = max(0, int(data.get("telemetry_offset", 0)))
    except (TypeError, ValueError):
        offset = 0
    cards: dict[str, AccessCardEntry] = {}
    for raw_card_id, raw_entry in data["cards"].items():
        card_id = card_id_from_any(raw_card_id, cfg)
        if card_id is None or not isinstance(raw_entry, dict):
            continue
        timestamp = raw_entry.get("last_ts")
        if not isinstance(timestamp, str) or parse_ts(timestamp) is None:
            continue
        try:
            count = max(0, int(raw_entry.get("count", 0)))
        except (TypeError, ValueError):
            count = 0
        cards[card_id] = AccessCardEntry(last_ts=timestamp, count=count)
    return (
        AccessLogState(
            telemetry_offset=offset,
            cards=cards,
            telemetry_identity=telemetry_identity_from_json(
                data.get("telemetry_identity")
            ),
        ),
        False,
    )


def load_access_rows(
    path: Path | None = None, config: MemoryConfig | None = None
) -> list[dict[str, str]]:
    state, _corrupt = load_access_log_state(path, config)
    return [
        {"card": card_id, "sid": "", "ts": entry.last_ts}
        for card_id, entry in sorted(state.cards.items())
    ]


def backup_corrupt_access_log(
    path: Path | None = None, config: MemoryConfig | None = None
) -> Path | None:
    cfg = config or load_config()
    target = path if path is not None else cfg.access_log
    if not target.exists():
        return None
    cfg.backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = cfg.backups_dir / f"access-log.corrupt-{stamp}.json"
    try:
        os.replace(target, backup)
    except OSError:
        return None
    return backup


@contextlib.contextmanager
def locked_access_log(config: MemoryConfig | None = None) -> Iterator[bool]:
    cfg = config or load_config()
    descriptor: int | None = None
    try:
        cfg.session_state_dir.mkdir(parents=True, exist_ok=True)
        descriptor = os.open(cfg.access_lock, os.O_CREAT | os.O_RDWR, 0o600)
        fcntl.flock(descriptor, fcntl.LOCK_EX)
    except OSError:
        if descriptor is not None:
            with contextlib.suppress(OSError):
                os.close(descriptor)
        yield False
        return
    try:
        yield True
    finally:
        with contextlib.suppress(OSError):
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)


def ingest_telemetry_tail(
    state: AccessLogState, config: MemoryConfig | None = None
) -> int:
    cfg = config or load_config()
    try:
        telemetry_size = cfg.telemetry_file.stat().st_size
    except OSError:
        state.telemetry_offset = 0
        state.telemetry_identity = None
        return 0
    current_identity = telemetry_identity(cfg)
    if current_identity is None:
        state.telemetry_offset = 0
        state.telemetry_identity = None
        return 0
    if state.telemetry_identity is None and state.telemetry_offset > 0:
        state.cards = {}
        offset = 0
    elif state.telemetry_identity != current_identity:
        offset = 0
    else:
        offset = (
            state.telemetry_offset if state.telemetry_offset <= telemetry_size else 0
        )
    additions = 0
    try:
        with cfg.telemetry_file.open("rb") as handle:
            handle.seek(offset)
            while True:
                line_start = handle.tell()
                raw_line = handle.readline()
                if not raw_line:
                    break
                if not raw_line.endswith(b"\n"):
                    handle.seek(line_start)
                    break
                try:
                    event = json.loads(raw_line.decode("utf-8", "replace"))
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict) or event.get("kind") != "kb_query":
                    continue
                timestamp, returned_ids = event.get("ts"), event.get("returned_ids")
                if not isinstance(timestamp, str) or not isinstance(returned_ids, list):
                    continue
                parsed = parse_ts(timestamp)
                if parsed is None:
                    continue
                for raw_card_id in returned_ids:
                    card_id = card_id_from_any(raw_card_id, cfg)
                    if card_id is not None:
                        update_access_card(state, card_id, parsed)
                        additions += 1
            state.telemetry_offset = handle.tell()
            state.telemetry_identity = current_identity
    except OSError:
        return additions
    return additions


def update_access_log(config: MemoryConfig | None = None) -> int:
    cfg = config or load_config()
    with locked_access_log(cfg) as locked:
        if not locked:
            return 0
        state, corrupt = load_access_log_state(config=cfg)
        if corrupt:
            backup = backup_corrupt_access_log(config=cfg)
            if backup is None and cfg.access_log.exists():
                return 0
            state = empty_access_log_state()
        additions = ingest_telemetry_tail(state, cfg)
        write_json_atomic(cfg.access_log, access_log_state_to_json(state))
        return additions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--access-log", action="store_true")
    parser.parse_args(argv)
    cfg = load_config()
    additions = update_access_log(cfg)
    print("access_log=memory/session-state/access-log.json")
    print(f"added_rows={additions}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
