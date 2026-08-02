#!/usr/bin/env python3
"""Measure era-audit corpus size, model-facing details wrappers, and skill descriptions."""

from __future__ import annotations

import argparse
import ast
import json
import re
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from era_audit import DEFAULT_EXCLUDES, DEFAULT_INCLUDES, discover


PRIMARY_INCLUDES = (
    "CLAUDE.md",
    "**/CLAUDE.md",
    "AGENTS.md",
    "**/AGENTS.md",
    "commands/*.md",
    "agents/*.md",
    "skills/**/SKILL.md",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def quartiles(values: list[int]) -> dict[str, float | int | None]:
    if not values:
        return {
            "min": None,
            "q1": None,
            "median": None,
            "q3": None,
            "max": None,
            "mean": None,
        }
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    lower = ordered[:midpoint]
    upper = ordered[midpoint + (len(ordered) % 2) :]
    return {
        "min": ordered[0],
        "q1": statistics.median(lower) if lower else ordered[0],
        "median": statistics.median(ordered),
        "q3": statistics.median(upper) if upper else ordered[-1],
        "max": ordered[-1],
        "mean": sum(ordered) / len(ordered),
    }


def fallback_description(frontmatter: str) -> str | None:
    lines = frontmatter.splitlines()
    for index, raw in enumerate(lines):
        if not raw.startswith("description:"):
            continue
        value = raw.split(":", 1)[1].strip()
        if value in {"|", ">", "|-", ">-", "|+", ">+"}:
            collected = []
            for continuation in lines[index + 1 :]:
                if continuation.startswith((" ", "\t")) or not continuation.strip():
                    collected.append(continuation.strip())
                else:
                    break
            separator = "\n" if value.startswith("|") else " "
            return separator.join(collected).strip()
        if value.startswith(('"', "'")):
            try:
                parsed = ast.literal_eval(value)
                return parsed if isinstance(parsed, str) else str(parsed)
            except (SyntaxError, ValueError):
                return value.strip('"').strip("'")
        return value
    return None


def read_description(path: Path) -> tuple[str | None, str | None]:
    text = path.read_text(errors="replace")
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        return None, "missing frontmatter"
    frontmatter = text.split("---\n", 2)[1]
    try:
        import yaml

        data = yaml.safe_load(frontmatter)
        value = data.get("description") if isinstance(data, dict) else None
        return (value if isinstance(value, str) else None), None
    except ImportError:
        value = fallback_description(frontmatter)
        return (
            value,
            None if value is not None else "description unavailable without PyYAML",
        )
    except Exception as exc:  # noqa: BLE001 - report parser fault in metrics
        return None, str(exc)


def detail_measurement(root: Path, paths: list[Path]) -> dict[str, Any]:
    by_directory: dict[str, dict[str, Any]] = {}
    total = 0
    for path in paths:
        text = path.read_text(errors="replace")
        count = len(
            re.findall(r"^\s*<details(?:\s[^>]*)?>\s*$", text, flags=re.MULTILINE)
        )
        if not count:
            continue
        relative = path.relative_to(root).as_posix()
        directory = relative.split("/", 1)[0] if "/" in relative else "."
        row = by_directory.setdefault(
            directory, {"openings": 0, "file_count": 0, "files": []}
        )
        row["openings"] += count
        row["file_count"] += 1
        row["files"].append({"file": relative, "openings": count})
        total += count
    return {
        "basis": "standalone <details> opening tags in the primary model-facing corpus",
        "openings": total,
        "by_directory": dict(sorted(by_directory.items())),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--description-threshold",
        type=int,
        help="Operator-supplied character threshold for an offender list",
    )
    args = parser.parse_args()
    root = args.root.resolve()
    excludes = list(DEFAULT_EXCLUDES)
    corpus = discover(root, DEFAULT_INCLUDES, excludes)
    primary = discover(root, PRIMARY_INCLUDES, excludes)
    descriptions = []
    parse_errors = []
    for path in sorted(root.glob("skills/**/SKILL.md")):
        if not path.is_file() or matches_excluded(
            path.relative_to(root).as_posix(), excludes
        ):
            continue
        description, error = read_description(path)
        if error:
            parse_errors.append(
                {"file": path.relative_to(root).as_posix(), "error": error}
            )
        if description is not None:
            descriptions.append(
                {
                    "file": path.relative_to(root).as_posix(),
                    "characters": len(description),
                    "utf8_bytes": len(description.encode()),
                }
            )
    char_values = [row["characters"] for row in descriptions]
    byte_values = [row["utf8_bytes"] for row in descriptions]
    above_threshold = None
    if args.description_threshold is not None:
        above_threshold = {
            "threshold_characters": args.description_threshold,
            "basis": "operator supplied",
            "files": sorted(
                (
                    row
                    for row in descriptions
                    if row["characters"] > args.description_threshold
                ),
                key=lambda row: (-row["characters"], row["file"]),
            ),
        }
    result = {
        "measured_at": now_iso(),
        "root_label": root.name,
        "corpus": {
            "basis": "default era-audit include and exclude patterns",
            "file_count": len(corpus),
            "bytes": sum(path.stat().st_size for path in corpus),
            "lines": sum(
                len(path.read_text(errors="replace").splitlines()) for path in corpus
            ),
            "include_patterns": list(DEFAULT_INCLUDES),
            "exclude_patterns": excludes,
        },
        "primary_model_facing": {
            "basis": "CLAUDE.md, AGENTS.md, commands/*.md, agents/*.md, and skills/**/SKILL.md",
            "file_count": len(primary),
            "details": detail_measurement(root, primary),
        },
        "skill_descriptions": {
            "basis": "decoded frontmatter description text in skills/**/SKILL.md",
            "count": len(descriptions),
            "characters": quartiles(char_values),
            "utf8_bytes": quartiles(byte_values),
            "above_threshold": above_threshold,
            "all": sorted(
                descriptions, key=lambda row: (-row["characters"], row["file"])
            ),
            "parse_errors": parse_errors,
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    chars = result["skill_descriptions"]["characters"]
    details = result["primary_model_facing"]["details"]
    print(
        f"WROTE {args.output} corpus_files={len(corpus)} primary_files={len(primary)} "
        f"details={details['openings']} descriptions={len(descriptions)} median_chars={chars['median']}"
    )
    return 0


def matches_excluded(path: str, patterns: list[str]) -> bool:
    import fnmatch

    return any(fnmatch.fnmatch(path, pattern) for pattern in patterns)


if __name__ == "__main__":
    raise SystemExit(main())
