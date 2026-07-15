#!/usr/bin/env python3
"""Refresh the catalog and lex cache, measuring token rarity when wordfreq is present.

The live hook self-heals vectors whenever reference content changes. This builder remains
the authoritative way to measure new tokens for terse single-token routing because the hook
interpreter commonly lacks the optional wordfreq dependency.
"""

import hashlib
import json
import math
import os
import re
import shutil
import sys
import tempfile

SCRIPT_EVAL = os.path.dirname(os.path.abspath(__file__))
REF = os.environ.get("STRATA_REF") or os.path.dirname(SCRIPT_EVAL)
EVAL = os.path.join(REF, ".router-eval")
CATALOG = os.path.join(EVAL, "doc-catalog.json")
CACHE = os.path.join(EVAL, ".lex-cache.json")
sys.path.insert(0, os.path.join(SCRIPT_EVAL, "matchers"))

from _common import load_router  # noqa: E402


def build_catalog():
    with open(os.path.join(REF, "INDEX.md")) as fh:
        idx = fh.read()
    desc = {
        m.group(1).strip(): m.group(2).strip()
        for m in re.finditer(r"^\|\s*`([^`]+\.md)`\s*\|\s*([^|]+)\|", idx, re.M)
    }
    catalog = []
    for fname in sorted(os.listdir(REF)):
        if not fname.endswith(".md") or fname == "INDEX.md":
            continue
        with open(os.path.join(REF, fname)) as fh:
            head = "\n".join(fh.read(4096).splitlines()[:5])
        km = re.search(r"<!--\s*keywords:\s*(.*?)\s*-->", head, re.S)
        catalog.append(
            {
                "doc": fname,
                "keywords": km.group(1).strip() if km else "",
                "description": desc.get(fname, ""),
            }
        )
    return catalog


def catalog_sig(catalog):
    # Keep byte-for-byte parity with the hook: vectors include both text fields, and
    # NUL separators make every field boundary unambiguous.
    return hashlib.sha1(
        "".join(
            c["doc"] + "\0" + c["keywords"] + "\0" + c["description"] for c in catalog
        ).encode()
    ).hexdigest()


SOLO_ZIPF_MAX = 2.0
UNJUDGED = 99.0


def _rarity_oracle():
    try:
        from wordfreq import zipf_frequency

        return lambda token: float(zipf_frequency(token, "en"))
    except Exception:
        return None


def build_cache(catalog, prev=None):
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

    prev = prev if isinstance(prev, dict) else {}
    prior_zipf = prev.get("zipf")
    zipf = (
        {
            token: float(value)
            for token, value in prior_zipf.items()
            if isinstance(token, str) and isinstance(value, (int, float))
        }
        if isinstance(prior_zipf, dict)
        else {}
    )
    measure = _rarity_oracle()
    if measure:
        absent = {token: value for token, value in zipf.items() if token not in df}
        zipf = {token: measure(token) for token in df}
        zipf.update(absent)
    elif not zipf:
        prior_solo = prev.get("solo")
        zipf = (
            {token: 0.0 for token in prior_solo if isinstance(token, str)}
            if isinstance(prior_solo, list)
            else {}
        )
    solo = sorted(
        token
        for token, docs in df.items()
        if docs == 1 and len(token) >= 5 and zipf.get(token, UNJUDGED) < SOLO_ZIPF_MAX
    )
    return {
        "idf": idf,
        "vecs": vecs,
        "solo": solo,
        "zipf": zipf,
        "sig": catalog_sig(catalog),
    }


def load_previous_cache():
    try:
        with open(CACHE) as fh:
            cache = json.load(fh)
        return cache if isinstance(cache, dict) else {}
    except Exception:
        return {}


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
previous = load_previous_cache()
before = len(previous.get("zipf")) if isinstance(previous.get("zipf"), dict) else 0
cache = build_cache(cat, prev=previous)
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

# wordfreq refreshes every live token measurement when importable by THIS interpreter.
# Without it, prior measurements survive and new tokens remain out of solo until a
# wordfreq-backed run. Rebuild via:
#   .local/venv/bin/python build-lex-cache.py
nsolo = len(cache.get("solo", []))
wf = "present" if _rarity_oracle() is not None else "MISSING"
measured = len(cache["zipf"])
new_measured = measured - before
print(
    f"rebuilt catalog ({len(cat)} docs) + lex cache; solo={nsolo} tokens "
    f"(zipf < {SOLO_ZIPF_MAX}; wordfreq {wf}); "
    f"zipf={measured} measurements ({new_measured:+d} this run)"
)
unmeasured = [token for token in cache["idf"] if token not in cache["zipf"]]
if wf == "MISSING" and unmeasured:
    print(
        f"  NOTE: wordfreq is absent, so {len(unmeasured)} token(s) remain unmeasured. "
        "Measure them with:  .local/venv/bin/python build-lex-cache.py"
    )
