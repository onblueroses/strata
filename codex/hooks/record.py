"""One telemetry row per Codex hook run, appended to the shared sink.

Codex keeps no record of its hook runs: the rollout does not show them and the log database
holds none. A Claude hook that fails is visible in the transcript; a Codex hook that fails,
or that Codex stopped running after a trust change, was visible nowhere. These rows make it
visible to whatever reads the sink.

Fail-open by construction: every error is swallowed, nothing is printed.
"""
import json
import os
import time
from pathlib import Path

SINK = Path(os.environ.get("CODEX_HOOK_SINK") or Path.home() / ".claude/telemetry/events.jsonl")


def record(hook: str, status: str, started: float, sid: str = "unknown", **fields) -> None:
    """status: ok | degraded (ran, part of its payload missing) | error | deny."""
    try:
        row = {**fields, "hook": hook, "status": status,
               "ms": int((time.monotonic() - started) * 1000),
               "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "sid": str(sid)[:36], "kind": "codex_hook", "source": "live"}
        if os.environ.get("TELEMETRY_SYNTHETIC", "") not in ("", "0"):
            row["synthetic"] = True
        with SINK.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")
    except Exception:  # noqa: BLE001 - a sink that cannot be written must not cost a hook
        pass
