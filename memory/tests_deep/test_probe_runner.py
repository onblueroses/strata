from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from memory.config import load_config
from memory.eval import probe_runner


def test_shipped_registry_validates_dynamically() -> None:
    corpus = probe_runner.load_corpus()
    probes, fixture_hash, grader_lane = probe_runner.load_probes(
        probe_runner.REGISTRY_PATH, corpus
    )
    assert probes
    assert len({probe["capability"] for probe in probes}) >= 3
    assert re.fullmatch(r"[0-9a-f]{64}", fixture_hash)
    assert grader_lane == "grader"


@pytest.mark.parametrize(
    "mutation, message",
    [
        (lambda data: data.update(version=1), "version-2"),
        (lambda data: data.update(grader_lane="concrete-model"), "symbolic lane"),
        (lambda data: data["probes"].append(dict(data["probes"][0])), "unique"),
    ],
)
def test_registry_rejects_corruption(
    tmp_path: Path,
    mutation,
    message: str,
) -> None:
    data = json.loads(probe_runner.REGISTRY_PATH.read_text(encoding="utf-8"))
    mutation(data)
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(probe_runner.ProbeError, match=message):
        probe_runner.load_probes(path, probe_runner.load_corpus())


def test_hit_abstain_and_adversarial_scoring() -> None:
    config = load_config()
    corpus = probe_runner.load_corpus()
    probes, fixture_hash, grader_lane = probe_runner.load_probes(
        probe_runner.REGISTRY_PATH, corpus
    )
    run_id = "a" * 32
    rows = [
        probe_runner.run_probe(
            probe,
            "bm25",
            {"k": 5, "use_embeddings": False},
            fixture_hash,
            grader_lane,
            corpus,
            config,
            run_id,
        )
        for probe in probes
    ]
    assert all(row["grader_lane"] == "grader" for row in rows)
    assert all(row["decision_grade"] is False for row in rows)
    assert (
        next(row for row in rows if row["probe_id"] == "unknown-abstain")["verdict"]
        == "PASS"
    )
    adversarial = next(row for row in rows if row["adversarial"])
    assert adversarial["verdict"] == "FAIL"
    assert adversarial["item_id"] not in adversarial["returned_ids"]


def test_bm25_dry_run_end_to_end(capsys: pytest.CaptureFixture[str]) -> None:
    assert probe_runner.main(["--dry-run", "--mode", "bm25"]) == 0
    output = capsys.readouterr().out
    assert "grader_lane=grader" in output
    assert "adversarial_verdicts=FAIL" in output
    assert "dry_run=true" in output
    assert re.search(r"summary: \d+/\d+ PASS", output)


def test_eval_query_telemetry_isolated_from_live_sink(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STRATA_TELEMETRY", "1")
    config = load_config()
    assert probe_runner.main(["--dry-run", "--mode", "bm25"]) == 0
    assert not config.telemetry_file.exists()
    eval_query_sink = config.session_state_dir / "eval-kb-query.jsonl"
    assert eval_query_sink.is_file()
    assert all(
        json.loads(line)["origin"] == probe_runner.ORIGIN
        for line in eval_query_sink.read_text(encoding="utf-8").splitlines()
    )
