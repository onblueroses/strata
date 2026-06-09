#!/usr/bin/env python3
"""tfidf matcher — sklearn TF-IDF cosine between (prompt + cwd tail) and each doc's
description+keywords. Free, ~instant. Threshold + top-k tuned on the `tune` split (Phase 3)
via env vars ROUTER_TFIDF_THRESHOLD / ROUTER_TFIDF_TOPK."""

import sys
import json
import time
import os

START = time.time()
EVAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
THRESH = float(os.environ.get("ROUTER_TFIDF_THRESHOLD", "0.06"))
TOPK = int(os.environ.get("ROUTER_TFIDF_TOPK", "3"))


def main():
    try:
        data = json.load(sys.stdin)
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
    except Exception as e:
        print(
            json.dumps(
                {"docs": [], "matcher": "tfidf", "latency_ms": 0, "error": str(e)}
            )
        )
        return
    prompt = data.get("prompt") or ""
    cwd = data.get("cwd") or ""
    query = prompt + " " + os.path.basename(cwd.rstrip("/"))
    catalog = json.load(open(os.path.join(EVAL, "doc-catalog.json")))
    corpus = [c["description"] + " " + c["keywords"] for c in catalog]
    vec = TfidfVectorizer(stop_words="english")
    M = vec.fit_transform(corpus + [query])
    sims = cosine_similarity(M[-1], M[:-1])[0]
    scored = sorted(
        ((float(s), catalog[i]["doc"]) for i, s in enumerate(sims) if s >= THRESH),
        reverse=True,
    )[:TOPK]
    docs = [{"name": n, "score": round(s, 3), "signal": "tfidf"} for s, n in scored]
    print(
        json.dumps(
            {
                "docs": docs,
                "matcher": "tfidf",
                "latency_ms": int((time.time() - START) * 1000),
            }
        )
    )


if __name__ == "__main__":
    main()
