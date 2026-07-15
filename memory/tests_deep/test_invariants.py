from __future__ import annotations

import re
from pathlib import Path

from memory.config import load_config

MEMORY_ROOT = Path(__file__).resolve().parents[1]


def test_all_runtime_roots_follow_the_config_seam() -> None:
    config = load_config()
    assert config.cards_dir == config.state_dir / "memory" / "cards"
    assert config.cache_dir == config.state_dir / "memory" / "cache"
    assert config.session_state_dir == config.state_dir / "memory" / "session-state"
    assert config.backups_dir == config.state_dir / "memory" / "backups"
    assert config.telemetry_dir == config.state_dir / "telemetry"
    assert config.embedding_model is None


def test_source_tree_contains_no_private_path_or_calibration_artifacts() -> None:
    forbidden = [
        "~/" + "life",
        "~/" + "to-delete",
        "projects/" + "-home-",
        "minishlab/" + "potion-base-8M",
    ]
    text_files = [
        path
        for path in MEMORY_ROOT.rglob("*")
        if path.is_file()
        and "__pycache__" not in path.parts
        and path.suffix not in {".pyc", ".npy"}
    ]
    violations = {
        str(path.relative_to(MEMORY_ROOT)): token
        for path in text_files
        for token in forbidden
        if token in path.read_text(encoding="utf-8", errors="ignore")
    }
    assert not violations
    absolute_home = re.compile(re.escape("/" + "home/") + r"[A-Za-z0-9._-]+")
    absolute_violations = [
        str(path.relative_to(MEMORY_ROOT))
        for path in text_files
        if path != Path(__file__)
        and absolute_home.search(path.read_text(encoding="utf-8", errors="ignore"))
    ]
    assert not absolute_violations
    assert not (MEMORY_ROOT / "eval" / "calib_queries.json").exists()
    assert not (MEMORY_ROOT / "eval" / "router_harness_negatives.json").exists()
    assert not (Path(__file__).parent / "test_label_sheet_apply.py").exists()


def test_expected_deep_invariants_are_present() -> None:
    expected = {
        "test_digest_nevertrim_overflow.py",
        "test_digest_reflects_corpus.py",
        "test_digest_table_fallback.py",
        "test_e2e_session.py",
        "test_engine_bm25_rank.py",
        "test_engine_cache_invalidation.py",
        "test_engine_determinism.py",
        "test_engine_isolation_dupe.py",
        "test_engine_low_confidence.py",
        "test_engine_model2vec_absent.py",
        "test_engine_rrf_fusion.py",
        "test_engine_telemetry.py",
        "test_engine_top_terms_invariance.py",
        "test_recall_paraphrase_recovery.py",
        "test_recall_path_resolution.py",
        "test_reconcile_accesslog_rotation.py",
        "test_regen_index_guards.py",
        "test_probe_runner.py",
        "test_wiring_hooks.py",
    }
    present = {path.name for path in Path(__file__).parent.glob("test_*.py")}
    assert expected <= present
