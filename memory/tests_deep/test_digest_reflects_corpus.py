from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

from memory import digest
from memory.config import MemoryConfig


def test_digest_reads_current_configured_corpus(
    memory_config: MemoryConfig, write_card: Callable[..., Path]
) -> None:
    write_card(memory_config.cards_dir, "alpha-card", "alpha fixture body")
    write_card(memory_config.cards_dir, "beta-card", "beta fixture body")
    context, ids, status = digest.build_digest(config=memory_config)
    assert status == "ok"
    assert ids == ["alpha-card", "beta-card"]
    assert "## Ranked Cards" not in context
    assert "score=" not in context
    assert "## Entities" not in context

    write_card(memory_config.cards_dir, "gamma-card", "gamma fixture body")
    refreshed, refreshed_ids, refreshed_status = digest.build_digest(
        config=memory_config
    )
    assert refreshed_status == "ok"
    assert refreshed_ids == ["alpha-card", "beta-card", "gamma-card"]
    assert "gamma-card" in refreshed


def test_fifo_card_cannot_block_or_zero_digest(
    memory_config: MemoryConfig, write_card: Callable[..., Path]
) -> None:
    if not hasattr(os, "mkfifo"):
        pytest.skip("FIFO creation is unavailable on this platform")
    write_card(memory_config.cards_dir, "safe-card", "safe body")
    os.mkfifo(memory_config.cards_dir / "blocking-card.md")
    context, ids, status = digest.build_digest(config=memory_config)
    assert ids == ["safe-card"]
    assert status == "card_load_errors"
    assert "failed to load" in context


def test_unrenderable_filename_is_isolated(
    memory_config: MemoryConfig, write_card: Callable[..., Path]
) -> None:
    write_card(memory_config.cards_dir, "safe-card", "safe body")
    hostile = memory_config.cards_dir / "forged\n## Card Index.md"
    hostile.write_text("hostile", encoding="utf-8")
    context, ids, status = digest.build_digest(config=memory_config)
    assert ids == ["safe-card"]
    assert status == "card_load_errors"
    assert context.count("## Card Index") == 1
    assert "failed to load" in context
