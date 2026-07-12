#!/usr/bin/env python3
"""Shared matcher plumbing for the router eval harness."""

import importlib.util
import json
import os
import sys
import time

MATCHERS = os.path.dirname(os.path.abspath(__file__))
EVAL = os.path.dirname(MATCHERS)
STRATA_HOME = os.path.dirname(os.path.dirname(EVAL))
CATALOG = os.path.join(EVAL, "doc-catalog.json")
HOOK = os.path.join(STRATA_HOME, "hooks", "context-doc-router.py")

_ROUTER = None


def load_router():
    global _ROUTER
    if _ROUTER is None:
        spec = importlib.util.spec_from_file_location("strata_context_doc_router", HOOK)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"cannot load router hook at {HOOK}")
        module = importlib.util.module_from_spec(spec)
        # The hook derives its cache paths from $STRATA_HOME at import time; pin it
        # to this checkout so an installed tree's env var cannot swap in a foreign cache.
        prior = os.environ.get("STRATA_HOME")
        os.environ["STRATA_HOME"] = STRATA_HOME
        try:
            spec.loader.exec_module(module)
        finally:
            if prior is None:
                del os.environ["STRATA_HOME"]
            else:
                os.environ["STRATA_HOME"] = prior
        _ROUTER = module
    return _ROUTER


def text_field(data, key):
    value = data.get(key)
    return value if isinstance(value, str) else ""


def load_catalog():
    with open(CATALOG) as f:
        return json.load(f)


def docs_from_scores(scores, signal):
    return [
        {"name": name, "score": score, "signal": signal}
        for name, score in scores.items()
    ]


def emit(matcher, start, docs=None, error=None):
    payload = {
        "docs": docs or [],
        "matcher": matcher,
        "latency_ms": int((time.time() - start) * 1000),
    }
    if error is not None:
        payload["error"] = str(error)
    print(json.dumps(payload))


def run(matcher, build_docs):
    start = time.time()
    try:
        data = json.load(sys.stdin)
        docs = build_docs(data)
    except Exception as e:
        emit(matcher, start, [], e)
        return
    emit(matcher, start, docs)
