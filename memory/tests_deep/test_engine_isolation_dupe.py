from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from memory import engine
from memory.config import MemoryConfig


def test_one_bad_card_does_not_zero_corpus(
    memory_config: MemoryConfig, write_card: Callable[..., Path]
) -> None:
    write_card(memory_config.cards_dir, "good-card", "alpha body", name="Good Card")
    (memory_config.cards_dir / "bad-card.md").write_bytes(b"\xff\xfe")
    (memory_config.cards_dir / ".hidden-card.md").write_text("hidden", encoding="utf-8")
    records = engine.load_memory_corpus(memory_config)
    assert [record["id"] for record in records] == ["good-card"]
    assert records[0]["title"] == "Good Card"
    assert records[0]["path"] == "memory/cards/good-card.md"


def test_duplicate_ids_are_rejected_before_search() -> None:
    corpus = [
        {"id": "dupe", "body": "alpha"},
        {"id": "dupe", "body": "beta"},
    ]
    with pytest.raises(ValueError, match="duplicate record id in corpus: dupe"):
        engine.search("alpha", corpus=corpus, use_embeddings=False)


def test_project_and_area_namespaces_do_not_collide(
    memory_config: MemoryConfig,
) -> None:
    for kind in ("projects", "areas"):
        path = memory_config.kb_dir / kind / "platform" / "summary.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Platform\nshared summary", encoding="utf-8")
    records = engine.load_memory_corpus(memory_config)
    assert {record["id"] for record in records} == {
        "project:platform",
        "area:platform",
    }
