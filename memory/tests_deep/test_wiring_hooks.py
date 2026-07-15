"""Verify the memory subsystem is wired into the host strata install.

These assertions read the repo's shipped settings.json and hook wrappers (like
test_invariants.py, this is a repo-level test, not a hermetic engine test). When the
memory package is used standalone without a host settings.json, the wiring checks skip.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SETTINGS = REPO_ROOT / "settings.json"
HOOKS = REPO_ROOT / "hooks"


def _event_commands(settings: dict, event: str) -> list[str]:
    commands: list[str] = []
    for group in settings.get("hooks", {}).get(event, []):
        for hook in group.get("hooks", []):
            command = hook.get("command")
            if isinstance(command, str):
                commands.append(command)
    return commands


def _load_settings() -> dict:
    if not SETTINGS.exists():
        pytest.skip("standalone memory subsystem: no host settings.json to verify")
    return json.loads(SETTINGS.read_text(encoding="utf-8"))


def test_session_start_wires_digest_and_table() -> None:
    """digest (cards) and entity table both register on SessionStart."""
    commands = _event_commands(_load_settings(), "SessionStart")
    assert any("memory-digest.sh" in c for c in commands)
    assert any("memory-entities.sh" in c for c in commands)


def test_session_end_wires_access_log() -> None:
    """access-log reconcile registers on SessionEnd."""
    commands = _event_commands(_load_settings(), "SessionEnd")
    assert any("memory-access-log.sh" in c for c in commands)


def test_hook_wrappers_exist_and_invoke_the_engine() -> None:
    """The three wrappers ship and call the engine entry points they promise."""
    if not HOOKS.exists():
        pytest.skip("standalone memory subsystem: no host hooks/ directory to verify")
    digest = (HOOKS / "memory-digest.sh").read_text(encoding="utf-8")
    entities = (HOOKS / "memory-entities.sh").read_text(encoding="utf-8")
    access_log = (HOOKS / "memory-access-log.sh").read_text(encoding="utf-8")
    assert "-m memory.digest" in digest and "--section cards" in digest
    assert "-m memory.digest" in entities and "--section table" in entities
    assert "-m memory.reconcile" in access_log and "--access-log" in access_log
