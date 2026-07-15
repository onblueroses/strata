#!/usr/bin/env python3
"""Deterministic recall and reciprocal-rank evaluation on synthetic fixtures."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Any

from memory.config import load_config
from memory import engine

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
CORPUS_PATH = FIXTURE_DIR / "corpus.json"
GOLD_PATH = FIXTURE_DIR / "gold.json"


def fixture_hash() -> str:
    digest = hashlib.sha256()
    digest.update(CORPUS_PATH.read_bytes())
    digest.update(GOLD_PATH.read_bytes())
    return digest.hexdigest()


def load_fixture() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    corpus = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    gold = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    if not isinstance(corpus, list) or not isinstance(gold, list):
        raise ValueError("evaluation fixtures must be JSON arrays")
    return corpus, gold


def recall_at(ids: list[str], relevant: set[str], k: int) -> float:
    return len(relevant & set(ids[:k])) / len(relevant) if relevant else 0.0


def reciprocal_rank(ids: list[str], relevant: set[str]) -> float:
    for index, document_id in enumerate(ids, 1):
        if document_id in relevant:
            return 1.0 / index
    return 0.0


def evaluate(
    corpus: list[dict[str, Any]],
    gold: list[dict[str, Any]],
    *,
    use_embeddings: bool,
) -> tuple[dict[str, dict[str, float | int]], str, str | None]:
    rows: defaultdict[str, list[dict[str, float]]] = defaultdict(list)
    modes: list[str] = []
    unavailable: str | None = None
    base_config = load_config()
    cfg = replace(
        base_config,
        telemetry_file=base_config.session_state_dir / "eval-run-kb-query.jsonl",
    )
    for query in gold:
        result = engine.search(
            str(query["query"]),
            k=len(corpus),
            corpus=corpus,
            use_embeddings=use_embeddings,
            origin="eval:run",
            config=cfg,
        )
        modes.append(result.search_mode)
        unavailable = unavailable or result.fusion_unavailable
        relevant = {str(value) for value in query.get("relevant_ids", [])}
        ids = [str(hit["id"]) for hit in result]
        rows[str(query.get("query_set", "default"))].append(
            {
                "recall@3": recall_at(ids, relevant, 3),
                "recall@5": recall_at(ids, relevant, 5),
                "mrr": reciprocal_rank(ids, relevant),
            }
        )
    metrics: dict[str, dict[str, float | int]] = {}
    for query_set in sorted(rows):
        values = rows[query_set]
        count = len(values)
        metrics[query_set] = {
            "n": count,
            "recall@3": sum(row["recall@3"] for row in values) / count,
            "recall@5": sum(row["recall@5"] for row in values) / count,
            "mrr": sum(row["mrr"] for row in values) / count,
        }
    expected_mode = "fused" if use_embeddings else "bm25"
    mode = (
        expected_mode
        if modes and all(value == expected_mode for value in modes)
        else "mixed"
    )
    return metrics, mode, unavailable


def _minimum(metrics: dict[str, dict[str, float | int]], field: str) -> float:
    return min(float(row[field]) for row in metrics.values()) if metrics else 0.0


def print_table(title: str, metrics: dict[str, dict[str, float | int]]) -> None:
    print(title)
    print(f"{'query set':24} {'n':>3} {'recall@3':>10} {'recall@5':>10} {'MRR':>10}")
    for query_set, row in metrics.items():
        print(
            f"{query_set:24} {int(row['n']):>3} "
            f"{float(row['recall@3']):>10.4f} {float(row['recall@5']):>10.4f} "
            f"{float(row['mrr']):>10.4f}"
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", action="store_true")
    parser.add_argument("--require-min-recall", type=float, default=1.0)
    args = parser.parse_args(argv)
    corpus, gold = load_fixture()
    print(f"fixture_sha256: {fixture_hash()}")
    bm25_metrics, bm25_mode, _unavailable = evaluate(corpus, gold, use_embeddings=False)
    print(f"bm25_mode: {bm25_mode}")
    if args.report:
        print_table("BM25-only", bm25_metrics)
    minimum = _minimum(bm25_metrics, "recall@3")
    print(f"bm25_min_recall@3: {minimum:.4f}")
    if bm25_mode != "bm25" or minimum < args.require_min_recall:
        return 2
    status = engine.model2vec_status(load_config())
    if not status["configured"] or not status["installed"]:
        print("fusion: skipped (optional embedding model unavailable)")
        return 0
    fused_metrics, fused_mode, unavailable = evaluate(corpus, gold, use_embeddings=True)
    if fused_mode != "fused":
        print(f"fusion: unavailable ({unavailable or 'vector ranking failed'})")
        return 2
    if args.report:
        print_table("Fused BM25 plus static embeddings", fused_metrics)
    if _minimum(fused_metrics, "recall@3") < minimum:
        print("fusion: recall regression")
        return 2
    print("fusion: non-regression PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
