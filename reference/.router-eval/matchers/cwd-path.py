#!/usr/bin/env python3
"""cwd-path matcher — maps the working directory (marker files + path patterns) to docs.
Deterministic, free. This is the highest-precision ignored signal: where you ARE is a
stronger router than what you typed."""

import sys
import json
import time
import os

START = time.time()

# path-segment substring -> doc (checked against the cwd string)
PATH_RULES = [
    ("/.claude/skills", "skill-design-principles.md"),
    ("/.claude/hooks", "claude-code-patterns.md"),
    ("/.claude", "claude-code-patterns.md"),
    ("/workspace", "knowledge-management.md"),
]
# marker file (searched upward from cwd) -> doc
MARKER_RULES = [
    ("Cargo.toml", "rust-ai-project-setup.md"),
    ("package.json", "nodejs-typescript-setup.md"),
]


def has_marker(cwd, fname, depth=6):
    d = cwd
    for _ in range(depth):
        if os.path.exists(os.path.join(d, fname)):
            return True
        nd = os.path.dirname(d)
        if nd == d:
            break
        d = nd
    return False


def main():
    try:
        data = json.load(sys.stdin)
    except Exception as e:
        print(
            json.dumps(
                {"docs": [], "matcher": "cwd-path", "latency_ms": 0, "error": str(e)}
            )
        )
        return
    cwd = data.get("cwd") or ""
    found = {}  # name -> score (keep highest)
    for seg, doc in PATH_RULES:
        if seg in cwd:
            found[doc] = max(found.get(doc, 0), 0.9)
    for marker, doc in MARKER_RULES:
        if isinstance(cwd, str) and cwd and has_marker(cwd, marker):
            found[doc] = max(found.get(doc, 0), 0.95)
    docs = [{"name": n, "score": s, "signal": "cwd-path"} for n, s in found.items()]
    print(
        json.dumps(
            {
                "docs": docs,
                "matcher": "cwd-path",
                "latency_ms": int((time.time() - START) * 1000),
            }
        )
    )


if __name__ == "__main__":
    main()
