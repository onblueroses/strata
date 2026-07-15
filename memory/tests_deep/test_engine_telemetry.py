from __future__ import annotations

import hashlib
import json

import pytest

from memory import engine
from memory.config import load_config
from memory.telemetry import QUERY_CHAR_CAP


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_telemetry_is_opt_in() -> None:
    config = load_config()
    engine.search("alpha", corpus=[{"id": "alpha", "body": "alpha"}], config=config)
    assert not config.telemetry_file.exists()


def test_opt_in_telemetry_has_bounded_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STRATA_TELEMETRY", "1")
    config = load_config()
    query = "alpha " + "x" * (QUERY_CHAR_CAP + 200)
    result = engine.search(
        query,
        corpus=[{"id": "alpha", "body": "alpha"}],
        use_embeddings=False,
        origin="recall",
        config=config,
    )
    row = _rows(config.telemetry_file)[0]
    assert row["kind"] == "kb_query"
    assert row["origin"] == "recall"
    assert row["returned_ids"] == [hit["id"] for hit in result]
    assert len(row["query"]) == QUERY_CHAR_CAP
    assert row["query_chars"] == len(query)
    assert row["query_truncated"] is True
    assert row["query_sha256"] == hashlib.sha256(query.encode()).hexdigest()
    assert not any(str(config.state_dir) in str(value) for value in row.values())


def test_telemetry_sink_failure_does_not_break_retrieval(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STRATA_TELEMETRY", "1")
    config = load_config()
    config.telemetry_dir.parent.mkdir(parents=True, exist_ok=True)
    config.telemetry_dir.write_text("blocks directory creation", encoding="utf-8")
    result = engine.search(
        "alpha",
        corpus=[{"id": "alpha", "body": "alpha"}],
        use_embeddings=False,
        config=config,
    )
    assert result[0]["id"] == "alpha"
