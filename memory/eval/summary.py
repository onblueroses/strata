"""Summarize the latest complete synthetic memory-eval run."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def load_memory_eval_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.is_file():
        return rows
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict) and row.get("kind") == "memory_eval":
            rows.append(row)
    return rows


def summarize_latest(path: Path) -> dict[str, Any]:
    rows = load_memory_eval_rows(path)
    if not rows:
        return {"run_id": None, "rows": 0, "pass": 0, "fail": 0, "units": []}
    run_id = str(rows[-1].get("run_id") or "")
    selected = [row for row in rows if str(row.get("run_id") or "") == run_id]
    selected = [row for row in selected if not row.get("adversarial")]
    counts: dict[tuple[str, str], Counter[str]] = {}
    for row in selected:
        key = (str(row.get("capability")), str(row.get("search_mode")))
        counter = counts.setdefault(key, Counter())
        counter["total"] += 1
        counter[str(row.get("verdict", "FAIL")).casefold()] += 1
    units = [
        {
            "capability": capability,
            "search_mode": mode,
            "total": counter["total"],
            "pass": counter["pass"],
            "fail": counter["fail"],
        }
        for (capability, mode), counter in sorted(counts.items())
    ]
    passed = sum(row.get("verdict") == "PASS" for row in selected)
    return {
        "run_id": run_id,
        "rows": len(selected),
        "pass": passed,
        "fail": len(selected) - passed,
        "decision_grade": False,
        "units": units,
    }


__all__ = ["load_memory_eval_rows", "summarize_latest"]
