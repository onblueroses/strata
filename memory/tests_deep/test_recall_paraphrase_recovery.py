from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from memory import engine, recall
from memory.config import MemoryConfig


def test_fused_recall_recovers_a_weak_lexical_target(
    monkeypatch: pytest.MonkeyPatch,
    memory_config: MemoryConfig,
    write_card: Callable[..., Path],
) -> None:
    write_card(
        memory_config.cards_dir, "alpha-distractor", "ordinary lexical distractor"
    )
    write_card(memory_config.cards_dir, "beta-distractor", "another ordinary note")
    write_card(
        memory_config.cards_dir,
        "z-semantic-target",
        "consumer pressure control prevents producer overload",
    )
    query = "throttle writers when readers lag"
    lexical = engine.search(
        query,
        k=2,
        use_embeddings=False,
        config=memory_config,
    )
    assert "z-semantic-target" not in [hit["id"] for hit in lexical]

    def vector_rank(
        query_text: str,
        records: list[dict[str, Any]],
        *,
        cacheable: bool,
        config: MemoryConfig,
    ) -> tuple[list[tuple[str, float]], None]:
        del query_text, records, cacheable, config
        return [
            ("z-semantic-target", 1.0),
            ("alpha-distractor", 0.2),
            ("beta-distractor", 0.1),
        ], None

    monkeypatch.setattr(engine, "_vector_rank", vector_rank)
    payload = recall.run_query(query, 2, True, memory_config)
    ids = [hit["id"] for hit in payload["hits"]]
    assert payload["search_mode"] == "fused"
    assert "z-semantic-target" in ids
    target = next(hit for hit in payload["hits"] if hit["id"] == "z-semantic-target")
    assert target["path_root"] == "state"
    assert target["path"] == "memory/cards/z-semantic-target.md"
    assert not str(target["path"]).startswith("/")
