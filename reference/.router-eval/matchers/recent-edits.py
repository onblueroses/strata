#!/usr/bin/env python3
"""recent-edits matcher — reads the session transcript (bounded tail), extracts this
session's Edit/Write file paths, maps extension/dir -> docs. Deterministic, free.
Bounded read (last N lines) so a huge transcript never blows the 2000ms hook budget."""

import sys
import json
import time
import os

START = time.time()
MAX_LINES = 200

EXT_RULES = {
    ".rs": "rust-ai-project-setup.md",
    ".ts": "nodejs-typescript-setup.md",
    ".tsx": "nodejs-typescript-setup.md",
    ".js": "nodejs-typescript-setup.md",
    ".jsx": "nodejs-typescript-setup.md",
}
PATH_RULES = [
    ("/.claude/skills", "skill-design-principles.md"),
    ("/.claude/hooks", "claude-code-patterns.md"),
    ("/workspace/", "knowledge-management.md"),
]


def tail_lines(path, n):
    """Last n lines without slurping the whole file."""
    try:
        with open(path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block = 4096
            data = b""
            while size > 0 and data.count(b"\n") <= n:
                step = min(block, size)
                size -= step
                f.seek(size)
                data = f.read(step) + data
            return data.decode("utf-8", "replace").splitlines()[-n:]
    except Exception:
        return []


def edited_paths(transcript_path):
    paths = []
    for line in tail_lines(transcript_path, MAX_LINES):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        content = (obj.get("message") or {}).get("content")
        if not isinstance(content, list):
            continue
        for item in content:
            if (
                isinstance(item, dict)
                and item.get("type") == "tool_use"
                and item.get("name") in ("Edit", "Write", "NotebookEdit")
            ):
                fp = (item.get("input") or {}).get("file_path")
                if fp:
                    paths.append(fp)
    return paths


def main():
    try:
        data = json.load(sys.stdin)
    except Exception as e:
        print(
            json.dumps(
                {
                    "docs": [],
                    "matcher": "recent-edits",
                    "latency_ms": 0,
                    "error": str(e),
                }
            )
        )
        return
    tx = data.get("transcript_path")
    found = {}
    if tx and os.path.exists(tx):
        for fp in edited_paths(tx):
            ext = os.path.splitext(fp)[1].lower()
            if ext in EXT_RULES:
                doc = EXT_RULES[ext]
                found[doc] = max(found.get(doc, 0), 0.85)
            for seg, doc in PATH_RULES:
                if seg in fp:
                    found[doc] = max(found.get(doc, 0), 0.85)
    docs = [{"name": n, "score": s, "signal": "recent-edits"} for n, s in found.items()]
    print(
        json.dumps(
            {
                "docs": docs,
                "matcher": "recent-edits",
                "latency_ms": int((time.time() - START) * 1000),
            }
        )
    )


if __name__ == "__main__":
    main()
