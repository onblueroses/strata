#!/usr/bin/env python3
"""Catch colors that will never remap in dark mode.

The hand-authored SVG idiom themes a file with one @media (prefers-color-scheme: dark)
block of attribute selectors: [fill="#ffffff"] { fill: #111827; }. A fill or stroke the
author writes but forgets to map is invisible in review, because the file looks correct
in light mode and only breaks for dark-mode readers.

Usage:
    svg_theme_lint.py FILE.svg [FILE.svg ...]
    svg_theme_lint.py doc/img/*.svg
    svg_theme_lint.py --quiet doc/img/*.svg     # only failures

Exit status is 1 if any file has unmapped colors, so it drops straight into a pre-commit
hook or CI step.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

# Presentation attributes on elements: fill="#abc123". Also catches them inside style
# blocks, which is why mapped values are subtracted rather than matched positionally.
ATTR_RE = re.compile(r'\b(fill|stroke)\s*=\s*"(#[0-9a-fA-F]{3,8})"')

# Selector heads inside the dark-mode block: [fill="#ffffff"] { ... }
SELECTOR_RE = re.compile(r'\[\s*(fill|stroke)\s*=\s*"(#[0-9a-fA-F]{3,8})"\s*\]')

# The dark-mode block itself. Non-greedy to the matching close is not possible with a
# flat regex, so take everything from the @media to the end of the <style> element and
# let the selector regex pick mapped values out of it.
DARK_BLOCK_RE = re.compile(
    r"@media[^{]*prefers-color-scheme\s*:\s*dark.*?</style>", re.S | re.I
)
STYLE_RE = re.compile(r"<style\b.*?</style>", re.S | re.I)


def norm(hex_color: str) -> str:
    """Normalize #ABC and #AABBCC to one comparable form.

    Shorthand expands so #fff and #ffffff are the same color, which they are; the
    corpus mixes both and a naive string compare reports false unmapped values.
    """
    h = hex_color.lower()
    if len(h) == 4:  # #abc -> #aabbcc
        return "#" + "".join(c * 2 for c in h[1:])
    return h


def audit(path: Path) -> tuple[list[tuple[str, str]], bool]:
    """Return (unmapped [(attr, color)], has_dark_block)."""
    text = path.read_text(encoding="utf-8", errors="replace")

    dark = DARK_BLOCK_RE.search(text)
    has_dark = dark is not None
    mapped = {
        (a, norm(c)) for a, c in SELECTOR_RE.findall(dark.group(0) if dark else "")
    }

    # Authored colors are those outside any <style> element: a value appearing only
    # inside CSS is a mapping target, not a mark to be themed.
    markup = STYLE_RE.sub("", text)
    authored = {(a, norm(c)) for a, c in ATTR_RE.findall(markup)}

    return sorted(authored - mapped), has_dark


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("files", nargs="+", type=Path)
    ap.add_argument(
        "--quiet", "-q", action="store_true", help="print only files that fail"
    )
    args = ap.parse_args()

    failed = 0
    for path in args.files:
        if not path.is_file():
            print(f"{path}: not a file", file=sys.stderr)
            failed += 1
            continue

        unmapped, has_dark = audit(path)

        if not has_dark:
            print(
                f"{path}: NO DARK-MODE BLOCK "
                f"(add @media (prefers-color-scheme: dark) or the file is light-only)"
            )
            failed += 1
            continue

        if unmapped:
            listed = ", ".join(f'{a}="{c}"' for a, c in unmapped)
            print(f"{path}: UNMAPPED {listed}")
            failed += 1
        elif not args.quiet:
            print(f"{path}: ok")

    if failed:
        print(
            f"\n{failed} file(s) with colors that will not remap in dark mode.",
            file=sys.stderr,
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
