#!/usr/bin/env python3
"""run-eval.py <matcher> [--split score|tune|all] [--verbose]

Pipes each fixture as synthetic hookData {prompt, cwd, transcript_path} to a matcher,
scores set-based P/R/F1 (per-fixture, aggregate macro, per-family) + p95 latency.

`oracle` is a built-in sanity matcher (returns expected_docs -> F1 should be 1.0).
Matchers live at matchers/<name>.{py,sh}, read hookData on stdin, emit the SCHEMA.md shape.
"""

import sys
import json
import os
import subprocess
import tempfile
import time
import math
import statistics
from collections import defaultdict

EVAL = os.path.dirname(os.path.abspath(__file__))
FIXTURES = os.path.join(EVAL, "fixtures.jsonl")


def load_fixtures():
    return [json.loads(ln) for ln in open(FIXTURES) if ln.strip()]


def synth_transcript(recent_files):
    """Write a JSONL transcript stub mirroring real shape: assistant tool_use Edit entries."""
    fd, path = tempfile.mkstemp(suffix=".jsonl", prefix="router-eval-tx-")
    with os.fdopen(fd, "w") as fh:
        for fp in recent_files:
            line = {
                "type": "assistant",
                "message": {
                    "role": "assistant",
                    "content": [
                        {"type": "tool_use", "name": "Edit", "input": {"file_path": fp}}
                    ],
                },
            }
            fh.write(json.dumps(line) + "\n")
    return path


def matcher_path(name):
    for ext in (".py", ".sh"):
        p = os.path.join(EVAL, "matchers", name + ext)
        if os.path.exists(p):
            return p, ext
    return None, None


def run_matcher(name, hookdata):
    path, ext = matcher_path(name)
    if path is None:
        raise SystemExit(f"no matcher at matchers/{name}.{{py,sh}}")
    cmd = [sys.executable, path] if ext == ".py" else ["bash", path]
    t0 = time.time()
    p = subprocess.run(
        cmd, input=json.dumps(hookdata), capture_output=True, text=True, timeout=30
    )
    wall = (time.time() - t0) * 1000
    try:
        out = (
            json.loads(p.stdout.strip().splitlines()[-1])
            if p.stdout.strip()
            else {"docs": []}
        )
    except Exception:
        out = {"docs": [], "error": "unparseable: " + p.stdout[:200]}
    # surface a crashing/contract-breaking matcher as an error, not a silent miss:
    # a nonzero exit with no parseable docs must not be scored as a valid empty result.
    if p.returncode != 0 and not out.get("docs"):
        err = out.get("error") or f"exit {p.returncode}: " + (p.stderr or "")[:200]
        return [], wall, err
    names = [d["name"] for d in out.get("docs", [])]
    return names, wall, out.get("error")


def prf(predicted, expected):
    P, E = set(predicted), set(expected)
    if not E:
        return (1.0, 1.0, 1.0) if not P else (0.0, 1.0, 0.0)
    if not P:
        return (1.0, 0.0, 0.0)
    tp = len(P & E)
    p = tp / len(P)
    r = tp / len(E)
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return (p, r, f)


def main():
    if len(sys.argv) < 2:
        raise SystemExit(
            "usage: run-eval.py <matcher> [--split score|tune|all] [--verbose]"
        )
    name = sys.argv[1]
    split = "score"
    if "--split" in sys.argv:
        split = sys.argv[sys.argv.index("--split") + 1]
    verbose = "--verbose" in sys.argv

    fixtures = load_fixtures()
    if split != "all":
        fixtures = [f for f in fixtures if f.get("split") == split]

    per_family = defaultdict(list)
    f1s, lats, rows = [], [], []
    for fx in fixtures:
        tx = synth_transcript(fx.get("recent_files", []))
        hookdata = {"prompt": fx["prompt"], "cwd": fx["cwd"], "transcript_path": tx}
        try:
            if name == "oracle":
                predicted, wall, err = list(fx["expected_docs"]), 0.0, None
            else:
                predicted, wall, err = run_matcher(name, hookdata)
        finally:
            os.unlink(tx)
        p, r, f = prf(predicted, fx["expected_docs"])
        f1s.append(f)
        lats.append(wall)
        per_family[fx["family"]].append(f)
        rows.append(
            (fx["id"], fx["family"], round(f, 2), predicted, fx["expected_docs"], err)
        )

    agg = statistics.mean(f1s) if f1s else 0.0
    # ceiling index so the p95 gate reflects the true 95th percentile for fixture
    # counts that aren't multiples of 20 (floor under-reports latency).
    p95 = sorted(lats)[max(0, math.ceil(len(lats) * 0.95) - 1)] if lats else 0.0

    print(f"\n=== matcher: {name}  split: {split}  fixtures: {len(fixtures)} ===")
    print(
        f"AGGREGATE F1 (macro): {agg:.3f}   p95 latency: {p95:.0f}ms   mean: {statistics.mean(lats):.0f}ms"
    )
    print("per-family F1:")
    for fam in sorted(per_family):
        vals = per_family[fam]
        print(f"  {fam:16s} {statistics.mean(vals):.2f}  (n={len(vals)})")
    if verbose:
        print("\nper-fixture:")
        for fid, fam, f, pred, exp, err in rows:
            flag = "" if f >= 0.99 else "  <--"
            print(
                f"  {fid:14s} F1={f:.2f} pred={pred} exp={exp}{(' ERR=' + err) if err else ''}{flag}"
            )
    # machine-readable summary on last line
    print(
        json.dumps(
            {
                "matcher": name,
                "split": split,
                "aggregate_f1": round(agg, 4),
                "p95_latency_ms": round(p95, 1),
                "per_family_f1": {
                    k: round(statistics.mean(v), 4) for k, v in per_family.items()
                },
            }
        )
    )


if __name__ == "__main__":
    main()
