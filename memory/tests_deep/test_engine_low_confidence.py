from __future__ import annotations

from typing import Any

import pytest

from memory import engine

CORPUS = [
    {"id": "alpha-card", "title": "Alpha", "description": "", "body": "alpha queue"},
    {"id": "beta-card", "title": "Beta", "description": "", "body": "beta schema"},
]


def high_vector_rank(
    query: str,
    records: list[dict[str, Any]],
    *,
    cacheable: bool,
    config: object,
) -> tuple[list[tuple[str, float]], None]:
    del query, cacheable, config
    return [
        (str(record["id"]), 0.999 - index * 0.01)
        for index, record in enumerate(records)
    ], None


def test_high_vector_similarity_cannot_rescue_zero_lexical_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(engine, "_vector_rank", high_vector_rank)
    result = engine.search("xylophone nebula", corpus=CORPUS, use_embeddings=True)
    assert result.search_mode == "fused"
    assert result.telemetry["bm25_top_score"] == 0.0
    assert result.telemetry["vector_top_score"] == pytest.approx(0.999)
    assert result.telemetry["low_confidence"] is True
    assert result.telemetry["is_miss"] is True
    assert result.telemetry["miss_reason"] == "low_confidence"


def test_strong_lexical_evidence_is_confident_with_fusion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(engine, "_vector_rank", high_vector_rank)
    result = engine.search("alpha queue", corpus=CORPUS, use_embeddings=True)
    assert result.search_mode == "fused"
    assert result.telemetry["bm25_top_score"] >= engine.BM25_LOW_CONFIDENCE_THRESHOLD
    assert result.telemetry["low_confidence"] is False
    assert result.telemetry["is_miss"] is False
