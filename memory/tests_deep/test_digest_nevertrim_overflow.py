from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from memory import digest
from memory.config import MemoryConfig


def test_normal_digest_keeps_every_card(
    memory_config: MemoryConfig, write_card: Callable[..., Path]
) -> None:
    for index in range(8):
        write_card(
            memory_config.cards_dir,
            f"critical-{index:02d}",
            "short invariant description",
            card_type="critical",
        )
    for index in range(8):
        write_card(
            memory_config.cards_dir,
            f"ordinary-{index:02d}",
            "short engineering note",
        )
    context, ids, status = digest.build_digest(config=memory_config)
    assert status == "ok"
    assert len(ids) == 16
    assert "## Never-Trim Cards" in context
    assert "## Card Index" in context
    assert digest.hook_payload_bytes(context) < digest.MAX_STDOUT_CHARS


def test_detail_ladder_sheds_text_before_cards(
    memory_config: MemoryConfig, write_card: Callable[..., Path]
) -> None:
    expected = []
    for index in range(35):
        card_id = f"critical-{index:03d}"
        expected.append(card_id)
        write_card(
            memory_config.cards_dir,
            card_id,
            "body " * 80,
            description="description " * 40,
            card_type="critical",
        )
    _full, _ids, _status = digest.build_digest(config=memory_config)
    for cap in range(2500, digest.MAX_STDOUT_CHARS, 100):
        context, ids, status = digest.build_digest(cap, memory_config)
        if status == "compacted" and ids == expected:
            assert all(card_id in context for card_id in expected)
            assert digest.hook_payload_bytes(context) < cap
            break
    else:
        raise AssertionError("no compacted rung preserved the complete critical corpus")


def test_overflow_drops_ordinary_before_critical_and_reports_critical_loss(
    memory_config: MemoryConfig, write_card: Callable[..., Path]
) -> None:
    critical_ids = []
    for index in range(900):
        card_id = f"critical-{index:04d}"
        critical_ids.append(card_id)
        write_card(
            memory_config.cards_dir,
            card_id,
            "critical invariant",
            card_type="critical",
        )
    for index in range(20):
        write_card(memory_config.cards_dir, f"cold-{index:03d}", "ordinary note")
    context, ids, status = digest.build_digest(config=memory_config)
    assert status == "critical_overflow"
    assert 0 < len(ids) < len(critical_ids)
    assert set(ids) <= set(critical_ids)
    assert not any(card_id.startswith("cold-") for card_id in ids)
    assert "more never-trim cards" in context
    assert digest.hook_payload_bytes(context) < digest.MAX_STDOUT_CHARS


def test_empty_store_is_silent(memory_config: MemoryConfig) -> None:
    assert digest.build_digest(config=memory_config) == ("", [], "no_hot_state")
