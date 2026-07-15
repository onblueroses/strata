#!/usr/bin/env python3
"""Command-line recall over configured memory cards and knowledge summaries."""

from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any

from memory.config import MemoryConfig, load_config
from memory import engine

SAFE_COMPONENT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]*\Z")


def _safe_component(value: str) -> bool:
    return SAFE_COMPONENT_RE.fullmatch(value) is not None and value not in {".", ".."}


def resolve_result_path(hit: dict[str, Any]) -> tuple[str, str] | None:
    """Return ``(root, relative_path)`` for a valid engine hit."""

    source = hit.get("source")
    document_id = str(hit.get("id") or "")
    if source == "card" and _safe_component(document_id):
        return "state", f"memory/cards/{document_id}.md"
    if source == "entity-summary" and ":" in document_id:
        kind, name = document_id.split(":", 1)
        if not _safe_component(name):
            return None
        if kind == "project":
            return "kb", f"projects/{name}/summary.md"
        if kind == "area":
            return "kb", f"areas/{name}/summary.md"
    return None


def run_query(
    query: str,
    k: int,
    use_embeddings: bool,
    config: MemoryConfig | None = None,
) -> dict[str, Any]:
    cfg = config or load_config()
    try:
        results = engine.search(
            query,
            k=k,
            use_embeddings=use_embeddings,
            origin="recall",
            config=cfg,
        )
        hits: list[dict[str, Any]] = []
        for hit in results:
            resolved = resolve_result_path(hit)
            row = {
                "id": str(hit.get("id")),
                "score": round(float(hit.get("score", 0.0)), 5),
                "top_terms_score": round(float(hit.get("top_terms_score", 0.0)), 4),
                "source": hit.get("source"),
                "title": hit.get("title"),
                "snippet": hit.get("snippet"),
                "path_root": resolved[0] if resolved else None,
                "path": resolved[1] if resolved else None,
            }
            hits.append(row)
        return {
            "query": query,
            "search_mode": results.search_mode,
            "fusion_unavailable": results.fusion_unavailable,
            "is_miss": results.telemetry.get("is_miss"),
            "low_confidence": results.telemetry.get("low_confidence"),
            "hits": hits,
        }
    except Exception as exc:
        return {
            "query": query,
            "search_mode": None,
            "fusion_unavailable": None,
            "is_miss": True,
            "low_confidence": True,
            "hits": [],
            "error": f"{type(exc).__name__}: {exc}",
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="*")
    parser.add_argument("--k", type=int, default=8)
    parser.add_argument("--no-embeddings", action="store_true")
    args = parser.parse_args(argv)
    if not args.query:
        sys.stdout.write("[]\n")
        return 0
    cfg = load_config()
    use_embeddings = not args.no_embeddings and cfg.embedding_model is not None
    payload = [
        run_query(query, max(args.k, 1), use_embeddings, cfg) for query in args.query
    ]
    json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")
    failures = sum("error" in result for result in payload)
    if failures == len(payload):
        sys.stderr.write("recall: all search angles failed; inspect the JSON errors\n")
        return 2
    if failures:
        sys.stderr.write(
            f"recall: degraded; {failures}/{len(payload)} search angles failed\n"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
