"""Small, fail-open JSONL emitter shared by memory entry points."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

QUERY_CHAR_CAP = 4096


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def session_id() -> str:
    return os.environ.get("STRATA_SESSION_ID") or f"memory-{os.getpid()}"


def bounded_query(payload: dict[str, Any]) -> dict[str, Any]:
    query = payload.get("query")
    if not isinstance(query, str) or len(query) <= QUERY_CHAR_CAP:
        return payload
    bounded = dict(payload)
    bounded["query"] = query[:QUERY_CHAR_CAP]
    bounded["query_chars"] = len(query)
    bounded["query_truncated"] = True
    bounded["query_sha256"] = hashlib.sha256(
        query.encode("utf-8", "replace")
    ).hexdigest()
    return bounded


def append_event(path: Path, kind: str, payload: dict[str, Any]) -> bool:
    """Append one compact event, returning false when the sink is unavailable."""

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        row = {
            **bounded_query(payload),
            "ts": utc_now(),
            "sid": session_id(),
            "kind": kind,
        }
        encoded = json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(encoded)
        return True
    except (OSError, TypeError, ValueError, UnicodeError):
        return False


__all__ = ["QUERY_CHAR_CAP", "append_event", "bounded_query", "session_id", "utc_now"]
