#!/usr/bin/env python3
"""Run a synthetic probe registry through BM25 and optional fused retrieval."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import uuid
from dataclasses import replace
from pathlib import Path
from typing import Any

from memory.config import MemoryConfig, load_config
from memory import engine
from memory.telemetry import append_event

FIXTURE_DIR = Path(__file__).resolve().parent / "fixtures"
REGISTRY_PATH = FIXTURE_DIR / "probes.json"
CORPUS_PATH = FIXTURE_DIR / "corpus.json"
RRF_PIN = 60
ORIGIN = "eval:probe-run"
SCORER = "native-hit-or-abstain-v1"
SYMBOLIC_LANES = {"strong", "fast", "grader", "breadth"}


class ProbeError(RuntimeError):
    pass


def registry_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_corpus(path: Path = CORPUS_PATH) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or not all(isinstance(row, dict) for row in data):
        raise ProbeError("probe corpus must be an array of objects")
    return data


def load_probes(
    path: Path, corpus: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], str, str]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("version") != 2:
        raise ProbeError("probe registry must be a version-2 object")
    grader_lane = data.get("grader_lane")
    if grader_lane not in SYMBOLIC_LANES:
        raise ProbeError("grader_lane must name a symbolic lane")
    probes = data.get("probes")
    if (
        not isinstance(probes, list)
        or not probes
        or not all(isinstance(row, dict) for row in probes)
    ):
        raise ProbeError("probe registry must contain a non-empty object array")
    probe_ids = [str(probe.get("probe_id") or "") for probe in probes]
    if any(not probe_id for probe_id in probe_ids) or len(probe_ids) != len(
        set(probe_ids)
    ):
        raise ProbeError("probe_id values must be non-empty and unique")
    known_ids = {str(record.get("id")) for record in corpus}
    adversarial_count = 0
    for probe in probes:
        expectation = probe.get("expect")
        item_id = probe.get("item_id")
        if not str(probe.get("query") or "").strip():
            raise ProbeError(f"{probe.get('probe_id')}: empty query")
        if not str(probe.get("capability") or "").strip():
            raise ProbeError(f"{probe.get('probe_id')}: empty capability")
        if expectation == "hit":
            if not isinstance(item_id, str) or not item_id:
                raise ProbeError(f"{probe.get('probe_id')}: hit probe needs item_id")
            if probe.get("adversarial"):
                adversarial_count += 1
                if item_id in known_ids:
                    raise ProbeError(
                        "adversarial item_id must be absent from the corpus"
                    )
            elif item_id not in known_ids:
                raise ProbeError(f"{probe.get('probe_id')}: unknown item_id")
        elif expectation == "abstain":
            if item_id is not None:
                raise ProbeError(
                    f"{probe.get('probe_id')}: abstain item_id must be null"
                )
        else:
            raise ProbeError(f"{probe.get('probe_id')}: unsupported expectation")
    if adversarial_count != 1:
        raise ProbeError("registry must contain exactly one adversarial probe")
    return probes, registry_hash(path), str(grader_lane)


def available_modes(
    config: MemoryConfig, requested: str
) -> list[tuple[str, dict[str, Any]]]:
    bm25 = ("bm25", {"k": 5, "use_embeddings": False})
    fused = ("fused", {"k": 5, "use_embeddings": True})
    if requested == "bm25":
        return [bm25]
    if requested == "fused":
        return [fused]
    if requested == "both":
        return [bm25, fused]
    status = engine.model2vec_status(config)
    return [bm25, fused] if status["configured"] and status["installed"] else [bm25]


def run_probe(
    probe: dict[str, Any],
    mode: str,
    search_kwargs: dict[str, Any],
    fixture_hash: str,
    grader_lane: str,
    corpus: list[dict[str, Any]],
    config: MemoryConfig,
    run_id: str,
) -> dict[str, Any]:
    result = engine.search(
        str(probe["query"]),
        corpus=corpus,
        origin=ORIGIN,
        config=config,
        **search_kwargs,
    )
    if result.search_mode != mode:
        raise ProbeError(
            f"{probe['probe_id']}[{mode}] ran as {result.search_mode}: "
            f"{result.fusion_unavailable}"
        )
    returned_ids = [str(hit["id"]) for hit in result]
    expectation, item_id = probe.get("expect"), probe.get("item_id")
    passed = (
        item_id in returned_ids
        if expectation == "hit"
        else bool(result.telemetry["is_miss"])
    )
    return {
        "probe_id": str(probe["probe_id"]),
        "capability": str(probe["capability"]),
        "query": str(probe["query"]),
        "search_mode": mode,
        "expected": {"expect": expectation, "item_id": item_id},
        "item_id": item_id,
        "returned_ids": returned_ids,
        "n_hits": len(result),
        "low_confidence": bool(result.telemetry["low_confidence"]),
        "verdict": "PASS" if passed else "FAIL",
        "scorer": SCORER,
        "grader_lane": grader_lane,
        "decision_grade": False,
        "fixture_hash": fixture_hash,
        "run_id": run_id,
        "adversarial": bool(probe.get("adversarial")),
    }


def error_row(
    probe: dict[str, Any],
    mode: str,
    fixture_hash: str,
    grader_lane: str,
    run_id: str,
    message: str,
) -> dict[str, Any]:
    return {
        "probe_id": str(probe.get("probe_id") or "?"),
        "capability": str(probe.get("capability") or "unknown"),
        "query": str(probe.get("query") or ""),
        "search_mode": mode,
        "expected": {"expect": probe.get("expect"), "item_id": probe.get("item_id")},
        "item_id": probe.get("item_id"),
        "returned_ids": [],
        "n_hits": 0,
        "low_confidence": True,
        "verdict": "FAIL",
        "scorer": SCORER,
        "grader_lane": grader_lane,
        "decision_grade": False,
        "fixture_hash": fixture_hash,
        "run_id": run_id,
        "adversarial": bool(probe.get("adversarial")),
        "error": message,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--corpus", type=Path, default=CORPUS_PATH)
    parser.add_argument(
        "--mode", choices=("auto", "bm25", "fused", "both"), default="auto"
    )
    args = parser.parse_args(argv)
    if engine.RRF_K != RRF_PIN:
        raise ProbeError(f"RRF k must remain pinned at {RRF_PIN}")
    config = load_config()
    eval_config = replace(
        config,
        telemetry_file=config.session_state_dir / "eval-kb-query.jsonl",
    )
    corpus = load_corpus(args.corpus)
    probes, fixture_hash, grader_lane = load_probes(args.registry, corpus)
    modes = available_modes(config, args.mode)
    run_id = uuid.uuid4().hex
    rows: list[dict[str, Any]] = []
    for probe in probes:
        for mode, kwargs in modes:
            try:
                rows.append(
                    run_probe(
                        probe,
                        mode,
                        kwargs,
                        fixture_hash,
                        grader_lane,
                        corpus,
                        eval_config,
                        run_id,
                    )
                )
            except Exception as exc:
                rows.append(
                    error_row(
                        probe,
                        mode,
                        fixture_hash,
                        grader_lane,
                        run_id,
                        f"{type(exc).__name__}: {exc}",
                    )
                )
    counts: dict[tuple[str, str], collections.Counter[str]] = collections.defaultdict(
        collections.Counter
    )
    for row in rows:
        if row["adversarial"]:
            continue
        counter = counts[(str(row["capability"]), str(row["search_mode"]))]
        counter["total"] += 1
        counter["pass"] += row["verdict"] == "PASS"
    adversarial_rows = [row for row in rows if row["adversarial"]]
    if len(adversarial_rows) != len(modes) or any(
        row["verdict"] != "FAIL" for row in adversarial_rows
    ):
        raise ProbeError("adversarial monitor did not fail in every active mode")
    if config.telemetry_enabled and not args.dry_run:
        for row in rows:
            append_event(config.memory_eval_file, "memory_eval", row)
    print(f"fixture_hash={fixture_hash}")
    print(f"grader_lane={grader_lane}")
    for (capability, mode), counter in sorted(counts.items()):
        print(f"{capability}[{mode}]: {counter['pass']}/{counter['total']} PASS")
    passed = sum(row["verdict"] == "PASS" for row in rows)
    verdicts = ",".join(str(row["verdict"]) for row in adversarial_rows)
    print(
        f"summary: {passed}/{len(rows)} PASS; dry_run={str(args.dry_run).lower()}; "
        f"adversarial_verdicts={verdicts}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
