import contextlib
import gzip
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "telemetry" / "cost_rollup.py"


@contextlib.contextmanager
def patched_env(**updates):
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


def load_cost_rollup(home, telemetry_dir):
    with patched_env(
        STRATA_HOME=str(home),
        STRATA_TELEMETRY_DIR=str(telemetry_dir),
        KB_DIR=None,
        STATE_DIR=None,
    ):
        spec = importlib.util.spec_from_file_location("cost_rollup_under_test", SCRIPT)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"could not load {SCRIPT}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def write_gzip_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt") as fh:
        for row in rows:
            fh.write(json.dumps(row) + "\n")


def write_rates(home, rates):
    rate_path = home / "telemetry" / "model_rates.json"
    rate_path.parent.mkdir(parents=True, exist_ok=True)
    rate_path.write_text(json.dumps(rates), encoding="utf-8")


def call_main(module, argv):
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        status = module.main(argv)
    return status, stdout.getvalue(), stderr.getvalue()


class CostRollupTests(unittest.TestCase):
    def test_delegation_only_session_is_reported_and_aggregated(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            telemetry = Path(tmp) / "telemetry"
            write_rates(
                home,
                {
                    "paid": {
                        "in": 1.0,
                        "out": 2.0,
                        "cache_read": 0.0,
                        "cache_write": 0.0,
                        "billing": "marginal",
                    }
                },
            )
            write_jsonl(
                telemetry / "events.jsonl",
                [
                    {
                        "kind": "delegation",
                        "sid": "deleg-only",
                        "model": "paid",
                        "tokens": {"output": 1_000_000},
                    }
                ],
            )
            module = load_cost_rollup(home, telemetry)

            status, out, err = call_main(module, ["deleg-only"])
            self.assertEqual(status, 0, err)
            ledger = json.loads(out)
            self.assertEqual(ledger["channels"]["main_loop"]["cost_notional"], 0.0)
            self.assertEqual(ledger["channels"]["delegations"]["cost_notional"], 2.0)
            self.assertEqual(ledger["total_cost_real"], 2.0)

            status, out, err = call_main(module, ["--aggregate"])
            self.assertEqual(status, 0, err)
            aggregate = json.loads(out)
            self.assertEqual(aggregate["sessions"], 1)
            self.assertEqual(aggregate["notional_usd"]["delegations"], 2.0)

    def test_archived_metrics_and_events_are_included(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            telemetry = Path(tmp) / "telemetry"
            write_rates(
                home,
                {
                    "paid": {
                        "in": 1.0,
                        "out": 3.0,
                        "cache_read": 0.0,
                        "cache_write": 0.0,
                        "billing": "marginal",
                    }
                },
            )
            write_gzip_jsonl(
                telemetry / "archive" / "session-metrics-20260101T000000Z.jsonl.gz",
                [
                    {
                        "sid": "archived",
                        "tok_by_model": {
                            "paid": {"input": 1_000_000, "output": 1_000_000}
                        },
                    }
                ],
            )
            write_gzip_jsonl(
                telemetry / "archive" / "events-20260101T000000Z.jsonl.gz",
                [
                    {
                        "kind": "delegation",
                        "sid": "archived",
                        "model": "paid",
                        "tokens": {"output": 1_000_000},
                    }
                ],
            )
            module = load_cost_rollup(home, telemetry)

            status, out, err = call_main(module, ["archived"])
            self.assertEqual(status, 0, err)
            ledger = json.loads(out)
            self.assertEqual(ledger["channels"]["main_loop"]["cost_notional"], 4.0)
            self.assertEqual(ledger["channels"]["delegations"]["cost_notional"], 3.0)

            status, out, err = call_main(module, ["--aggregate"])
            self.assertEqual(status, 0, err)
            aggregate = json.loads(out)
            self.assertEqual(aggregate["sessions"], 1)
            self.assertEqual(aggregate["notional_usd"]["total"], 7.0)

    def test_delegation_full_token_split_charges_cache_creation(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            telemetry = Path(tmp) / "telemetry"
            write_rates(
                home,
                {
                    "paid": {
                        "in": 0.0,
                        "out": 0.0,
                        "cache_read": 0.0,
                        "cache_write": 100.0,
                        "billing": "marginal",
                    }
                },
            )
            write_jsonl(telemetry / "session-metrics.jsonl", [{"sid": "cache"}])
            write_jsonl(
                telemetry / "events.jsonl",
                [
                    {
                        "kind": "delegation",
                        "sid": "cache",
                        "model": "paid",
                        "tokens": {"cache_creation": 1_000_000},
                    }
                ],
            )
            module = load_cost_rollup(home, telemetry)

            status, out, err = call_main(module, ["cache"])
            self.assertEqual(status, 0, err)
            ledger = json.loads(out)
            self.assertEqual(ledger["channels"]["delegations"]["cost_notional"], 100.0)
            self.assertEqual(ledger["total_cost_real"], 100.0)

    def test_aggregate_sums_raw_costs_before_rounding(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            telemetry = Path(tmp) / "telemetry"
            write_rates(
                home,
                {
                    "tiny": {
                        "in": 40.0,
                        "out": 0.0,
                        "cache_read": 0.0,
                        "cache_write": 0.0,
                        "billing": "marginal",
                    }
                },
            )
            write_jsonl(
                telemetry / "session-metrics.jsonl",
                [
                    {"sid": f"s{i}", "tok_by_model": {"tiny": {"input": 1}}}
                    for i in range(250)
                ],
            )
            module = load_cost_rollup(home, telemetry)

            status, out, err = call_main(module, ["--aggregate"])
            self.assertEqual(status, 0, err)
            aggregate = json.loads(out)
            self.assertEqual(aggregate["sessions"], 250)
            self.assertEqual(aggregate["notional_usd"]["main_loop"], 0.01)
            self.assertEqual(aggregate["notional_usd"]["total"], 0.01)

    def test_corrupt_rate_table_raises_with_path_but_missing_table_uses_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            telemetry = Path(tmp) / "telemetry"
            rate_path = home / "telemetry" / "model_rates.json"
            rate_path.parent.mkdir(parents=True, exist_ok=True)
            rate_path.write_text("{", encoding="utf-8")
            write_jsonl(
                telemetry / "session-metrics.jsonl",
                [{"sid": "bad", "tok_by_model": {"paid": {"input": 1_000_000}}}],
            )
            module = load_cost_rollup(home, telemetry)

            with self.assertRaises(ValueError) as exc:
                module.main(["bad"])
            self.assertIn("model_rates.json", str(exc.exception))

            rate_path.unlink()
            status, out, err = call_main(module, ["bad"])
            self.assertEqual(status, 0, err)
            ledger = json.loads(out)
            self.assertEqual(ledger["total_cost_notional"], 0.0)

    def test_rate_lookup_uses_only_exact_or_dated_model_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            telemetry = Path(tmp) / "telemetry"
            write_rates(
                home,
                {
                    "_note": "metadata is ignored",
                    "gpt-4o": {
                        "in": 10.0,
                        "out": 10.0,
                        "cache_read": 0.0,
                        "cache_write": 0.0,
                        "billing": "marginal",
                    },
                },
            )
            write_jsonl(
                telemetry / "session-metrics.jsonl",
                [
                    {
                        "sid": "short",
                        "tok_by_model": {
                            "gpt-4": {"input": 1_000_000, "output": 1_000_000}
                        },
                    },
                    {
                        "sid": "dated",
                        "tok_by_model": {
                            "gpt-4o-2026-06-30": {
                                "input": 1_000_000,
                                "output": 1_000_000,
                            }
                        },
                    },
                ],
            )
            module = load_cost_rollup(home, telemetry)

            status, out, err = call_main(module, ["short"])
            self.assertEqual(status, 0, err)
            short = json.loads(out)
            self.assertEqual(short["total_cost_notional"], 0.0)

            status, out, err = call_main(module, ["dated"])
            self.assertEqual(status, 0, err)
            dated = json.loads(out)
            self.assertEqual(dated["total_cost_notional"], 20.0)


if __name__ == "__main__":
    unittest.main()
