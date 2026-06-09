#!/usr/bin/env python3
"""nomic-embed matcher — local ollama `nomic-embed-text` cosine between (prompt + cwd tail)
and each doc's description+keywords. Free, local. Doc embeddings are cached to disk
(.embed-cache.json) so per-call cost is one query embedding (~50-100ms).
Threshold/top-k tuned on the `tune` split (Phase 3) via ROUTER_EMBED_THRESHOLD / ROUTER_EMBED_TOPK."""

import sys
import json
import time
import os
import hashlib
import urllib.request
import math

START = time.time()
EVAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(EVAL, ".embed-cache.json")
THRESH = float(os.environ.get("ROUTER_EMBED_THRESHOLD", "0.5"))
TOPK = int(os.environ.get("ROUTER_EMBED_TOPK", "3"))
MODEL = "nomic-embed-text"
URL = "http://localhost:11434/api/embeddings"


def embed(text):
    req = urllib.request.Request(
        URL,
        data=json.dumps({"model": MODEL, "prompt": text}).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())["embedding"]


def cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def doc_cache(catalog):
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else {}
    changed = False
    for c in catalog:
        text = c["description"] + " " + c["keywords"]
        h = hashlib.sha1(text.encode()).hexdigest()
        if cache.get(c["doc"], {}).get("h") != h:
            cache[c["doc"]] = {"h": h, "emb": embed(text)}
            changed = True
    if changed:
        json.dump(cache, open(CACHE, "w"))
    return cache


def main():
    try:
        data = json.load(sys.stdin)
        catalog = json.load(open(os.path.join(EVAL, "doc-catalog.json")))
        cache = doc_cache(catalog)
        q = embed(
            (data.get("prompt") or "")
            + " "
            + os.path.basename((data.get("cwd") or "").rstrip("/"))
        )
    except Exception as e:
        print(
            json.dumps(
                {"docs": [], "matcher": "nomic-embed", "latency_ms": 0, "error": str(e)}
            )
        )
        return
    scored = sorted(
        ((cosine(q, cache[c["doc"]]["emb"]), c["doc"]) for c in catalog), reverse=True
    )
    docs = [
        {"name": n, "score": round(s, 3), "signal": "embed"}
        for s, n in scored
        if s >= THRESH
    ][:TOPK]
    print(
        json.dumps(
            {
                "docs": docs,
                "matcher": "nomic-embed",
                "latency_ms": int((time.time() - START) * 1000),
            }
        )
    )


if __name__ == "__main__":
    main()
