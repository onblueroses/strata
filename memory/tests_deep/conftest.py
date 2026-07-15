from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from memory import engine
from memory.config import MemoryConfig, load_config


@pytest.fixture(autouse=True)
def isolated_roots(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[MemoryConfig]:
    home = tmp_path / "home"
    strata = tmp_path / "install"
    kb = tmp_path / "knowledge"
    state = tmp_path / "state"
    for name, value in {
        "HOME": home,
        "STRATA_HOME": strata,
        "KB_DIR": kb,
        "STATE_DIR": state,
    }.items():
        monkeypatch.setenv(name, str(value))
    monkeypatch.delenv("STRATA_TELEMETRY", raising=False)
    monkeypatch.delenv("STRATA_MEMORY_EMBEDDING_MODEL", raising=False)
    monkeypatch.delenv("STRATA_MEMORY_DIGEST", raising=False)
    engine._reset_model_state()
    config = load_config()
    config.ensure_state_dirs()
    config.memory_index.write_text(
        "# Memory Index\n\n"
        "## Entities\n\n"
        "| Entity | Path | Status | last_verified |\n"
        "|---|---|---|---|\n",
        encoding="utf-8",
    )
    yield config
    engine._reset_model_state()


@pytest.fixture
def memory_config() -> MemoryConfig:
    return load_config()


@pytest.fixture
def write_card() -> Callable[..., Path]:
    def writer(
        directory: Path,
        card_id: str,
        body: str,
        *,
        name: str | None = None,
        description: str | None = None,
        card_type: str = "memory",
        importance: float | None = None,
    ) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        lines = [
            "---",
            f"name: {name or card_id}",
            f"description: {description or body[:100]}",
            f"type: {card_type}",
        ]
        if importance is not None:
            lines.append(f"importance: {importance}")
        lines.extend(["---", body, ""])
        path = directory / f"{card_id}.md"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path

    return writer
