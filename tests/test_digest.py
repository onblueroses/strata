import contextlib
import importlib.util
import io
import json
import os
import tempfile
import unittest
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
DIGEST_PATH = REPO_ROOT / "telemetry" / "digest.py"


@contextlib.contextmanager
def patched_env(**updates: str | None) -> Iterator[None]:
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


def write_router_universe(home: Path) -> None:
    router_dir = home / "reference" / ".router-eval"
    router_dir.mkdir(parents=True)
    (router_dir / "doc-catalog.json").write_text(
        json.dumps(
            [
                {"doc": "alpha.md", "keywords": "alpha"},
                {"doc": "never.md", "keywords": "never"},
            ]
        ),
        encoding="utf-8",
    )
    (router_dir / ".lex-cache.json").write_text(
        json.dumps({"vecs": {"alpha.md": {}, "never.md": {}}}),
        encoding="utf-8",
    )


def load_digest(home: Path) -> ModuleType:
    write_router_universe(home)
    state_dir = home / "workspace" / "state"
    telemetry_dir = state_dir / "telemetry"
    with patched_env(
        STRATA_HOME=str(home),
        KB_DIR=str(home / "workspace"),
        STATE_DIR=str(state_dir),
        STRATA_TELEMETRY_DIR=str(telemetry_dir),
    ):
        spec = importlib.util.spec_from_file_location("digest_under_test", DIGEST_PATH)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"could not load {DIGEST_PATH}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def call_main(module: ModuleType, argv: list[str]) -> tuple[int, str, str]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    main = getattr(module, "main")
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        status = main(argv)
    return int(status), stdout.getvalue(), stderr.getvalue()


def synthetic_events() -> list[dict[str, object]]:
    events: list[dict[str, object]] = [
        {
            "ts": "2026-01-01T00:00:00Z",
            "sid": "abc12345",
            "kind": "doc_inject",
            "source": "injection-log",
            "doc": "alpha.md",
            "score": 0.2,
            "signal": "lexical",
        },
        {
            "ts": "2026-01-01T00:00:30Z",
            "sid": "abc12345-full",
            "kind": "doc_used",
            "source": "session-events",
            "item": "alpha.md",
        },
        {
            "ts": "2026-01-01T00:01:00Z",
            "sid": "abc12345",
            "kind": "doc_inject",
            "source": "injection-log",
            "doc": "alpha.md",
            "score": 0.5,
            "signal": "lexical",
        },
        {
            "ts": "2026-01-01T00:02:00Z",
            "sid": "abc12345",
            "kind": "doc_inject",
            "source": "injection-log",
            "doc": "alpha.md",
            "score": 0.9,
            "signal": "lexical",
        },
        {
            "ts": "2026-01-01T00:03:00Z",
            "sid": "abc12345",
            "kind": "doc_zero_route",
            "source": "injection-log",
            "signal": "none",
        },
        {
            "ts": "2026-01-01T00:04:00Z",
            "sid": "abc12345",
            "kind": "edit",
            "source": "session-events",
            "file": "src/main.py",
        },
        {
            "ts": "2026-01-01T00:05:00Z",
            "sid": "abc12345-full",
            "kind": "hook_block",
            "source": "live",
            "hook": "pre-push",
            "reason": "review",
        },
    ]
    events.extend(
        {
            "ts": f"2026-01-01T00:0{minute}:00Z",
            "sid": "abc12345-full",
            "kind": "tool_fail",
            "source": "live",
            "tool": "shell",
            "reason": "exit",
        }
        for minute in (6, 7, 8)
    )
    events.extend(
        {
            "ts": f"2026-01-01T00:10:{second:02d}Z",
            "sid": "abc12345-full",
            "kind": "delegation",
            "source": "live",
            "lane": "strong",
            "exit": 0,
            "dur_s": 10,
        }
        for second in (10, 20, 30)
    )
    return events


class DigestTests(unittest.TestCase):
    def test_public_sections_render_and_private_sections_are_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            module = load_digest(Path(tmp) / "strata")
            events = synthetic_events()
            with mock.patch.object(module, "load_events", return_value=(events, [])):
                status, output, error = call_main(module, [])
                report = getattr(module, "build_report")(None)

            self.assertEqual(status, 0, error)
            for header in (
                "## 2. Router Precision",
                "### Worst-served docs",
                "### Best-served docs",
                "## 3. Never-Surfaced Router Docs",
                "## 4. Router Score Calibration",
                "## 5. Zero-Route Analysis",
                "## 6. Delegation Summary",
                "## 7. Friction and Rework",
                "## 8. Serial-Wait Diagnostic",
            ):
                self.assertIn(header, output)
            for dropped in (
                "Memory System",
                "Memory Calibration",
                "True Cost",
                "Quota Headroom",
                "Skills/Lenses",
                "lenses",
            ):
                self.assertNotIn(dropped, output)
            self.assertEqual(
                set(report),
                {
                    "generated_at",
                    "unify",
                    "window",
                    "header",
                    "doc_precision",
                    "never_surfaced",
                    "score_calibration",
                    "zero_routes",
                    "delegation",
                    "friction",
                    "serial_wait",
                    "top_signals",
                },
            )
            self.assertEqual(report["doc_precision"]["used_injections"], 1)
            self.assertIn("instrumentation smoke signal", output)
            self.assertEqual(report["never_surfaced"]["never_docs"], ["never.md"])
            self.assertEqual(report["delegation"]["lanes"][0]["lane"], "strong")
            self.assertEqual(report["delegation"]["lanes"][0]["success"], 3)
            self.assertEqual(report["serial_wait"]["overall_parallelism"], 1.0)
            self.assertEqual(
                report["serial_wait"]["serial_sessions"][0]["longest_serial_run"],
                3,
            )
            self.assertEqual(report["friction"]["retry_storms"][0]["count"], 3)

    def test_tracked_output_is_refused_and_emitted_to_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            module = load_digest(Path(tmp) / "strata")
            tracked = REPO_ROOT / "telemetry" / "README.md"
            before = tracked.read_text(encoding="utf-8")
            with (
                mock.patch.object(module, "load_events", return_value=([], [])),
                mock.patch.dict(
                    os.environ,
                    {"GIT_CEILING_DIRECTORIES": str(REPO_ROOT)},
                    clear=False,
                ),
            ):
                status, output, error = call_main(module, ["--out", str(tracked)])

            self.assertEqual(status, 0, error)
            self.assertIn("refusing --out", error)
            self.assertIn("# Public Telemetry Digest", output)
            self.assertEqual(before, tracked.read_text(encoding="utf-8"))

    def test_empty_stream_renders_all_public_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "strata"
            module = load_digest(home)
            state_dir = home / "workspace" / "state"
            with patched_env(
                STRATA_HOME=str(home),
                KB_DIR=str(home / "workspace"),
                STATE_DIR=str(state_dir),
                STRATA_TELEMETRY_DIR=str(state_dir / "telemetry"),
            ):
                status, output, error = call_main(module, [])

            self.assertEqual(status, 0, error)
            self.assertIn("No events found.", output)
            self.assertIn("## 2. Router Precision", output)
            self.assertIn("## 8. Serial-Wait Diagnostic", output)
            self.assertNotIn("Traceback", error)


if __name__ == "__main__":
    unittest.main()
