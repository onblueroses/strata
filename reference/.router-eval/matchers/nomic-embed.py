#!/usr/bin/env python3
"""nomic-embed matcher — local ollama `nomic-embed-text` cosine between (prompt + cwd tail)
and each doc's description+keywords. Optional historical comparison, invoked by name."""

import json
import os
import urllib.request
import math

from _common import load_catalog, run, text_field

MODEL = "nomic-embed-text"
URL = "http://localhost:11434/api/embeddings"
TIMEOUT_SECONDS = 5
MIN_SCORE = 0.5
MAX_DOCS = 3


def embed(text):
    req = urllib.request.Request(
        URL,
        data=json.dumps({"model": MODEL, "prompt": text}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT_SECONDS) as r:
        return json.loads(r.read())["embedding"]


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def build_docs(data):
    catalog = load_catalog()
    query = (
        text_field(data, "prompt")
        + " "
        + os.path.basename(text_field(data, "cwd").rstrip("/"))
    )
    if not query.strip():
        return []
    q = embed(query)
    scored = sorted(
        (
            (cosine(q, embed(c["description"] + " " + c["keywords"])), c["doc"])
            for c in catalog
        ),
        reverse=True,
    )
    return [
        {"name": name, "score": round(score, 3), "signal": "embed"}
        for score, name in scored
        if score >= MIN_SCORE
    ][:MAX_DOCS]


if __name__ == "__main__":
    run("nomic-embed", build_docs)
