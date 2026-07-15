from __future__ import annotations

import pytest

from memory import regen_memory_index as regen
from memory.config import MemoryConfig


def _seed_index(config: MemoryConfig) -> str:
    original = (
        "# Existing\n\n## Entities\n\n"
        "| Entity | Path | Status | last_verified |\n"
        "|---|---|---|---|\n"
        "| compiler | `projects/compiler` | active | 2026-01-01 |\n\n"
        "**Dormant**: retired-service\n"
    )
    config.memory_index.write_text(original, encoding="utf-8")
    return original


def test_default_writes_proposal_without_mutating_live(
    memory_config: MemoryConfig,
) -> None:
    original = _seed_index(memory_config)
    assert regen.main([]) == 0
    assert memory_config.memory_index.read_text(encoding="utf-8") == original
    assert memory_config.index_proposal.is_file()
    proposal = memory_config.index_proposal.read_text(encoding="utf-8")
    assert proposal.startswith("# Memory Index")
    assert "## Subsystem Docs" in proposal


def test_proposal_path_cannot_alias_live_index(
    memory_config: MemoryConfig, capsys: pytest.CaptureFixture[str]
) -> None:
    original = _seed_index(memory_config)
    assert regen.main(["--proposal", str(memory_config.memory_index)]) == 2
    assert memory_config.memory_index.read_text(encoding="utf-8") == original
    assert "refusing" in capsys.readouterr().err


def test_proposal_path_cannot_escape_state_cache(
    memory_config: MemoryConfig, capsys: pytest.CaptureFixture[str]
) -> None:
    original = _seed_index(memory_config)
    escaped = memory_config.state_dir / "outside-cache.md"
    assert regen.main(["--proposal", str(escaped)]) == 2
    assert memory_config.memory_index.read_text(encoding="utf-8") == original
    assert not escaped.exists()
    assert "must stay under memory/cache" in capsys.readouterr().err


def test_apply_backs_up_exact_preimage(memory_config: MemoryConfig) -> None:
    original = _seed_index(memory_config)
    assert regen.main(["--apply"]) == 0
    backups = list(memory_config.backups_dir.glob("MEMORY.*.bak"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == original
    assert memory_config.memory_index.read_text(encoding="utf-8").startswith(
        "# Memory Index"
    )


def test_byte_cap_refuses_to_trim_entity_registry(memory_config: MemoryConfig) -> None:
    _seed_index(memory_config)
    with pytest.raises(RuntimeError, match="refusing to trim"):
        regen.main(["--max-bytes", "100"])
    assert not memory_config.index_proposal.exists()


def test_configured_kb_glob_updates_and_adds_entities(
    memory_config: MemoryConfig,
) -> None:
    _seed_index(memory_config)
    compiler = memory_config.kb_dir / "projects" / "compiler" / "summary.md"
    compiler.parent.mkdir(parents=True, exist_ok=True)
    compiler.write_text("# Compiler\nlast_verified: 2026-05-04\n", encoding="utf-8")
    reliability = memory_config.kb_dir / "areas" / "reliability" / "summary.md"
    reliability.parent.mkdir(parents=True, exist_ok=True)
    reliability.write_text(
        "# Reliability\n**Last verified:** 2026-04-03\n", encoding="utf-8"
    )
    assert regen.main([]) == 0
    output = memory_config.index_proposal.read_text(encoding="utf-8")
    assert "| compiler | `projects/compiler` | active | 2026-05-04 |" in output
    assert (
        "| reliability | `areas/reliability` | active (auto-added; curate status) | 2026-04-03 |"
        in output
    )
    assert "retired-service" in output
