from __future__ import annotations

from memory import engine


def test_bm25_distinctive_terms_outrank_common_repetition() -> None:
    corpus = [
        {
            "id": "distinctive",
            "title": "Distinctive",
            "description": "",
            "body": "quartzforge deployment invariant",
        },
        {
            "id": "common-repetition",
            "title": "Common",
            "description": "",
            "body": "deployment " * 30,
        },
        {
            "id": "unrelated",
            "title": "Unrelated",
            "description": "",
            "body": "database schema migration",
        },
    ]
    result = engine.search(
        "quartzforge deployment", corpus=corpus, use_embeddings=False
    )
    scores = {str(hit["id"]): float(hit["score"]) for hit in result}
    assert result.search_mode == "bm25"
    assert result[0]["id"] == "distinctive"
    assert scores["distinctive"] > scores["common-repetition"]


def test_bm25_length_normalization_rewards_concise_match() -> None:
    corpus = [
        {"id": "short", "title": "", "description": "", "body": "ioncalibration"},
        {
            "id": "padded",
            "title": "",
            "description": "",
            "body": "ioncalibration " + "ordinary filler " * 200,
        },
    ]
    result = engine.search("ioncalibration", corpus=corpus, use_embeddings=False)
    assert result[0]["id"] == "short"
    assert float(result[0]["score"]) > float(result[1]["score"])


def test_zero_overlap_is_a_low_confidence_miss() -> None:
    corpus = [{"id": "alpha", "title": "", "description": "", "body": "alpha beta"}]
    result = engine.search("xylophone nebula", corpus=corpus, use_embeddings=False)
    assert result.telemetry["bm25_top_score"] == 0.0
    assert result.telemetry["low_confidence"] is True
    assert result.telemetry["is_miss"] is True
