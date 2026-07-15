from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from memory import digest
from memory.config import MemoryConfig


def test_heading_drift_and_caption_are_tolerated(memory_config: MemoryConfig) -> None:
    memory_config.memory_index.write_text(
        "# Index\n\n### Entities (2)\nTotal: 2\n\n"
        "| Entity | Status |\n|---|---|\n| alpha | active |\n| beta | active |\n",
        encoding="utf-8",
    )
    context, ids, status = digest.build_entities_table(config=memory_config)
    assert status == "ok"
    assert ids == []
    assert "### Entities (2)" in context
    assert "| alpha | active |" in context


def test_missing_table_does_not_remove_card_digest(
    memory_config: MemoryConfig, write_card: Callable[..., Path]
) -> None:
    memory_config.memory_index.write_text("# Index without a table\n", encoding="utf-8")
    write_card(memory_config.cards_dir, "retained-card", "retained body")
    table = digest.build_entities_table(config=memory_config)
    cards = digest.build_digest(config=memory_config)
    assert table == ("", [], "no_hot_state")
    assert cards[2] == "ok"
    assert cards[1] == ["retained-card"]


def test_oversized_fixed_table_structure_emits_breadcrumb(
    memory_config: MemoryConfig,
) -> None:
    memory_config.memory_index.write_text(
        "## Entities\n| " + ("wide" * 1000) + " |\n|---|\n| row |\n",
        encoding="utf-8",
    )
    context, ids, status = digest.build_entities_table(500, memory_config)
    assert status == "table_state_exceeds_cap"
    assert ids == []
    assert "exceeds the output cap" in context
    assert digest.hook_payload_bytes(context) < 500
