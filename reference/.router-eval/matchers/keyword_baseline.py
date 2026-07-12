#!/usr/bin/env python3
"""Historical keyword baseline: prompt substring match against catalog keywords."""

from _common import load_catalog, run, text_field


def build_docs(data):
    prompt = text_field(data, "prompt").lower()
    docs = []
    for c in load_catalog():
        kws = [
            k.strip().lower() for k in c["keywords"].split(",") if len(k.strip()) >= 6
        ]
        if any(k and k in prompt for k in kws):
            docs.append({"name": c["doc"], "score": 1.0, "signal": "keyword"})
    return docs


if __name__ == "__main__":
    run("keyword_baseline", build_docs)
