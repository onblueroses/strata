"""Environment-backed path and feature configuration for the memory subsystem."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


def _enabled(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


def _root(env: Mapping[str, str], name: str, fallback: Path) -> Path:
    raw = env.get(name)
    return Path(raw).expanduser() if raw else fallback


@dataclass(frozen=True)
class MemoryConfig:
    """Fully resolved memory paths and opt-in features.

    Paths may be absolute internally. Public results use logical IDs or paths
    relative to ``state_dir`` and ``kb_dir``.
    """

    strata_home: Path
    kb_dir: Path
    state_dir: Path
    memory_dir: Path
    cards_dir: Path
    cache_dir: Path
    session_state_dir: Path
    backups_dir: Path
    telemetry_dir: Path
    telemetry_file: Path
    memory_eval_file: Path
    access_log: Path
    access_lock: Path
    memory_index: Path
    index_proposal: Path
    embedding_model: str | None
    telemetry_enabled: bool
    digest_enabled: bool

    def ensure_state_dirs(self) -> None:
        """Create the bounded mutable directories used by the subsystem."""

        for path in (
            self.cards_dir,
            self.cache_dir,
            self.session_state_dir,
            self.backups_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)
        if self.telemetry_enabled:
            self.telemetry_dir.mkdir(parents=True, exist_ok=True)


def load_config(env: Mapping[str, str] | None = None) -> MemoryConfig:
    """Resolve configuration from an environment mapping.

    ``STRATA_HOME`` defaults to ``$HOME/.strata``. The knowledge and state
    roots then follow Strata's normal ``workspace`` and ``workspace/state``
    defaults. An embedding model is disabled when unset or left as a
    ``<PICK_...>`` placeholder.
    """

    values = os.environ if env is None else env
    home = Path(values.get("HOME") or Path.home())
    strata_home = _root(values, "STRATA_HOME", home / ".strata")
    kb_dir = _root(values, "KB_DIR", strata_home / "workspace")
    state_dir = _root(values, "STATE_DIR", kb_dir / "state")
    memory_dir = state_dir / "memory"
    cards_dir = memory_dir / "cards"
    cache_dir = memory_dir / "cache"
    session_state_dir = memory_dir / "session-state"
    backups_dir = memory_dir / "backups"
    telemetry_dir = state_dir / "telemetry"

    raw_model = values.get("STRATA_MEMORY_EMBEDDING_MODEL", "").strip()
    embedding_model = (
        raw_model if raw_model and not raw_model.startswith("<PICK_") else None
    )
    return MemoryConfig(
        strata_home=strata_home,
        kb_dir=kb_dir,
        state_dir=state_dir,
        memory_dir=memory_dir,
        cards_dir=cards_dir,
        cache_dir=cache_dir,
        session_state_dir=session_state_dir,
        backups_dir=backups_dir,
        telemetry_dir=telemetry_dir,
        telemetry_file=telemetry_dir / "events.jsonl",
        memory_eval_file=telemetry_dir / "memory-eval.jsonl",
        access_log=session_state_dir / "access-log.json",
        access_lock=session_state_dir / "access-log.lock",
        memory_index=cards_dir / "MEMORY.md",
        index_proposal=cache_dir / "MEMORY.proposed.md",
        embedding_model=embedding_model,
        telemetry_enabled=_enabled(values.get("STRATA_TELEMETRY")),
        digest_enabled=_enabled(values.get("STRATA_MEMORY_DIGEST"), default=True),
    )


__all__ = ["MemoryConfig", "load_config"]
