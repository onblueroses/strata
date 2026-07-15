#!/usr/bin/env python3
"""Bounded SessionStart card index and entity-table rendering."""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from memory.config import MemoryConfig, load_config
from memory.telemetry import append_event

MAX_STDOUT_CHARS = 9999
TYPE_IMPORTANCE_PRIOR = {
    "user": 10.0,
    "safety": 10.0,
    "critical": 10.0,
    "feedback": 8.0,
    "project": 6.0,
    "memory": 5.0,
    "reference": 3.0,
}
TYPE_ORDER = (
    "user",
    "safety",
    "critical",
    "feedback",
    "project",
    "memory",
    "reference",
)
FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.S)
FIELD_RE_TEMPLATE = r"^[ \t]*{key}:[ \t]*(.+?)[ \t]*$"
CARD_PATH_HINT = "memory/cards/{id}.md (relative to STATE_DIR)"
UNREADABLE_HINT = "(unreadable card; inspect the configured card store)"
FAILURE_MARKER = (
    "...({count} card file(s) failed to load; inspect memory health telemetry)"
)


@dataclass(frozen=True)
class Card:
    card_id: str
    title: str
    description: str
    card_type: str
    path: Path
    importance: float
    critical: bool


def split_frontmatter(text: str) -> tuple[str, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return "", text
    return match.group(1), text[match.end() :]


def fm_get(frontmatter: str, key: str) -> str:
    pattern = FIELD_RE_TEMPLATE.format(key=re.escape(key))
    match = re.search(pattern, frontmatter, re.M)
    return match.group(1).strip() if match else ""


def fm_metadata_type(frontmatter: str) -> str:
    match = re.search(
        r"^[ \t]*metadata:[ \t]*\n(?P<body>(?:[ \t]+.+\n?)+)",
        frontmatter,
        re.M,
    )
    return fm_get(match.group("body"), "type") if match else ""


def fm_importance(frontmatter: str, card_type: str) -> float:
    for key in ("importance", "importance_score", "score"):
        raw = fm_get(frontmatter, key)
        if not raw:
            continue
        try:
            value = float(raw)
        except ValueError:
            continue
        if math.isfinite(value) and value > 0:
            return value
    return TYPE_IMPORTANCE_PRIOR.get(
        (card_type or "memory").lower(), TYPE_IMPORTANCE_PRIOR["memory"]
    )


def clean_scalar(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().strip('"').strip("'")).strip()


def snippet(text: str, limit: int = 170) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    cut = compact[:limit].rfind(" ")
    return compact[: cut if cut > 40 else limit].rstrip() + "..."


def extract_entities_table(index_text: str) -> str:
    lines = index_text.splitlines()
    for index, line in enumerate(lines):
        if not re.match(r"#{2,}\s+Entities\b", line.strip()):
            continue
        output = [line]
        in_table = False
        for next_line in lines[index + 1 :]:
            if next_line.startswith("|"):
                in_table = True
                output.append(next_line)
            elif in_table:
                break
            elif not next_line.strip():
                output.append(next_line)
            elif next_line.lstrip().startswith("#"):
                break
        if in_table:
            return "\n".join(output).rstrip() + "\n"
        break
    raise ValueError("MEMORY.md Entities table not found")


def valid_card_id(card_id: str) -> bool:
    if not card_id.strip() or card_id != card_id.strip():
        return False
    if card_id.splitlines() != [card_id]:
        return False
    try:
        card_id.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return not any(unicodedata.category(char).startswith("C") for char in card_id)


def scan_cards(config: MemoryConfig | None = None) -> tuple[list[Card], list[str]]:
    cfg = config or load_config()
    cards: list[Card] = []
    failures: list[str] = []
    if not cfg.cards_dir.exists():
        return cards, failures
    for path in sorted(cfg.cards_dir.glob("*.md")):
        if path.name == "MEMORY.md" or path.name.startswith("."):
            continue
        card_id = path.stem
        if not valid_card_id(card_id) or not path.is_file():
            failures.append(path.name)
            continue
        try:
            text = path.read_text(encoding="utf-8")
            frontmatter, body = split_frontmatter(text)
            card_type = clean_scalar(
                fm_get(frontmatter, "type") or fm_metadata_type(frontmatter) or "memory"
            )
            title = snippet(clean_scalar(fm_get(frontmatter, "name")), 120)
            description = clean_scalar(fm_get(frontmatter, "description")) or snippet(
                body
            )
            importance = fm_importance(frontmatter, card_type)
            critical = card_type.lower() in {"user", "safety", "critical"}
        except (OSError, UnicodeDecodeError, ValueError):
            failures.append(path.name)
            title, description, card_type = "", UNREADABLE_HINT, "memory"
            importance, critical = TYPE_IMPORTANCE_PRIOR["memory"], False
        cards.append(
            Card(
                card_id=card_id,
                title=title,
                description=description,
                card_type=card_type,
                path=path,
                importance=importance,
                critical=critical,
            )
        )
    positions = {card_type: index for index, card_type in enumerate(TYPE_ORDER)}

    def sort_key(card: Card) -> tuple[int, int | str, str]:
        card_type = card.card_type.lower()
        if card_type in positions:
            return (0, positions[card_type], card.card_id)
        return (1, card_type, card.card_id)

    return sorted(cards, key=sort_key), failures


def load_cards(
    now: float | None = None, config: MemoryConfig | None = None
) -> list[Card]:
    del now
    cards, _failures = scan_cards(config)
    return cards


def card_line(card: Card, desc_limit: int | None = 135, *, bare: bool = False) -> str:
    if bare:
        return f"- {card.card_id}"
    if desc_limit is None:
        return f"- CARD {card.card_id}: CRITICAL (type={card.card_type})"
    description = (
        f" -- {snippet(card.description, desc_limit)}" if card.description else ""
    )
    title = f" {card.title}" if card.title else ""
    return (
        f"- CARD {card.card_id}: CRITICAL{title} (type={card.card_type}){description}"
    )


def normalized_hint_value(value: str) -> str:
    return "".join(char for char in value.casefold() if char.isalnum())


def card_hint(card: Card, limit: int) -> str:
    title = normalized_hint_value(card.title)
    card_id = normalized_hint_value(card.card_id)
    title_restates_id = not title or not card_id or title in card_id or card_id in title
    source = card.description if title_restates_id else card.title
    return snippet(source, limit) if source else ""


def index_line(card: Card, hint_limit: int | None) -> str:
    hint = card_hint(card, hint_limit) if hint_limit is not None else ""
    return f"- {card.card_id}: {hint}" if hint else f"- {card.card_id}"


def hook_payload(context: str, hook_event_name: str = "SessionStart") -> str:
    return json.dumps(
        {
            "hookSpecificOutput": {
                "hookEventName": hook_event_name,
                "additionalContext": context,
            }
        },
        ensure_ascii=False,
        separators=(",", ":"),
    )


def hook_payload_bytes(context: str) -> int:
    return len(hook_payload(context).encode("utf-8"))


def split_entities_table_rows(entities_table: str) -> tuple[list[str], list[str]]:
    header: list[str] = []
    rows: list[str] = []
    table_lines = 0
    for line in entities_table.rstrip("\n").splitlines():
        if line.startswith("|"):
            (header if table_lines < 2 else rows).append(line)
            table_lines += 1
        else:
            header.append(line)
    return header, rows


def render_hot_overflow(
    digest_intro: str,
    critical_cards: list[Card],
    index_cards: list[Card],
    max_stdout_chars: int,
    failure_count: int = 0,
) -> tuple[str, list[str]]:
    hot_cards = sorted(
        critical_cards, key=lambda card: (-card.importance, card.card_id)
    )
    other_cards = sorted(index_cards, key=lambda card: (-card.importance, card.card_id))

    def render(
        critical_count: int, index_count: int, *, include_index_marker: bool
    ) -> tuple[str, list[str]]:
        context = digest_intro
        selected_hot = hot_cards[:critical_count]
        selected_other = other_cards[:index_count]
        if hot_cards:
            critical_lines = [card_line(card, None, bare=True) for card in selected_hot]
            omitted = len(hot_cards) - critical_count
            if omitted:
                critical_lines.append(
                    f"...({omitted} more never-trim cards; use the recall CLI)"
                )
            context += "## Never-Trim Cards\n" + "\n".join(critical_lines) + "\n\n"
        index_lines = [index_line(card, None) for card in selected_other]
        omitted = len(other_cards) - index_count
        if omitted and include_index_marker:
            index_lines.append(f"...({omitted} more cards; use the recall CLI)")
        if failure_count:
            index_lines.append(FAILURE_MARKER.format(count=failure_count))
        if index_lines:
            context += "## Card Index\n" + "\n".join(index_lines) + "\n"
        ids = [card.card_id for card in selected_hot + selected_other]
        return context.rstrip() + "\n", ids

    def fits(critical_count: int, index_count: int, marker: bool) -> bool:
        context, _ids = render(critical_count, index_count, include_index_marker=marker)
        return hook_payload_bytes(context) < max_stdout_chars

    def max_fitting(high: int, predicate: object) -> int:
        if not callable(predicate):
            return 0
        low, best = 0, 0
        while low <= high:
            middle = (low + high) // 2
            if predicate(middle):
                best = middle
                low = middle + 1
            else:
                high = middle - 1
        return best

    if fits(len(hot_cards), 0, True):
        count = max_fitting(
            len(other_cards), lambda value: fits(len(hot_cards), value, True)
        )
        return render(len(hot_cards), count, include_index_marker=True)
    if fits(0, 0, False):
        count = max_fitting(len(hot_cards), lambda value: fits(value, 0, False))
        return render(count, 0, include_index_marker=False)
    minimal = (
        "# Memory Digest\n...(card corpus exceeds the output cap; use the recall CLI)\n"
    )
    return (minimal, []) if hook_payload_bytes(minimal) < max_stdout_chars else ("", [])


def build_entities_table(
    max_stdout_chars: int = MAX_STDOUT_CHARS,
    config: MemoryConfig | None = None,
) -> tuple[str, list[str], str]:
    cfg = config or load_config()
    try:
        entities_table = extract_entities_table(
            cfg.memory_index.read_text(encoding="utf-8")
        )
    except (OSError, ValueError):
        return "", [], "no_hot_state"
    if hook_payload_bytes(entities_table) < max_stdout_chars:
        return entities_table, [], "ok"
    header, rows = split_entities_table_rows(entities_table)
    total_rows = len(rows)
    while rows:
        rows.pop()
        omitted = total_rows - len(rows)
        context = (
            "\n".join(header + rows)
            + f"\n...({omitted} more entities; inspect MEMORY.md)\n"
        )
        if hook_payload_bytes(context) < max_stdout_chars:
            return context, [], "compacted"
    context = (
        "\n".join(header) + f"\n...({total_rows} more entities; inspect MEMORY.md)\n"
    )
    if hook_payload_bytes(context) < max_stdout_chars:
        return context, [], "compacted"
    breadcrumb = "...(entity table exceeds the output cap; inspect MEMORY.md)\n"
    if hook_payload_bytes(breadcrumb) < max_stdout_chars:
        return breadcrumb, [], "table_state_exceeds_cap"
    return "", [], "table_state_exceeds_cap"


def build_digest(
    max_stdout_chars: int = MAX_STDOUT_CHARS,
    config: MemoryConfig | None = None,
) -> tuple[str, list[str], str]:
    cfg = config or load_config()
    if not cfg.digest_enabled:
        return "", [], "disabled"
    cards, failures = scan_cards(cfg)
    if not cards:
        return "", [], "no_hot_state" if not failures else "card_load_errors"
    critical_cards = [card for card in cards if card.critical]
    index_cards = [card for card in cards if not card.critical]
    intro = (
        "# Memory Digest\n"
        "This is the complete card corpus. Read a card at "
        f"`{CARD_PATH_HINT}`; use the recall CLI for a judged search.\n\n"
    )

    def render(
        desc_limit: int | None, hint_limit: int | None, *, bare: bool = False
    ) -> tuple[str, list[str]]:
        context = intro
        if critical_cards:
            context += (
                "## Never-Trim Cards\n"
                + "\n".join(
                    card_line(card, desc_limit, bare=bare) for card in critical_cards
                )
                + "\n\n"
            )
        index_lines = [index_line(card, hint_limit) for card in index_cards]
        if failures:
            index_lines.append(FAILURE_MARKER.format(count=len(failures)))
        if index_lines:
            context += "## Card Index\n" + "\n".join(index_lines) + "\n"
        return context.rstrip() + "\n", [card.card_id for card in cards]

    ladder = (
        (135, 100, False),
        (60, 60, False),
        (None, None, False),
        (None, None, True),
    )
    for rung, (desc_limit, hint_limit, bare) in enumerate(ladder):
        context, ids = render(desc_limit, hint_limit, bare=bare)
        if hook_payload_bytes(context) < max_stdout_chars:
            status = "card_load_errors" if failures else ("compacted" if rung else "ok")
            return context, ids, status
    context, ids = render_hot_overflow(
        intro, critical_cards, index_cards, max_stdout_chars, len(failures)
    )
    if not context:
        return "", [], "critical_state_exceeds_cap"
    critical_ids = {card.card_id for card in critical_cards}
    if critical_cards and not critical_ids.issubset(ids):
        return context, ids, "critical_overflow"
    if len(ids) < len(cards):
        return context, ids, "cards_dropped"
    return context, ids, "compacted"


def record_health(
    status: str, detail: str = "", config: MemoryConfig | None = None
) -> None:
    cfg = config or load_config()
    if cfg.telemetry_enabled:
        append_event(
            cfg.telemetry_dir / "memory-digest-health.jsonl",
            "memory_digest_health",
            {"status": status, "detail": detail[:500]},
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--text", action="store_true")
    parser.add_argument("--ids-json", action="store_true")
    parser.add_argument("--section", choices=("cards", "table"), default="cards")
    parser.add_argument("--max-stdout-chars", type=int, default=MAX_STDOUT_CHARS)
    args = parser.parse_args(argv)
    cfg = load_config()
    try:
        if os.environ.get("STRATA_MEMORY_DIGEST_FORCE_ERROR"):
            raise RuntimeError("forced digest failure")
        if args.section == "cards":
            context, ids, status = build_digest(args.max_stdout_chars, cfg)
        else:
            context, ids, status = build_entities_table(args.max_stdout_chars, cfg)
        if not context:
            if status not in {"no_hot_state", "disabled"}:
                record_health(status, config=cfg)
            if args.ids_json:
                print("[]")
            return 0
        if status != "ok":
            sys.stderr.write(f"memory-digest: status={status}\n")
            record_health(status, config=cfg)
        if args.ids_json:
            print(json.dumps(ids, ensure_ascii=False))
        elif args.text:
            sys.stdout.write(context)
        else:
            sys.stdout.write(hook_payload(context))
        return 0
    except Exception as exc:
        record_health("exception", f"{type(exc).__name__}: {exc}", cfg)
        if args.ids_json:
            print("[]")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
