#!/usr/bin/env python3
"""tfidf matcher — sklearn TF-IDF cosine between (prompt + cwd tail) and each doc's
description+keywords. Historical comparison only; never part of the default router."""

import os

from _common import load_catalog, run, text_field


def envnum(name, default, cast):
    try:
        return cast(os.environ.get(name, default))
    except (TypeError, ValueError):
        return cast(default)


def build_docs(data):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    prompt = text_field(data, "prompt")
    cwd = text_field(data, "cwd")
    query = prompt + " " + os.path.basename(cwd.rstrip("/"))
    catalog = load_catalog()
    corpus = [c["description"] + " " + c["keywords"] for c in catalog]
    vec = TfidfVectorizer(stop_words="english")
    M = vec.fit_transform(corpus + [query])
    sims = cosine_similarity(M[-1], M[:-1])[0]
    threshold = envnum("ROUTER_TFIDF_THRESHOLD", "0.06", float)
    topk = envnum("ROUTER_TFIDF_TOPK", "3", int)
    scored = sorted(
        ((float(s), catalog[i]["doc"]) for i, s in enumerate(sims) if s >= threshold),
        reverse=True,
    )[:topk]
    return [{"name": n, "score": round(s, 3), "signal": "tfidf"} for s, n in scored]


if __name__ == "__main__":
    run("tfidf", build_docs)
