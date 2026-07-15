from __future__ import annotations

import pytest

from memory.config import load_config
from memory.eval import run


def test_synthetic_bm25_eval_meets_frozen_gold() -> None:
    corpus, gold = run.load_fixture()
    metrics, mode, unavailable = run.evaluate(corpus, gold, use_embeddings=False)
    assert mode == "bm25"
    assert unavailable is None
    assert metrics
    assert all(float(row["recall@3"]) == 1.0 for row in metrics.values())
    assert run.main([]) == 0


def test_eval_queries_stay_out_of_live_telemetry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STRATA_TELEMETRY", "1")
    config = load_config()
    corpus, gold = run.load_fixture()
    run.evaluate(corpus, gold, use_embeddings=False)
    assert not config.telemetry_file.exists()
    assert (config.session_state_dir / "eval-run-kb-query.jsonl").is_file()
