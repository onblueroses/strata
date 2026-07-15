from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path

from memory import reconcile
from memory.config import MemoryConfig


def _event(timestamp: str, returned_ids: list[str]) -> str:
    return (
        json.dumps(
            {
                "ts": timestamp,
                "kind": "kb_query",
                "query": "synthetic query",
                "returned_ids": returned_ids,
            }
        )
        + "\n"
    )


def _state(config: MemoryConfig) -> dict:
    return json.loads(config.access_log.read_text(encoding="utf-8"))


def _counts(config: MemoryConfig) -> dict[str, int]:
    return {
        card_id: int(entry["count"])
        for card_id, entry in _state(config)["cards"].items()
    }


def test_incremental_tail_and_rotation_identity(
    memory_config: MemoryConfig, write_card: Callable[..., Path]
) -> None:
    for card_id in ("alpha-card", "beta-card", "gamma-card"):
        write_card(memory_config.cards_dir, card_id, card_id)
    memory_config.telemetry_dir.mkdir(parents=True, exist_ok=True)
    memory_config.telemetry_file.write_text(
        _event("2026-01-01T00:00:00.000Z", ["alpha-card", "beta-card"])
        + _event("2026-01-01T00:01:00.000Z", ["alpha-card"]),
        encoding="utf-8",
    )
    assert reconcile.update_access_log(memory_config) == 3
    assert _counts(memory_config) == {"alpha-card": 2, "beta-card": 1}
    first_offset = _state(memory_config)["telemetry_offset"]

    with memory_config.telemetry_file.open("a", encoding="utf-8") as handle:
        handle.write(_event("2026-01-01T00:02:00.000Z", ["gamma-card"]))
    assert reconcile.update_access_log(memory_config) == 1
    assert _counts(memory_config) == {
        "alpha-card": 2,
        "beta-card": 1,
        "gamma-card": 1,
    }
    assert _state(memory_config)["telemetry_offset"] > first_offset
    assert reconcile.update_access_log(memory_config) == 0

    replacement = memory_config.telemetry_file.with_suffix(".new")
    replacement.write_text(
        _event("2026-01-02T00:00:00.000Z", ["beta-card", "gamma-card"]),
        encoding="utf-8",
    )
    old_inode = memory_config.telemetry_file.stat().st_ino
    os.replace(replacement, memory_config.telemetry_file)
    assert memory_config.telemetry_file.stat().st_ino != old_inode
    assert reconcile.update_access_log(memory_config) == 2
    assert _counts(memory_config) == {
        "alpha-card": 2,
        "beta-card": 2,
        "gamma-card": 2,
    }
    assert reconcile.update_access_log(memory_config) == 0


def test_partial_tail_waits_for_newline(
    memory_config: MemoryConfig, write_card: Callable[..., Path]
) -> None:
    write_card(memory_config.cards_dir, "alpha-card", "alpha")
    memory_config.telemetry_dir.mkdir(parents=True, exist_ok=True)
    partial = _event("2026-01-01T00:00:00.000Z", ["alpha-card"]).rstrip("\n")
    memory_config.telemetry_file.write_text(partial, encoding="utf-8")
    assert reconcile.update_access_log(memory_config) == 0
    assert _counts(memory_config) == {}
    with memory_config.telemetry_file.open("a", encoding="utf-8") as handle:
        handle.write("\n")
    assert reconcile.update_access_log(memory_config) == 1
    assert _counts(memory_config) == {"alpha-card": 1}


def test_corrupt_state_is_backed_up_then_rebuilt(
    memory_config: MemoryConfig, write_card: Callable[..., Path]
) -> None:
    write_card(memory_config.cards_dir, "alpha-card", "alpha")
    memory_config.telemetry_dir.mkdir(parents=True, exist_ok=True)
    memory_config.telemetry_file.write_text(
        _event("2026-01-01T00:00:00.000Z", ["alpha-card"]),
        encoding="utf-8",
    )
    memory_config.access_log.parent.mkdir(parents=True, exist_ok=True)
    memory_config.access_log.write_text("{invalid", encoding="utf-8")
    assert reconcile.update_access_log(memory_config) == 1
    assert _counts(memory_config) == {"alpha-card": 1}
    backups = list(memory_config.backups_dir.glob("access-log.corrupt-*.json"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "{invalid"
