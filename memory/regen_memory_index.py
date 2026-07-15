#!/usr/bin/env python3
"""Generate or apply a guarded MEMORY.md entity-index proposal."""

from __future__ import annotations

import argparse
import difflib
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from memory.config import MemoryConfig, load_config
from memory.digest import extract_entities_table, split_entities_table_rows
from memory.reconcile import write_text_atomic

MAX_INDEX_BYTES = 20_000
LAST_VERIFIED_RE = re.compile(
    r"last[ _]verified:?\*{0,2}\s*(\d{4}-\d{2}-\d{2})", re.IGNORECASE
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--diff", action="store_true")
    parser.add_argument("--proposal", type=Path)
    parser.add_argument("--max-bytes", type=int, default=MAX_INDEX_BYTES)
    return parser.parse_args(argv)


def extract_dormant_archive_block(index_text: str, entities_table: str) -> str:
    start = index_text.find(entities_table)
    if start < 0:
        return ""
    lines: list[str] = []
    for line in index_text[start + len(entities_table) :].splitlines():
        if line.startswith("## Subsystem Docs"):
            break
        lines.append(line)
    return "\n".join(lines).strip()


def subsystem_docs_block() -> str:
    return (
        "## Subsystem Docs\n\n"
        "Configuration and card format: `memory/README.md` and "
        "`memory/CARD-SCHEMA.md` under STRATA_HOME."
    )


def _split_table_row(line: str) -> list[str]:
    cells = [cell.strip() for cell in line.split("|")]
    if cells and not cells[0]:
        cells = cells[1:]
    if cells and not cells[-1]:
        cells = cells[:-1]
    return cells


def _summary_last_verified(text: str) -> str | None:
    dates = LAST_VERIFIED_RE.findall(text)
    return max(dates) if dates else None


def entities_on_disk(
    config: MemoryConfig | None = None,
) -> dict[str, tuple[str, str | None]]:
    cfg = config or load_config()
    found: dict[str, tuple[str, str | None]] = {}
    for kind in ("projects", "areas"):
        for summary in sorted((cfg.kb_dir / kind).glob("*/summary.md")):
            name = summary.parent.name
            if name in found or not summary.is_file():
                continue
            try:
                text = summary.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                text = ""
            found[name] = (f"{kind}/{name}", _summary_last_verified(text))
    return found


def _dormant_archive_names(block: str) -> set[str]:
    names: set[str] = set()
    for line in block.splitlines():
        if "**Dormant**" not in line and "**Archived" not in line:
            continue
        _, _, tail = line.partition(":")
        tail = re.sub(r"\([^)]*\)", "", tail)
        for token in tail.split(","):
            candidate = token.strip(" .")
            if re.fullmatch(r"[a-z0-9][a-z0-9-]*", candidate):
                names.add(candidate)
    return names


def reconcile_entities_table(
    entities_table: str,
    dormant_archive: str,
    config: MemoryConfig | None = None,
) -> str:
    on_disk = entities_on_disk(config)
    if not on_disk:
        return entities_table
    header, rows = split_entities_table_rows(entities_table)
    pipe_headers = [line for line in header if line.startswith("|")]
    if not pipe_headers:
        return entities_table
    column_names = [cell.lower() for cell in _split_table_row(pipe_headers[0])]
    column_count = len(column_names)
    verified_index = (
        column_names.index("last_verified") if "last_verified" in column_names else -1
    )
    dormant_names = _dormant_archive_names(dormant_archive)
    table_names: set[str] = set()
    rebuilt: list[str] = []
    for row in rows:
        cells = _split_table_row(row)
        if not cells or not cells[0]:
            rebuilt.append(row)
            continue
        name = cells[0]
        table_names.add(name)
        disk = on_disk.get(name)
        if disk and disk[1] and 0 <= verified_index < len(cells):
            current = cells[verified_index]
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", current) or disk[1] > current:
                cells[verified_index] = disk[1]
                row = "| " + " | ".join(cells) + " |"
        rebuilt.append(row)
    for name in sorted(on_disk):
        if name in table_names or name in dormant_names:
            continue
        relative_path, last_verified = on_disk[name]
        cells = [""] * max(column_count, 1)
        cells[0] = name
        if column_count > 1:
            cells[1] = f"`{relative_path}`"
        if column_count > 2:
            cells[2] = "active (auto-added; curate status)"
        if 0 <= verified_index < column_count:
            cells[verified_index] = last_verified or "(no last_verified)"
        rebuilt.append("| " + " | ".join(cells) + " |")
    return "\n".join([*header, *rebuilt])


def render_index(
    live_text: str, max_bytes: int, config: MemoryConfig | None = None
) -> str:
    entities_table = extract_entities_table(live_text).rstrip()
    dormant_archive = extract_dormant_archive_block(live_text, entities_table + "\n")
    entities_table = reconcile_entities_table(entities_table, dormant_archive, config)
    parts = ["# Memory Index", "", entities_table]
    if dormant_archive:
        parts.extend(["", dormant_archive])
    parts.extend(["", subsystem_docs_block(), ""])
    output = "\n".join(parts)
    if len(output.encode("utf-8")) > max_bytes:
        raise RuntimeError(
            "Entities table plus documentation block exceed the byte cap; refusing to trim"
        )
    return output


def backup_live_index(config: MemoryConfig | None = None) -> Path:
    cfg = config or load_config()
    cfg.backups_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = cfg.backups_dir / f"MEMORY.{stamp}.bak"
    shutil.copy2(cfg.memory_index, backup)
    return backup


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cfg = load_config()
    proposal = args.proposal or cfg.index_proposal
    live_text = cfg.memory_index.read_text(encoding="utf-8")
    output = render_index(live_text, args.max_bytes, cfg)
    if args.diff:
        sys.stdout.writelines(
            difflib.unified_diff(
                live_text.splitlines(keepends=True),
                output.splitlines(keepends=True),
                fromfile="MEMORY.md",
                tofile="MEMORY.md (generated)",
            )
        )
    if args.apply:
        backup = backup_live_index(cfg)
        write_text_atomic(cfg.memory_index, output)
        print(
            "applied memory/cards/MEMORY.md; "
            f"backup=memory/backups/{backup.name}; bytes={len(output.encode('utf-8'))}"
        )
        return 0
    if proposal.resolve() == cfg.memory_index.resolve():
        print(
            "refusing: --proposal resolves to the live MEMORY.md; use --apply",
            file=sys.stderr,
        )
        return 2
    if not proposal.resolve().is_relative_to(cfg.cache_dir.resolve()):
        print(
            "refusing: --proposal must stay under memory/cache in STATE_DIR",
            file=sys.stderr,
        )
        return 2
    write_text_atomic(proposal, output)
    print(
        f"wrote proposal {proposal.name}; live unchanged; bytes={len(output.encode('utf-8'))}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
