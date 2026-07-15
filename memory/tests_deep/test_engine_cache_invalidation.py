from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
import numpy as np
import pytest

from memory import engine
from memory.config import MemoryConfig, load_config


class SpyModel:
    def __init__(self) -> None:
        self.document_calls = 0

    def encode(
        self, texts: list[str], *, batch_size: int, max_length: int
    ) -> list[list[float]]:
        del batch_size, max_length
        if any("\n" in text for text in texts):
            self.document_calls += 1
        return [
            [
                float(text.casefold().count("alpha")),
                float(text.casefold().count("omega")),
                float("\n" in text),
            ]
            for text in texts
        ]


def test_vector_cache_reuses_and_invalidates_on_content_change(
    monkeypatch: pytest.MonkeyPatch,
    memory_config: MemoryConfig,
    write_card: Callable[..., Path],
) -> None:
    monkeypatch.setenv("STRATA_MEMORY_EMBEDDING_MODEL", "synthetic-static-model")
    config = load_config()
    model = SpyModel()
    monkeypatch.setattr(engine, "_load_static_model", lambda _config: model)
    first = write_card(
        config.cards_dir,
        "alpha-card",
        "alpha alpha alpha",
        name="Primary card",
        description="primary document",
    )
    write_card(
        config.cards_dir,
        "backup-alpha",
        "alpha",
        name="Backup card",
        description="backup document",
    )

    initial_records = engine.load_memory_corpus(config)
    ranked, error = engine._vector_rank(
        "alpha", initial_records, cacheable=True, config=config
    )
    assert error is None
    assert ranked and ranked[0][0] == "alpha-card"
    assert model.document_calls == 1
    vectors_path, ids_path = engine._cache_paths(config)
    assert vectors_path.is_file() and ids_path.is_file()

    warm_ranked, error = engine._vector_rank(
        "alpha", initial_records, cacheable=True, config=config
    )
    assert error is None and warm_ranked == ranked
    assert model.document_calls == 1

    original_mtime = first.stat().st_mtime_ns
    first.write_text(
        first.read_text().replace("alpha alpha alpha", "omega omega omega")
    )
    os.utime(first, ns=(original_mtime, original_mtime))
    edited_records = engine.load_memory_corpus(config)
    edited_ranked, error = engine._vector_rank(
        "alpha", edited_records, cacheable=True, config=config
    )
    assert error is None
    assert edited_ranked and edited_ranked[0][0] == "backup-alpha"
    assert model.document_calls == 2
    metadata = json.loads(ids_path.read_text(encoding="utf-8"))
    assert metadata["entries"] == engine._cache_entries(edited_records)
    assert all(entry["sha256"] for entry in metadata["entries"])


def test_vector_cache_invalidates_add_remove_and_bad_shape(
    monkeypatch: pytest.MonkeyPatch,
    write_card: Callable[..., Path],
) -> None:
    monkeypatch.setenv("STRATA_MEMORY_EMBEDDING_MODEL", "synthetic-static-model")
    config = load_config()
    model = SpyModel()
    monkeypatch.setattr(engine, "_load_static_model", lambda _config: model)
    write_card(config.cards_dir, "alpha-card", "alpha")
    records = engine.load_memory_corpus(config)
    engine._vector_rank("alpha", records, cacheable=True, config=config)
    assert model.document_calls == 1

    added = write_card(config.cards_dir, "omega-card", "omega")
    records = engine.load_memory_corpus(config)
    engine._vector_rank("omega", records, cacheable=True, config=config)
    assert model.document_calls == 2
    vectors_path, _ids_path = engine._cache_paths(config)
    assert np.load(vectors_path, allow_pickle=False).shape[0] == 2

    added.unlink()
    records = engine.load_memory_corpus(config)
    engine._vector_rank("alpha", records, cacheable=True, config=config)
    assert model.document_calls == 3

    np.save(vectors_path, np.zeros((0, 3), dtype=np.float32))
    engine._vector_rank("alpha", records, cacheable=True, config=config)
    assert model.document_calls == 4
