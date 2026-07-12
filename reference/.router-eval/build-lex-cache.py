#!/usr/bin/env python3
"""Rebuild the lex doc-vector cache + doc-catalog from the live reference docs.
Run this whenever a reference doc's keywords or INDEX description changes."""

import hashlib
import json
import math
import os
import re
import shutil
import sys
import tempfile

EVAL = os.path.dirname(os.path.abspath(__file__))
REF = os.environ.get("STRATA_REF") or os.path.dirname(EVAL)
CATALOG = os.path.join(EVAL, "doc-catalog.json")
CACHE = os.path.join(EVAL, ".lex-cache.json")
sys.path.insert(0, os.path.join(EVAL, "matchers"))

from _common import load_router  # noqa: E402


def build_catalog():
    idx = open(os.path.join(REF, "INDEX.md")).read()
    desc = {
        m.group(1).strip(): m.group(2).strip()
        for m in re.finditer(r"^\|\s*`([^`]+\.md)`\s*\|\s*([^|]+)\|", idx, re.M)
    }
    catalog = []
    for fname in sorted(os.listdir(REF)):
        if not fname.endswith(".md") or fname == "INDEX.md":
            continue
        head = "\n".join(open(os.path.join(REF, fname)).read().splitlines()[:5])
        km = re.search(r"<!--\s*keywords:\s*(.*?)\s*-->", head, re.S)
        catalog.append(
            {
                "doc": fname,
                "keywords": km.group(1).strip() if km else "",
                "description": desc.get(fname, ""),
            }
        )
    return catalog


def is_rare_token():
    try:
        from wordfreq import zipf_frequency

        return lambda token: zipf_frequency(token, "en") < 2.5
    except Exception:
        return lambda token: False


def build_cache(catalog):
    toks = load_router().toks
    docs_toks = [toks(c["description"] + " " + c["keywords"]) for c in catalog]
    df = {}
    for dt in docs_toks:
        for token in set(dt):
            df[token] = df.get(token, 0) + 1
    count = len(catalog)
    idf = {token: math.log((1 + count) / (1 + docs)) + 1 for token, docs in df.items()}
    vecs = {}
    for doc, dt in zip(catalog, docs_toks):
        tf = {}
        for token in dt:
            tf[token] = tf.get(token, 0) + 1
        vec = (
            {token: (freq / len(dt)) * idf[token] for token, freq in tf.items()}
            if dt
            else {}
        )
        norm = math.sqrt(sum(value * value for value in vec.values())) or 1.0
        vecs[doc["doc"]] = {token: value / norm for token, value in vec.items()}
    rare = is_rare_token()
    solo = sorted(
        token
        for token, docs in df.items()
        if docs == 1 and len(token) >= 5 and rare(token)
    )
    return {
        "idf": idf,
        "vecs": vecs,
        "solo": solo,
        "sig": hashlib.sha1(
            "".join(c["doc"] + c["keywords"] for c in catalog).encode()
        ).hexdigest(),
    }


def write_temp_json(path, value, indent=None):
    fd, tmp = tempfile.mkstemp(
        dir=EVAL, prefix=os.path.basename(path) + ".", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(value, f, indent=indent)
        with open(tmp) as f:
            json.load(f)
        return tmp
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise


def replace_verified(files):
    backups = []
    try:
        for dest, _ in files:
            if not os.path.exists(dest):
                continue
            fd, backup = tempfile.mkstemp(
                dir=EVAL, prefix=os.path.basename(dest) + ".backup.", suffix=".tmp"
            )
            os.close(fd)
            shutil.copy2(dest, backup)
            backups.append((dest, backup))
        for dest, tmp in files:
            os.replace(tmp, dest)
    except Exception:
        for dest, backup in backups:
            if os.path.exists(backup):
                os.replace(backup, dest)
        raise
    finally:
        for _, backup in backups:
            if os.path.exists(backup):
                os.unlink(backup)


cat = build_catalog()
cache = build_cache(cat)
if not cache.get("vecs"):
    raise SystemExit("rebuild FAILED (empty doc vectors)")

temps = []
try:
    temps.append((CATALOG, write_temp_json(CATALOG, cat, indent=1)))
    temps.append((CACHE, write_temp_json(CACHE, cache)))
    replace_verified(temps)
except Exception as e:
    for _, tmp in temps:
        if os.path.exists(tmp):
            os.unlink(tmp)
    raise SystemExit(f"rebuild FAILED ({e})")

# The solo (strong-solo single-token bypass) set is populated ONLY when wordfreq is
# importable by THIS interpreter. Rebuilding with a bare python3 that lacks wordfreq
# silently empties solo -> the router degrades to clean >=2-token routing and loses
# terse "hyprland"/"vitest" recall (correct, but weaker). Surface it loudly so a
# rebuild never quietly reverts the solo win. Rebuild via:
#   .local/venv/bin/python build-lex-cache.py
nsolo = len(cache.get("solo", []))
try:
    import wordfreq  # noqa: F401

    wf = "present"
except Exception:
    wf = "MISSING"
print(
    f"rebuilt catalog ({len(cat)} docs) + lex cache; solo={nsolo} tokens (wordfreq {wf})"
)
if nsolo == 0:
    print(
        "  WARNING: solo set is EMPTY. If you want terse single-token routing, rebuild "
        "with the wordfreq venv:  .local/venv/bin/python build-lex-cache.py"
    )
