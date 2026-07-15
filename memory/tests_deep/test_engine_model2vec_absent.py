from __future__ import annotations

import pytest

from memory import engine
from memory.config import MemoryConfig, load_config


def test_model2vec_absence_falls_back_to_bm25(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STRATA_MEMORY_EMBEDDING_MODEL", "synthetic-static-model")
    config = load_config()

    def absent(_config: MemoryConfig) -> bool:
        engine._MODEL2VEC_CHECKED = True
        engine._MODEL2VEC_INSTALLED = False
        engine._MODEL2VEC_ERROR = "ImportError: optional package is absent"
        return False

    monkeypatch.setattr(engine, "_check_model2vec_import", absent)
    corpus = [
        {
            "id": "fallback-card",
            "title": "",
            "description": "",
            "body": "fallback anchor",
        },
        {"id": "other-card", "title": "", "description": "", "body": "unrelated"},
    ]
    result = engine.search(
        "fallback anchor",
        corpus=corpus,
        use_embeddings=True,
        config=config,
    )
    assert result and result[0]["id"] == "fallback-card"
    assert result.search_mode == "bm25"
    assert result.fusion_unavailable == "ImportError: optional package is absent"
    assert result.telemetry["search_mode"] == "bm25"
    assert engine._MODEL2VEC_CHECKED is True
    assert engine._MODEL2VEC_INSTALLED is False


def test_unset_embedding_model_never_imports_model2vec(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def forbidden(_config: MemoryConfig) -> bool:
        nonlocal called
        called = True
        raise AssertionError("optional import should not run")

    monkeypatch.setattr(engine, "_check_model2vec_import", forbidden)
    result = engine.search(
        "alpha",
        corpus=[{"id": "alpha", "body": "alpha"}],
        use_embeddings=False,
    )
    assert result.search_mode == "bm25"
    assert result.fusion_unavailable is None
    assert called is False


def test_placeholder_embedding_value_is_treated_as_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STRATA_MEMORY_EMBEDDING_MODEL", "<PICK_EMBEDDING_MODEL>")
    assert load_config().embedding_model is None
