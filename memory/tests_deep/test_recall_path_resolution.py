from __future__ import annotations

from memory.recall import resolve_result_path


def test_card_and_entity_paths_are_root_relative() -> None:
    assert resolve_result_path({"source": "card", "id": "queue-card"}) == (
        "state",
        "memory/cards/queue-card.md",
    )
    assert resolve_result_path(
        {"source": "entity-summary", "id": "project:compiler"}
    ) == ("kb", "projects/compiler/summary.md")
    assert resolve_result_path(
        {"source": "entity-summary", "id": "area:reliability"}
    ) == ("kb", "areas/reliability/summary.md")


def test_unknown_or_unsafe_paths_fail_closed() -> None:
    assert (
        resolve_result_path({"source": "entity-summary", "id": "team:compiler"}) is None
    )
    assert resolve_result_path({"source": "card", "id": "../escape"}) is None
    assert (
        resolve_result_path({"source": "entity-summary", "id": "project:../escape"})
        is None
    )
    assert resolve_result_path({"source": "fixture", "id": "queue-card"}) is None
