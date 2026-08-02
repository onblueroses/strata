#!/usr/bin/env python3
"""Render per-file era-audit briefs from a findings JSON file."""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path


def terminal_safe(value: object) -> str:
    text = str(value)
    return "".join(
        char
        if char == "\n" or unicodedata.category(char) not in {"Cc", "Cf"}
        else f"\\u{ord(char):04x}"
        for char in text
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--findings", type=Path, required=True)
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()
    data = json.loads(args.findings.read_text())
    records = data.get("files", data) if isinstance(data, dict) else data
    by_file = {row["file"]: row for row in records}
    missing = [path for path in args.files if path not in by_file]
    if missing:
        print(f"NOT IN AUDIT: {terminal_safe(missing)}", file=sys.stderr)
        print("Known files:", file=sys.stderr)
        for path in sorted(by_file):
            print(f"  {terminal_safe(path)}", file=sys.stderr)
        return 1
    for path in args.files:
        row = by_file[path]
        print(
            f"{'=' * 78}\nFILE: {terminal_safe(path)}    "
            f"DISPOSITION: {terminal_safe(row['disposition'])}"
        )
        print(f"NOTES: {terminal_safe(row.get('notes', ''))}\n")
        for index, finding in enumerate(row["stale_findings"], 1):
            print(f"--- finding {index} [{terminal_safe(finding['category'])}] ---")
            print(f"QUOTE:\n{terminal_safe(finding['quote'])}")
            print(f"WHY STALE: {terminal_safe(finding['why_stale'])}")
            print(f"FIX DIRECTION: {terminal_safe(finding['fix_direction'])}")
            refs = finding.get("ground_truth_refs") or []
            if refs:
                print(f"GROUND TRUTH: {terminal_safe(', '.join(refs))}")
            print()
        capabilities = row.get("underused_capabilities") or []
        if capabilities:
            print(
                "UNDERUSED CAPABILITIES (optional; apply only when ground truth confirms them):"
            )
            for capability in capabilities:
                print(f"  - {terminal_safe(capability)}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
