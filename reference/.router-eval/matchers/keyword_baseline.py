#!/usr/bin/env python3
"""keyword matcher — ports the live hook's substring logic behind the eval interface.
Matches the prompt against each doc's >=6-char keywords (the current router behavior)."""

import sys
import json
import time
import os

START = time.time()
EVAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    try:
        data = json.load(sys.stdin)
    except Exception as e:
        print(
            json.dumps(
                {"docs": [], "matcher": "keyword", "latency_ms": 0, "error": str(e)}
            )
        )
        return
    prompt = (data.get("prompt") or "").lower()
    catalog = json.load(open(os.path.join(EVAL, "doc-catalog.json")))
    docs = []
    for c in catalog:
        kws = [
            k.strip().lower() for k in c["keywords"].split(",") if len(k.strip()) >= 6
        ]
        if any(k and k in prompt for k in kws):
            docs.append({"name": c["doc"], "score": 1.0, "signal": "keyword"})
    print(
        json.dumps(
            {
                "docs": docs,
                "matcher": "keyword",
                "latency_ms": int((time.time() - START) * 1000),
            }
        )
    )


if __name__ == "__main__":
    main()
