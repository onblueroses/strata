#!/usr/bin/env python3
"""Rebuild the lex doc-vector cache + doc-catalog from the live reference docs.
Run this whenever a reference doc's keywords or INDEX description changes."""

import os
import re
import json
import subprocess
import sys
from typing import NoReturn

# reference/ is the parent of this script's dir (.router-eval); STRATA_HOME env overrides.
EVAL = os.path.dirname(os.path.abspath(__file__))
REF = os.environ.get("STRATA_REF") or os.path.dirname(EVAL)
idx = open(os.path.join(REF, "INDEX.md")).read()
desc = {
    m.group(1).strip(): m.group(2).strip()
    for m in re.finditer(r"^\|\s*`([^`]+\.md)`\s*\|\s*([^|]+)\|", idx, re.M)
}
cat = []
for f in sorted(os.listdir(REF)):
    if not f.endswith(".md") or f == "INDEX.md":
        continue
    head = "\n".join(open(os.path.join(REF, f)).read().splitlines()[:5])
    km = re.search(r"<!--\s*keywords:\s*(.*?)\s*-->", head, re.S)
    cat.append(
        {
            "doc": f,
            "keywords": km.group(1).strip() if km else "",
            "description": desc.get(f, ""),
        }
    )
json.dump(cat, open(os.path.join(EVAL, "doc-catalog.json"), "w"), indent=1)

# Rebuild the lex cache atomically: keep a backup, let the matcher rebuild on sig
# change, then verify the result parses before committing. A crashed matcher (bad env,
# missing dep) must NOT leave the hook with no cache -- the old cache is restored.
CACHE = os.path.join(EVAL, ".lex-cache.json")
backup = None
if os.path.exists(CACHE):
    backup = CACHE + ".bak"
    os.replace(CACHE, backup)
proc = subprocess.run(
    [sys.executable, os.path.join(EVAL, "matchers", "lex.py")],
    input='{"prompt":"warm","cwd":"/tmp"}',
    text=True,
    capture_output=True,
)


def _restore_and_die(reason) -> NoReturn:
    if backup is not None:
        os.replace(backup, CACHE)
        print(f"  rebuild FAILED ({reason}); restored previous cache.", file=sys.stderr)
    else:
        print(
            f"  rebuild FAILED ({reason}); no prior cache to restore.", file=sys.stderr
        )
    sys.exit(1)


if proc.returncode != 0:
    _restore_and_die(f"matcher exit={proc.returncode}: {proc.stderr.strip()[:200]}")
try:
    cache = json.load(open(CACHE))
    assert cache.get("vecs"), "empty doc vectors"
except (FileNotFoundError, ValueError, AssertionError) as e:
    _restore_and_die(f"cache unreadable: {e}")
if backup is not None:
    os.remove(backup)

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
