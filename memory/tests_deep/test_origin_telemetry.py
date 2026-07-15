from __future__ import annotations

import json

import pytest

from memory import engine
from memory.config import load_config


def test_origin_lands_in_returned_and_emitted_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STRATA_TELEMETRY", "1")
    config = load_config()
    result = engine.search(
        "alpha",
        corpus=[{"id": "alpha", "body": "alpha"}],
        use_embeddings=False,
        origin="eval:probe-run",
        config=config,
    )
    row = json.loads(config.telemetry_file.read_text(encoding="utf-8"))
    assert result.telemetry["origin"] == "eval:probe-run"
    assert row["origin"] == "eval:probe-run"


def test_origin_is_absent_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRATA_TELEMETRY", "1")
    config = load_config()
    result = engine.search(
        "no-overlap",
        corpus=[{"id": "alpha", "body": "alpha"}],
        use_embeddings=False,
        config=config,
    )
    row = json.loads(config.telemetry_file.read_text(encoding="utf-8"))
    assert "origin" not in result.telemetry
    assert "origin" not in row
    assert row["is_miss"] is True
