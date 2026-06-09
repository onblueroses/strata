#!/usr/bin/env python3
"""lex matcher — pure-Python TF-IDF cosine (no sklearn import, no network). Precomputes
normalized doc vectors to .lex-cache.json; query time is tokenize + cosine (~5ms).
Gets tfidf-quality conceptual routing at deterministic-signal speed. Tuned via
ROUTER_LEX_THRESHOLD / ROUTER_LEX_TOPK on the `tune` split."""

import sys
import json
import time
import os
import re
import math
import hashlib

START = time.time()
EVAL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(EVAL, ".lex-cache.json")


def _envnum(name, default, cast):
    # Guard the parse like the live hook does: a malformed override must fall back to
    # the default, never raise at module import (a module-level raise here would crash
    # the matcher before main(), and build-lex-cache.py deletes the cache before
    # invoking it -> a bad env value would otherwise leave NO cache behind).
    try:
        return cast(os.environ.get(name, default))
    except (TypeError, ValueError):
        return cast(default)


THRESH = _envnum("ROUTER_LEX_THRESHOLD", "0.07", float)
# Relaxed threshold for solo-only (single strong-solo token) matches; mirrors the
# live hook's LEX_SOLO_THRESH. Applies ONLY to the solo-bypass path.
SOLO_THRESH = _envnum("ROUTER_LEX_SOLO_THRESHOLD", "0.10", float)
TOPK = _envnum("ROUTER_LEX_TOPK", "2", int)
MIN_TOK = _envnum("ROUTER_LEX_MIN_TOK", "2", int)
# STOP must stay byte-identical to the live hook's STOP (context-doc-router.py):
# build-lex-cache.py builds the live .lex-cache.json via this module, so a divergent
# stop set here would tokenize doc vectors differently than the hook tokenizes queries.
STOP = set(
    "the a an and or of to in for on with is are be this that it as at by from your you "
    "i we my our use using used setup set up add new run check make help me can do "
    "how want really today getting into over".split()
)


def toks(text):
    return [
        t
        for t in re.split(r"[^a-z0-9]+", text.lower())
        if len(t) >= 3 and t not in STOP
    ]


def _is_rare_token():
    # A single token is safe to fire a doc alone only if it is RARE in general English
    # (a genuine tool/brand name like "hyprland"/"vitest"), not merely absent from a
    # dictionary -- measured: cracklib membership leaks common proper nouns/jargon
    # (google, linux, dataset, workflow) as false positives. Frequency is the right
    # oracle. With wordfreq we gate on Zipf rarity; WITHOUT it we cannot judge rarity,
    # so nothing qualifies as solo and the rule degrades to clean >=2-token (never worse).
    try:
        from wordfreq import zipf_frequency

        return lambda t: zipf_frequency(t, "en") < 2.5
    except Exception:
        return lambda t: False


def build_cache(catalog):
    docs_toks = [toks(c["description"] + " " + c["keywords"]) for c in catalog]
    df = {}
    for dt in docs_toks:
        for t in set(dt):
            df[t] = df.get(t, 0) + 1
    N = len(catalog)
    idf = {t: math.log((1 + N) / (1 + d)) + 1 for t, d in df.items()}
    vecs = {}
    for c, dt in zip(catalog, docs_toks):
        tf = {}
        for t in dt:
            tf[t] = tf.get(t, 0) + 1
        v = {t: (f / len(dt)) * idf[t] for t, f in tf.items()} if dt else {}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs[c["doc"]] = {t: x / norm for t, x in v.items()}
    # strong-solo tokens: corpus-unique (df==1) + distinctive length + RARE in general
    # English -> safe to fire a doc on a single match (recovers terse "hyprland"/"vitest"
    # prompts that >=2-token drops, while homonyms and common jargon stay gated). Empty
    # unless a frequency oracle (wordfreq) is installed; see _is_rare_token.
    is_rare = _is_rare_token()
    solo = sorted(t for t, d in df.items() if d == 1 and len(t) >= 5 and is_rare(t))
    return {
        "idf": idf,
        "vecs": vecs,
        "solo": solo,
        "sig": hashlib.sha1(
            "".join(c["doc"] + c["keywords"] for c in catalog).encode()
        ).hexdigest(),
    }


def main():
    try:
        data = json.load(sys.stdin)
        catalog = json.load(open(os.path.join(EVAL, "doc-catalog.json")))
    except Exception as e:
        print(
            json.dumps({"docs": [], "matcher": "lex", "latency_ms": 0, "error": str(e)})
        )
        return
    sig = hashlib.sha1(
        "".join(c["doc"] + c["keywords"] for c in catalog).encode()
    ).hexdigest()
    cache = json.load(open(CACHE)) if os.path.exists(CACHE) else None
    if not cache or cache.get("sig") != sig:
        cache = build_cache(catalog)
        json.dump(cache, open(CACHE, "w"))
    idf, vecs = cache["idf"], cache["vecs"]
    solo = set(cache.get("solo", []))
    qt = toks(
        (data.get("prompt") or "")
        + " "
        + os.path.basename((data.get("cwd") or "").rstrip("/"))
    )
    qtf = {}
    for t in qt:
        qtf[t] = qtf.get(t, 0) + 1
    qv = {t: (f / len(qt)) * idf.get(t, 0) for t, f in qtf.items()} if qt else {}
    qn = math.sqrt(sum(x * x for x in qv.values())) or 1.0
    qv = {t: x / qn for t, x in qv.items()}
    scored = []
    for name, dv in vecs.items():
        matched = [t for t in dv if qv.get(t, 0) > 0]
        # fire on >=2 corroborating tokens OR a single strong-solo (unambiguous) token
        solo_only = len(matched) < MIN_TOK and any(t in solo for t in matched)
        if len(matched) < MIN_TOK and not solo_only:
            continue
        s = sum(qv[t] * dv[t] for t in matched)
        if s >= (SOLO_THRESH if solo_only else THRESH):
            scored.append((round(s, 3), name))
    scored.sort(reverse=True)
    docs = [{"name": n, "score": s, "signal": "lex"} for s, n in scored[:TOPK]]
    print(
        json.dumps(
            {
                "docs": docs,
                "matcher": "lex",
                "latency_ms": int((time.time() - START) * 1000),
            }
        )
    )


if __name__ == "__main__":
    main()
