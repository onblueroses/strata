from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

from memory import reconcile
from memory.config import MemoryConfig


def _write_state(path: Path, card_id: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": reconcile.ACCESS_LOG_VERSION,
                "telemetry_offset": 0,
                "telemetry_identity": None,
                "cards": {
                    card_id: {
                        "last_ts": "2026-01-01T00:00:00.000Z",
                        "count": 1,
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def test_default_paths_are_resolved_at_call_time(
    memory_config: MemoryConfig, write_card: Callable[..., Path]
) -> None:
    write_card(memory_config.cards_dir, "current-card", "current")
    current = memory_config.session_state_dir / "current.json"
    stale = memory_config.session_state_dir / "stale.json"
    _write_state(current, "current-card")
    _write_state(stale, "stale-card")
    current_config = replace(memory_config, access_log=current)
    state, corrupt = reconcile.load_access_log_state(config=current_config)
    assert not corrupt
    assert sorted(state.cards) == ["current-card"]
    assert reconcile.load_access_log_state.__defaults__ is not None
    assert reconcile.load_access_log_state.__defaults__[0] is None


def test_corrupt_backup_uses_configured_backup_directory(
    memory_config: MemoryConfig,
) -> None:
    memory_config.access_log.parent.mkdir(parents=True, exist_ok=True)
    memory_config.access_log.write_text("{broken", encoding="utf-8")
    backup = reconcile.backup_corrupt_access_log(config=memory_config)
    assert backup is not None
    assert backup.parent == memory_config.backups_dir
    assert backup.read_text(encoding="utf-8") == "{broken"
    assert not memory_config.access_log.exists()
