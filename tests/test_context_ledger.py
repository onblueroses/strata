"""Tests for the offline context-composition ledger."""

from __future__ import annotations

import contextlib
import importlib.util
import itertools
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "telemetry" / "context_ledger.py"
_MODULE_IDS = itertools.count()


@contextlib.contextmanager
def patched_env(**updates: str | None):
    old = {key: os.environ.get(key) for key in updates}
    try:
        for key, value in updates.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def load_context_ledger(
    strata_home: Path,
    *,
    state_dir: Path | None = None,
    telemetry_dir: Path | None = None,
    config_repo: Path | None = None,
):
    with patched_env(
        STRATA_HOME=str(strata_home),
        KB_DIR=None,
        STATE_DIR=str(state_dir) if state_dir is not None else None,
        STRATA_TELEMETRY_DIR=(
            str(telemetry_dir) if telemetry_dir is not None else None
        ),
        STRATA_CONFIG_REPO=str(config_repo) if config_repo is not None else None,
    ):
        name = f"context_ledger_under_test_{next(_MODULE_IDS)}"
        spec = importlib.util.spec_from_file_location(name, SCRIPT)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"could not load {SCRIPT}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module


_TEST_RUNTIME = tempfile.TemporaryDirectory()
with patched_env(
    STRATA_HOME=str(Path(_TEST_RUNTIME.name) / "install"),
    KB_DIR=None,
    STATE_DIR=str(Path(_TEST_RUNTIME.name) / "state"),
    STRATA_TELEMETRY_DIR=None,
    STRATA_CONFIG_REPO=None,
):
    from telemetry import context_ledger as ledger

SID = "11111111-1111-4111-8111-111111111111"
TS = "2026-07-23T10:00:00Z"


def row(line_no: int, **value: object) -> ledger.TranscriptRow:
    return ledger.TranscriptRow(line_no, dict(value))


def assistant(
    line_no: int,
    *,
    request_id: str,
    prompt_tokens: int,
    output_tokens: int = 10,
    text: str = "answer",
) -> ledger.TranscriptRow:
    return row(
        line_no,
        type="assistant",
        sessionId=SID,
        timestamp=TS,
        version="2.1.218",
        requestId=request_id,
        uuid=f"assistant-{line_no}",
        message={
            "id": f"message-{request_id}",
            "model": "claude-test",
            "usage": {
                "input_tokens": 3,
                "cache_creation_input_tokens": prompt_tokens - 103,
                "cache_read_input_tokens": 100,
                "output_tokens": output_tokens,
            },
            "content": [{"type": "text", "text": text}],
        },
    )


def boundary(
    line_no: int, uuid: str, metadata: dict[str, object]
) -> ledger.TranscriptRow:
    return row(
        line_no,
        type="system",
        subtype="compact_boundary",
        sessionId=SID,
        timestamp=TS,
        uuid=uuid,
        compactMetadata=metadata,
        content="Conversation compacted",
    )


def transcript(rows: list[ledger.TranscriptRow]) -> ledger.Transcript:
    return ledger.Transcript(Path(f"/tmp/{SID}.jsonl"), tuple(rows), 0, 0)


CALIBRATION = {
    "state": "fitted",
    "method": "test_two_class",
    "samples_total": 3,
    "samples_fit": 3,
    "samples_validation": 3,
    "classes": {
        "prose": {
            "chars_per_token": 4.0,
            "reliable": True,
            "reliability_state": "reliable_positive_heldout_r2",
            "attribution_ratio": "class_fitted",
            "samples_fit": 3,
            "n": 3,
            "r2": 1.0,
            "median_absolute_percentage_error_pct": 0.0,
        },
        "structured": {
            "chars_per_token": 4.0,
            "reliable": True,
            "reliability_state": "reliable_positive_heldout_r2",
            "attribution_ratio": "class_fitted",
            "samples_fit": 3,
            "n": 3,
            "r2": 1.0,
            "median_absolute_percentage_error_pct": 0.0,
        },
    },
    "pooled": {
        "chars_per_token": 4.0,
        "reliable": True,
        "reliability_state": "reliable_positive_heldout_r2",
        "n": 3,
        "r2": 1.0,
        "median_absolute_percentage_error_pct": 0.0,
    },
    "combined_validation": {
        "n": 3,
        "r2": 1.0,
        "median_absolute_percentage_error_pct": 0.0,
    },
}


def _epoch(value: str) -> float:
    """Parsed epoch for a timestamp a test controls; asserts the parse succeeded."""
    parsed = ledger.parse_timestamp(value)
    assert parsed is not None
    return parsed.timestamp()


class UsageTests(unittest.TestCase):
    def test_usage_summation(self) -> None:
        usage = {
            "input_tokens": 3,
            "cache_creation_input_tokens": 25_359,
            "cache_read_input_tokens": 14_929,
            "output_tokens": 29,
        }
        self.assertEqual(ledger.prompt_usage(usage), 40_291)
        components = ledger.usage_components(usage)
        assert components is not None
        self.assertEqual(components["total_prompt_tokens"], 40_291)

    def test_invalid_usage_is_unavailable(self) -> None:
        self.assertIsNone(ledger.prompt_usage(None))
        self.assertIsNone(
            ledger.prompt_usage(
                {
                    "input_tokens": -1,
                    "cache_creation_input_tokens": 0,
                    "cache_read_input_tokens": 0,
                }
            )
        )


class BoundaryTests(unittest.TestCase):
    def test_boundary_detection_handles_old_and_new_schema_variants(self) -> None:
        rows = [
            assistant(1, request_id="pre-1", prompt_tokens=150_000),
            boundary(2, "old-boundary", {"trigger": "manual", "preTokens": 150_010}),
            row(
                3,
                type="user",
                sessionId=SID,
                timestamp=TS,
                uuid="summary-old",
                isCompactSummary=True,
                message={"content": "old compact summary"},
            ),
            assistant(4, request_id="post-1", prompt_tokens=40_000),
            assistant(5, request_id="pre-2", prompt_tokens=80_000),
            row(
                6,
                type="user",
                sessionId=SID,
                timestamp=TS,
                uuid="preserved-head",
                message={"content": "preserved user message"},
            ),
            boundary(
                7,
                "new-boundary",
                {
                    "trigger": "manual",
                    "preTokens": 80_010,
                    "durationMs": 100,
                    "postTokens": 5_000,
                    "preCompactDiscoveredTools": ["Read"],
                    "preservedSegment": {
                        "headUuid": "preserved-head",
                        "tailUuid": "preserved-head",
                    },
                    "preservedMessages": {
                        "uuids": ["preserved-head"],
                        "allUuids": ["preserved-head"],
                    },
                },
            ),
            row(
                8,
                type="user",
                sessionId=SID,
                timestamp=TS,
                uuid="summary-new",
                isCompactSummary=True,
                message={"content": "new compact summary"},
            ),
            assistant(9, request_id="post-2", prompt_tokens=50_000),
        ]
        boundary_rows, session_row = ledger.analyze_transcript(
            transcript(rows), CALIBRATION
        )
        self.assertEqual(len(boundary_rows), 2)
        self.assertEqual(session_row["boundaries_detected"], 2)
        self.assertEqual(session_row["boundaries_measured"], 2)
        self.assertEqual(sum(session_row["boundary_bucket_tokens"].values()), 90_000)
        self.assertIn("refill", session_row)
        self.assertEqual(
            boundary_rows[0]["attribution_state"], "partial_legacy_unattributed"
        )
        self.assertEqual(
            boundary_rows[1]["preserved_segment_basis"],
            "preservedMessages.allUuids",
        )
        self.assertEqual(len(ledger.calibration_samples(transcript(rows))), 1)
        for result, expected in zip(boundary_rows, (40_000, 50_000)):
            self.assertEqual(result["post_prompt_tokens"], expected)
            self.assertEqual(sum(result["buckets"].values()), expected)
            self.assertEqual(result["bucket_sum_tokens"], expected)

    def test_missing_post_usage_is_counted(self) -> None:
        rows = [boundary(1, "lonely-boundary", {"trigger": "manual", "preTokens": 10})]
        boundary_rows, session_row = ledger.analyze_transcript(
            transcript(rows), CALIBRATION
        )
        self.assertEqual(
            boundary_rows[0]["measurement_state"],
            "missing_authoritative_post_usage",
        )
        self.assertEqual(session_row["boundaries_missing_usage"], 1)

    def test_replayed_request_id_after_boundary_is_not_globally_deduplicated(
        self,
    ) -> None:
        rows = [
            assistant(1, request_id="replayed", prompt_tokens=150_000),
            row(
                2,
                type="user",
                sessionId=SID,
                timestamp=TS,
                message={"content": "resume"},
            ),
            boundary(
                3,
                "replayed-boundary",
                {"trigger": "manual", "preTokens": 150_010},
            ),
            row(
                4,
                type="user",
                sessionId=SID,
                timestamp=TS,
                isCompactSummary=True,
                message={"content": "summary"},
            ),
            assistant(5, request_id="replayed", prompt_tokens=40_000),
        ]
        calls = ledger.calls_in_rows(rows)
        self.assertEqual(len(calls), 2)
        boundary_rows, _ = ledger.analyze_transcript(transcript(rows), CALIBRATION)
        self.assertEqual(boundary_rows[0]["post_prompt_tokens"], 40_000)

    def test_interleaved_tool_results_do_not_split_one_api_response(self) -> None:
        shared_usage = {
            "input_tokens": 3,
            "cache_creation_input_tokens": 897,
            "cache_read_input_tokens": 100,
            "output_tokens": 10,
        }
        rows = [
            row(
                1,
                type="assistant",
                requestId="shared-request",
                message={
                    "id": "shared-message",
                    "model": "claude-test",
                    "usage": shared_usage,
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "read-id",
                            "name": "Read",
                            "input": {"file_path": "/tmp/a"},
                        }
                    ],
                },
            ),
            row(
                2,
                type="user",
                message={
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "read-id",
                            "content": "interleaved read payload",
                        }
                    ]
                },
            ),
            row(
                3,
                type="assistant",
                requestId="shared-request",
                message={
                    "id": "shared-message",
                    "model": "claude-test",
                    "usage": shared_usage,
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "bash-id",
                            "name": "Bash",
                            "input": {"command": "true"},
                        }
                    ],
                },
            ),
            row(
                4,
                type="user",
                message={
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": "bash-id",
                            "content": "interleaved bash payload",
                        }
                    ]
                },
            ),
            assistant(5, request_id="next-request", prompt_tokens=1_200),
        ]
        calls = ledger.calls_in_rows(rows)
        self.assertEqual(len(calls), 2)
        refill = ledger.boundary_refill(
            rows,
            calls,
            calls[0],
            len(rows),
            ledger.tool_name_map(rows),
            CALIBRATION,
        )
        self.assertEqual(refill["transitions"], 1)
        self.assertGreater(refill["bucket_tokens"]["tool_result:Read"], 0)

    def test_durable_skill_listing_survives_boundary_without_reemission(
        self,
    ) -> None:
        rows = [
            row(
                1,
                type="attachment",
                sessionId=SID,
                timestamp=TS,
                attachment={
                    "type": "skill_listing",
                    "content": "x" * 400,
                    "skillCount": 1,
                },
            ),
            assistant(2, request_id="pre", prompt_tokens=10_000),
            boundary(
                3,
                "durable-boundary",
                {"trigger": "manual", "preTokens": 10_010},
            ),
            row(
                4,
                type="user",
                sessionId=SID,
                timestamp=TS,
                isCompactSummary=True,
                message={"content": "summary"},
            ),
            assistant(5, request_id="post", prompt_tokens=1_000),
        ]
        boundary_rows, _ = ledger.analyze_transcript(transcript(rows), CALIBRATION)
        self.assertEqual(boundary_rows[0]["bucket_chars"]["skill_listing"], 400)
        self.assertEqual(boundary_rows[0]["buckets"]["skill_listing"], 100)


class CalibrationTests(unittest.TestCase):
    def test_exact_two_class_calibration_fit_and_quality(self) -> None:
        samples = [
            ledger.CalibrationSample(400, 0, 100, "a", "a"),
            ledger.CalibrationSample(0, 500, 100, "b", "b"),
            ledger.CalibrationSample(400, 500, 200, "c", "c"),
        ]
        fit = ledger.fit_calibration(samples)
        self.assertEqual(fit["state"], "fitted")
        self.assertAlmostEqual(
            fit["classes"]["prose"]["chars_per_token"], 4.0, places=9
        )
        self.assertAlmostEqual(
            fit["classes"]["structured"]["chars_per_token"], 5.0, places=9
        )
        self.assertAlmostEqual(fit["combined_validation"]["r2"], 1.0, places=9)
        self.assertAlmostEqual(
            fit["combined_validation"]["median_absolute_percentage_error_pct"],
            0.0,
            places=9,
        )

    def test_corpus_sized_fit_uses_a_stable_heldout_partition(self) -> None:
        samples = [
            ledger.CalibrationSample(
                prose_chars=400 * (number + 1),
                structured_chars=500 * ((number % 7) + 1),
                target_tokens=100 * (number + 1) + 100 * ((number % 7) + 1),
                sid=str(number),
                key=f"sample-{number}",
            )
            for number in range(30)
        ]
        fit = ledger.fit_calibration(samples)
        self.assertEqual(fit["split_policy"], "stable_sha256_80_20")
        self.assertGreater(fit["samples_validation"], 0)
        self.assertLess(fit["samples_validation"], fit["samples_total"])
        self.assertAlmostEqual(
            fit["classes"]["prose"]["chars_per_token"], 4.0, places=9
        )
        self.assertAlmostEqual(
            fit["classes"]["structured"]["chars_per_token"], 5.0, places=9
        )

    def test_overflow_is_exposed_as_negative_residual_without_downscaling(self) -> None:
        buckets, diagnostics = ledger.estimate_and_reconcile(
            {"user_messages": 800, "assistant_text": 800},
            authoritative_tokens=100,
            calibration=CALIBRATION,
        )
        self.assertEqual(sum(buckets.values()), 100)
        self.assertEqual(buckets["system_and_tools"], -300)
        self.assertGreater(diagnostics["estimation_overflow_tokens"], 0)
        self.assertTrue(diagnostics["calibration_failure"])
        self.assertFalse(diagnostics["downscaled"])
        self.assertEqual(diagnostics["reconciliation_scale"], 1.0)

    def test_unreliable_class_uses_pooled_ratio_for_attribution(self) -> None:
        calibration = {
            "classes": {
                "prose": {"chars_per_token": 4.0, "reliable": True},
                "structured": {"chars_per_token": 1.0, "reliable": False},
            },
            "pooled": {"chars_per_token": 10.0, "reliable": True},
        }
        buckets, diagnostics = ledger.estimate_and_reconcile(
            {"user_messages": 100},
            authoritative_tokens=100,
            calibration=calibration,
        )
        self.assertEqual(buckets["user_messages"], 10)
        self.assertEqual(
            diagnostics["bucket_estimation_methods"]["user_messages"],
            "pooled_combined:structured_unreliable",
        )


class WindowRegimeAndFloorTests(unittest.TestCase):
    def test_session_window_uses_observed_ceiling_and_never_drops_percentage(
        self,
    ) -> None:
        rows = [
            assistant(1, request_id="pre", prompt_tokens=250_000),
            boundary(2, "extended", {"trigger": "manual", "preTokens": 250_010}),
            row(
                3,
                type="user",
                sessionId=SID,
                timestamp=TS,
                isCompactSummary=True,
                message={"content": "summary"},
            ),
            assistant(4, request_id="post", prompt_tokens=80_000),
        ]
        boundaries, _ = ledger.analyze_transcript(transcript(rows), CALIBRATION)
        self.assertEqual(boundaries[0]["context_window_tokens"], 1_000_000)
        self.assertEqual(
            boundaries[0]["context_window_basis"],
            "session_observed_above_200k",
        )
        self.assertAlmostEqual(boundaries[0]["fill_pct"], 8.0)

        short = [
            boundary(1, "base", {"trigger": "auto", "preTokens": 150_000}),
            assistant(2, request_id="post-base", prompt_tokens=80_000),
        ]
        boundaries, _ = ledger.analyze_transcript(transcript(short), CALIBRATION)
        self.assertEqual(boundaries[0]["context_window_tokens"], 200_000)
        self.assertAlmostEqual(boundaries[0]["fill_pct"], 40.0)

        ambiguous = [
            boundary(1, "ambiguous", {"trigger": "manual", "preTokens": 150_000}),
            assistant(2, request_id="post-ambiguous", prompt_tokens=80_000),
        ]
        boundaries, _ = ledger.analyze_transcript(transcript(ambiguous), CALIBRATION)
        self.assertIsNone(boundaries[0]["context_window_tokens"])
        self.assertIsNone(boundaries[0]["fill_pct"])
        self.assertEqual(
            boundaries[0]["fill_pct_bounds_if_window_unknown"],
            {"if_1m": 8.0, "if_200k": 40.0},
        )

    def test_git_regime_join_and_actual_hook_set_are_independent(self) -> None:
        history = [
            {
                "id": "old1111",
                "commit": "old1111",
                "timestamp": "2026-07-23T09:00:00Z",
                "timestamp_epoch": _epoch("2026-07-23T09:00:00Z"),
                "subject": "old",
            },
            {
                "id": "new2222",
                "commit": "new2222",
                "timestamp": "2026-07-23T09:30:00Z",
                "timestamp_epoch": _epoch("2026-07-23T09:30:00Z"),
                "subject": "new",
                "is_current": True,
            },
        ]
        rows = [
            assistant(1, request_id="pre", prompt_tokens=150_000),
            boundary(2, "hooked", {"trigger": "manual", "preTokens": 150_010}),
            row(
                3,
                type="attachment",
                timestamp=TS,
                attachment={
                    "type": "hook_success",
                    "hookName": "SessionStart",
                    "command": "bash /tmp/memory-digest.sh",
                    "content": "digest",
                },
            ),
            assistant(4, request_id="post", prompt_tokens=40_000),
        ]
        boundaries, _ = ledger.analyze_transcript(
            transcript(rows), CALIBRATION, history
        )
        self.assertEqual(boundaries[0]["config_regime"]["id"], "new2222")
        self.assertEqual(boundaries[0]["hooks_fired"]["names"], ["memory-digest.sh"])

    def test_no_compaction_session_tracks_first_turn_floor_and_regime(self) -> None:
        rows = [
            row(
                1,
                type="user",
                sessionId=SID,
                timestamp=TS,
                message={"content": "hello"},
            ),
            assistant(2, request_id="only", prompt_tokens=55_000),
        ]
        _, session = ledger.analyze_transcript(transcript(rows), CALIBRATION)
        self.assertEqual(session["session_floor"]["state"], "measured")
        self.assertEqual(session["session_floor"]["tokens"], 55_000)
        self.assertEqual(session["session_floor"]["config_regime"]["id"], "unknown")


class ToleranceTests(unittest.TestCase):
    def test_malformed_lines_are_skipped_and_counted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.jsonl"
            path.write_text(
                '{"type":"user","sessionId":"ok","message":{"content":"hello"}}\n'
                "{bad json\n"
                "[]\n",
                encoding="utf-8",
            )
            parsed = ledger.read_transcript(path)
            self.assertEqual(len(parsed.rows), 1)
            self.assertEqual(parsed.malformed_lines, 1)
            self.assertEqual(parsed.non_object_lines, 1)

    def test_transcript_without_compactions_produces_one_session_row(self) -> None:
        parsed = transcript(
            [
                row(
                    1,
                    type="user",
                    sessionId=SID,
                    timestamp=TS,
                    message={"content": "hello"},
                ),
                assistant(2, request_id="only", prompt_tokens=1_000),
            ]
        )
        boundaries, session = ledger.analyze_transcript(parsed, CALIBRATION)
        self.assertEqual(boundaries, [])
        self.assertEqual(session["boundaries_detected"], 0)
        self.assertEqual(session["boundaries_measured"], 0)

    def test_unified_event_append_is_idempotent_and_envelope_is_fixed(self) -> None:
        event = {
            "ts": TS,
            "sid": SID,
            "kind": ledger.KIND,
            "source": ledger.SOURCE,
            "schema": ledger.SCHEMA,
            "row_type": "session",
            "ledger_id": "stable-id",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "events.jsonl"
            self.assertEqual(ledger.append_missing_events([event, event], path), 1)
            self.assertEqual(ledger.append_missing_events([event], path), 0)
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(
                {key: rows[0][key] for key in ("ts", "sid", "kind", "source")},
                {
                    "ts": TS,
                    "sid": SID,
                    "kind": ledger.KIND,
                    "source": ledger.SOURCE,
                },
            )


class RuntimePathTests(unittest.TestCase):
    def test_state_dir_redirects_all_runtime_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install = root / "install"
            state = root / "runtime-state"
            module = load_context_ledger(install, state_dir=state)
            setattr(module, "TRANSCRIPT_ROOT", root / "transcripts")

            rows, appended = module.backfill()

            telemetry = state / "telemetry"
            self.assertEqual(rows, [])
            self.assertEqual(appended, 0)
            self.assertEqual(module.STRATA_HOME, install)
            self.assertEqual(module.KB_DIR, install / "workspace")
            self.assertEqual(module.STATE_DIR, state)
            self.assertEqual(module.TEL_DIR, telemetry)
            self.assertEqual(module.LEDGER_PATH, telemetry / "context-ledger.jsonl")
            self.assertEqual(module.EVENTS_PATH, telemetry / "events.jsonl")
            self.assertEqual(module.LOCK_PATH, telemetry / ".rotate.lock")
            self.assertTrue(module.LEDGER_PATH.is_file())
            self.assertTrue(module.LOCK_PATH.is_file())
            self.assertFalse((install / "telemetry" / "context-ledger.jsonl").exists())

    def test_report_reads_redirected_ledger_without_install_writes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install = root / "install"
            state = root / "runtime-state"
            module = load_context_ledger(install, state_dir=state)
            module.LEDGER_PATH.parent.mkdir(parents=True)
            session = {
                "ts": TS,
                "sid": SID,
                "kind": module.KIND,
                "source": module.SOURCE,
                "schema": module.SCHEMA,
                "row_type": "session",
                "ledger_id": f"v{module.SCHEMA}:session:{SID}",
                "boundaries_detected": 0,
                "session_floor": {
                    "state": "measured",
                    "tokens": 1_000,
                    "timestamp": TS,
                    "config_regime": {
                        "id": "unknown",
                        "subject": "config history unavailable",
                        "is_current": False,
                    },
                },
            }
            module.LEDGER_PATH.write_text(
                json.dumps(session) + "\n",
                encoding="utf-8",
            )
            stdout = io.StringIO()
            stderr = io.StringIO()

            with (
                contextlib.redirect_stdout(stdout),
                contextlib.redirect_stderr(stderr),
            ):
                status = module.main(["--report"])

            self.assertEqual(status, 0, stderr.getvalue())
            self.assertTrue(
                stdout.getvalue().startswith("# Context Composition Ledger\n")
            )
            self.assertFalse((install / "telemetry").exists())

    def test_telemetry_dir_takes_precedence_over_state_dir(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            install = root / "install"
            state = root / "runtime-state"
            telemetry = root / "explicit-telemetry"
            module = load_context_ledger(
                install,
                state_dir=state,
                telemetry_dir=telemetry,
            )
            setattr(module, "TRANSCRIPT_ROOT", root / "transcripts")

            module.backfill()

            self.assertEqual(module.STATE_DIR, state)
            self.assertEqual(module.TEL_DIR, telemetry)
            self.assertTrue((telemetry / "context-ledger.jsonl").is_file())
            self.assertTrue((telemetry / ".rotate.lock").is_file())
            self.assertFalse((state / "telemetry").exists())


class RegimeHistoryTests(unittest.TestCase):
    @staticmethod
    def _write_compaction_config(repo: Path) -> Path:
        hook = repo / "hooks" / "pre-compaction.sh"
        hook.parent.mkdir(parents=True)
        hook.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
        settings = {
            "hooks": {
                "PreCompact": [
                    {
                        "hooks": [
                            {"command": "bash $STRATA_HOME/hooks/pre-compaction.sh"},
                        ]
                    }
                ]
            }
        }
        (repo / "settings.json").write_text(json.dumps(settings), encoding="utf-8")
        return hook

    @staticmethod
    def _git(repo: Path, *args: str, date: str | None = None) -> None:
        env = os.environ.copy()
        if date is not None:
            env["GIT_AUTHOR_DATE"] = date
            env["GIT_COMMITTER_DATE"] = date
        subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )

    def test_config_repo_override_drives_git_regime_history(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "config-repo"
            repo.mkdir()
            hook = self._write_compaction_config(repo)
            self._git(repo, "init")
            self._git(repo, "config", "user.name", "Context Ledger Test")
            self._git(repo, "config", "user.email", "test@example.invalid")
            self._git(repo, "add", ".")
            self._git(
                repo,
                "commit",
                "-m",
                "Add generic compaction hook",
                date="2026-01-01T00:00:00Z",
            )
            hook.write_text(
                "#!/usr/bin/env bash\nexit 0\n# revised\n", encoding="utf-8"
            )
            self._git(repo, "add", ".")
            self._git(
                repo,
                "commit",
                "-m",
                "Update generic compaction hook",
                date="2026-01-02T00:00:00Z",
            )
            module = load_context_ledger(
                root / "install",
                state_dir=root / "state",
                config_repo=repo,
            )

            history = module.load_regime_history()

            self.assertEqual(module.CONFIG_REPO, repo)
            self.assertEqual(len(history), 2)
            self.assertEqual(
                [item["subject"] for item in history],
                ["Add generic compaction hook", "Update generic compaction hook"],
            )
            self.assertTrue(history[-1]["is_current"])

    def test_non_git_config_repo_degrades_to_unknown_regime(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "config-repo"
            repo.mkdir()
            self._write_compaction_config(repo)
            module = load_context_ledger(
                root / "install",
                state_dir=root / "state",
                config_repo=repo,
            )

            history = module.load_regime_history()
            regime = module.regime_for_timestamp(TS, history)

            self.assertEqual(history, [])
            self.assertEqual(regime["id"], "unknown")
            self.assertEqual(regime["subject"], "config history unavailable")


if __name__ == "__main__":
    unittest.main(verbosity=2)
