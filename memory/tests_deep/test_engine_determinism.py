from __future__ import annotations

import json
import os
import subprocess
import sys

from memory import engine

CORPUS = [
    {"id": "charlie", "title": "", "description": "", "body": "alpha beta gamma"},
    {"id": "alpha", "title": "", "description": "", "body": "alpha beta"},
    {"id": "bravo", "title": "", "description": "", "body": "alpha gamma"},
]


def _payload() -> dict[str, object]:
    result = engine.search(
        "gamma alpha beta alpha", corpus=CORPUS, use_embeddings=False
    )
    return {
        "ids": [hit["id"] for hit in result],
        "scores": [hit["score"] for hit in result],
        "top_terms": [hit["top_terms_score"] for hit in result],
    }


def test_ranking_is_deterministic_in_process() -> None:
    assert _payload() == _payload() == _payload()


def test_ranking_is_deterministic_across_hash_seeds() -> None:
    script = (
        "import json; from memory import engine; "
        f"corpus=json.loads({json.dumps(json.dumps(CORPUS))}); "
        "r=engine.search('gamma alpha beta alpha', corpus=corpus, use_embeddings=False); "
        "print(json.dumps({'ids':[h['id'] for h in r],'scores':[h['score'] for h in r],"
        "'top_terms':[h['top_terms_score'] for h in r]}))"
    )
    outputs = []
    for seed in ("1", "91"):
        env = dict(os.environ)
        env["PYTHONHASHSEED"] = seed
        process = subprocess.run(
            [sys.executable, "-c", script],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )
        outputs.append(json.loads(process.stdout))
    assert outputs[0] == outputs[1] == _payload()
