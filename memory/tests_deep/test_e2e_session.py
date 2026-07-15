from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

import pytest

from memory import digest, engine, recall, reconcile
from memory.config import load_config


def test_digest_recall_and_access_log_session_flow(
    monkeypatch: pytest.MonkeyPatch,
    write_card: Callable[..., Path],
) -> None:
    monkeypatch.setenv("STRATA_TELEMETRY", "1")
    config = load_config()
    config.ensure_state_dirs()
    config.memory_index.write_text(
        "## Entities\n| Entity | Status |\n|---|---|\n| compiler | active |\n",
        encoding="utf-8",
    )
    write_card(
        config.cards_dir,
        "bounded-queue",
        "A bounded queue applies admission control when consumers lag.",
        card_type="critical",
    )
    write_card(config.cards_dir, "schema-note", "compatible schema migration")

    context, ids, status = digest.build_digest(config=config)
    assert status == "ok"
    assert set(ids) == {"bounded-queue", "schema-note"}
    assert "## Never-Trim Cards" in context
    table_context, _, table_status = digest.build_entities_table(config=config)
    assert table_status == "ok" and "## Entities" in table_context

    results = engine.search(
        "bounded queue admission control",
        use_embeddings=False,
        origin="recall",
        config=config,
    )
    assert results[0]["id"] == "bounded-queue"
    payload = recall.run_query("bounded queue admission control", 2, False, config)
    assert payload["hits"][0]["id"] == "bounded-queue"
    assert payload["hits"][0]["path"] == "memory/cards/bounded-queue.md"

    assert reconcile.update_access_log(config) >= 2
    access = json.loads(config.access_log.read_text(encoding="utf-8"))
    assert access["cards"]["bounded-queue"]["count"] >= 2
