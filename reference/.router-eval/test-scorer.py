#!/usr/bin/env python3
"""Scorer unit tests on fixed predictions (Phase 1 Step 1.5)."""

import importlib.util
import os

spec = importlib.util.spec_from_file_location(
    "runeval", os.path.join(os.path.dirname(os.path.abspath(__file__)), "run-eval.py")
)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
prf = m.prf

cases = [
    ("perfect single", ["a.md"], ["a.md"], 1.0),
    ("perfect multi", ["a.md", "b.md"], ["b.md", "a.md"], 1.0),
    ("empty pred vs need", [], ["a.md"], 0.0),
    ("null correct", [], [], 1.0),
    ("null false-fire", ["a.md"], [], 0.0),
    ("half recall", ["a.md"], ["a.md", "b.md"], 2 / 3),  # p=1 r=.5 -> f=0.667
    ("wrong doc", ["x.md"], ["a.md"], 0.0),
]
fails = 0
for name, pred, exp, want_f1 in cases:
    _, _, f = prf(pred, exp)
    ok = abs(f - want_f1) < 1e-6
    print(f"  [{'PASS' if ok else 'FAIL'}] {name:18s} F1={f:.3f} (want {want_f1:.3f})")
    fails += not ok
print(f"\n{'ALL PASS' if not fails else str(fails) + ' FAILED'}")
raise SystemExit(1 if fails else 0)
