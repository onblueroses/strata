from __future__ import annotations

import json
from pathlib import Path

from memory.eval.summary import summarize_latest


def _row(
    run_id: str, probe_id: str, verdict: str, *, adversarial: bool = False
) -> dict:
    return {
        "kind": "memory_eval",
        "run_id": run_id,
        "probe_id": probe_id,
        "capability": "retrieval",
        "search_mode": "bm25",
        "verdict": verdict,
        "adversarial": adversarial,
        "decision_grade": False,
    }


def test_latest_run_summary_excludes_adversarial_sentinel(tmp_path: Path) -> None:
    path = tmp_path / "memory-eval.jsonl"
    rows = [
        _row("old", "p1", "FAIL"),
        _row("new", "p1", "PASS"),
        _row("new", "p2", "FAIL"),
        _row("new", "sentinel", "FAIL", adversarial=True),
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    summary = summarize_latest(path)
    assert summary["run_id"] == "new"
    assert summary["rows"] == 2
    assert summary["pass"] == 1
    assert summary["fail"] == 1
    assert summary["decision_grade"] is False
    assert summary["units"] == [
        {
            "capability": "retrieval",
            "search_mode": "bm25",
            "total": 2,
            "pass": 1,
            "fail": 1,
        }
    ]


def test_empty_or_malformed_window_is_safe(tmp_path: Path) -> None:
    path = tmp_path / "memory-eval.jsonl"
    path.write_text("not-json\n", encoding="utf-8")
    assert summarize_latest(path) == {
        "run_id": None,
        "rows": 0,
        "pass": 0,
        "fail": 0,
        "units": [],
    }
