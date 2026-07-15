from __future__ import annotations

from typing import Any

import pytest

from memory import engine


def test_rrf_uses_k_60_and_deterministic_ties() -> None:
    assert engine.RRF_K == 60
    fused = engine._rrf_fuse(
        [("alpha", 4.0), ("beta", 3.0)],
        [("beta", 1.0), ("alpha", 0.5)],
    )
    assert [document_id for document_id, _score in fused] == ["alpha", "beta"]
    assert fused[0][1] == pytest.approx(1 / 61 + 1 / 62)


def test_semantic_rank_can_improve_through_rrf(monkeypatch: pytest.MonkeyPatch) -> None:
    corpus = [
        {"id": "alpha", "body": "quartz query exact"},
        {"id": "beta", "body": "quartz query"},
        {"id": "semantic-target", "body": "conceptual equivalent quartz"},
        {"id": "zeta", "body": "other"},
    ]
    bm25 = engine.search("quartz query", corpus=corpus, use_embeddings=False)

    def vector_rank(
        query: str,
        records: list[dict[str, Any]],
        *,
        cacheable: bool,
        config: object,
    ) -> tuple[list[tuple[str, float]], None]:
        del query, records, cacheable, config
        return [
            ("semantic-target", 1.0),
            ("alpha", 0.8),
            ("beta", 0.6),
            ("zeta", 0.1),
        ], None

    monkeypatch.setattr(engine, "_vector_rank", vector_rank)
    fused = engine.search("quartz query", corpus=corpus, use_embeddings=True)
    bm25_ids = [hit["id"] for hit in bm25]
    fused_ids = [hit["id"] for hit in fused]
    assert fused.search_mode == "fused"
    assert all(hit["search_mode"] == "fused" for hit in fused)
    assert fused_ids.index("semantic-target") < bm25_ids.index("semantic-target")


def test_zero_evidence_bm25_does_not_override_vector_rank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    corpus = [
        {"id": "alpha", "body": "apple"},
        {"id": "zeta", "body": "banana"},
    ]
    bm25 = engine.search("quasar", corpus=corpus, use_embeddings=False)
    assert [hit["id"] for hit in bm25] == ["alpha", "zeta"]
    assert all(hit["score"] == 0.0 for hit in bm25)

    def vector_rank(
        query: str,
        records: list[dict[str, Any]],
        *,
        cacheable: bool,
        config: object,
    ) -> tuple[list[tuple[str, float]], None]:
        del query, records, cacheable, config
        return [("zeta", 1.0), ("alpha", 0.5)], None

    monkeypatch.setattr(engine, "_vector_rank", vector_rank)
    fused = engine.search("quasar", corpus=corpus, use_embeddings=True)

    assert fused.search_mode == "fused"
    assert [hit["id"] for hit in fused] == ["zeta", "alpha"]
