#!/usr/bin/env python3
"""Offline Claude Code context-composition ledger.

Reads transcript JSONL without modifying it and emits deterministic rows for every
session and compaction boundary. Authoritative prompt size always comes from the
first real assistant usage after a compact boundary. Named bucket sizes are
calibrated character-based estimates; ``system_and_tools`` is the visible residual,
not a direct measurement.

Modes:
  context_ledger.py --backfill
  context_ledger.py --session <uuid|path>
  context_ledger.py --report
"""

from __future__ import annotations

import argparse
import collections
import fcntl
import hashlib
import json
import math
import os
import re
import shlex
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any, Mapping, Sequence


# Runtime path contract — matches telemetry-emit.sh, unify.py, and cost_rollup.py.
# The script ships at $STRATA_HOME/telemetry/context_ledger.py.
_SCRIPT_DIR = Path(__file__).resolve().parent
STRATA_HOME = Path(os.environ.get("STRATA_HOME") or _SCRIPT_DIR.parent)
KB_DIR = Path(os.environ.get("KB_DIR") or STRATA_HOME / "workspace")
STATE_DIR = Path(os.environ.get("STATE_DIR") or KB_DIR / "state")
TEL_DIR = Path(os.environ.get("STRATA_TELEMETRY_DIR") or STATE_DIR / "telemetry")

# Claude Code owns transcript storage. Ledger output and its shared telemetry lock
# stay under the runtime telemetry sink, never beside the tracked script.
TRANSCRIPT_ROOT = Path.home() / ".claude" / "projects"
LEDGER_PATH = TEL_DIR / "context-ledger.jsonl"
EVENTS_PATH = TEL_DIR / "events.jsonl"
LOCK_PATH = TEL_DIR / ".rotate.lock"

KIND = "context_composition"
SOURCE = "context_ledger"
SCHEMA = 3
BASE_CONTEXT_WINDOW = 200_000
EXTENDED_CONTEXT_WINDOW = 1_000_000
# A strata install keeps the versioned Claude Code configuration in STRATA_HOME.
# An alternate config checkout can be supplied without moving runtime state.
CONFIG_REPO = Path(os.environ.get("STRATA_CONFIG_REPO") or STRATA_HOME)
SETTINGS_PATH = CONFIG_REPO / "settings.json"
CLAUDE_MD_PATH = CONFIG_REPO / "CLAUDE.md"
USAGE_FIELDS = (
    "input_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)
PROMPT_RECORD_TYPES = {"user", "assistant", "attachment", "system"}
DURABLE_ATTACHMENT_TYPES = {
    "skill_listing",
    "deferred_tools_delta",
    "agent_listing_delta",
    "nested_memory",
}
SYSTEM_REMINDER_RE = re.compile(
    r"<system-reminder>.*?</system-reminder>", re.IGNORECASE | re.DOTALL
)


@dataclass(frozen=True)
class TranscriptRow:
    line_no: int
    value: dict[str, Any]


@dataclass(frozen=True)
class Transcript:
    path: Path
    rows: tuple[TranscriptRow, ...]
    malformed_lines: int
    non_object_lines: int


@dataclass(frozen=True)
class Call:
    """One model request, represented by its first assistant transcript row."""

    index: int
    key: str
    input_tokens: int
    usage: dict[str, int]
    model: str | None
    version: str | None
    request_id: str | None


@dataclass(frozen=True)
class CalibrationSample:
    prose_chars: int
    structured_chars: int
    target_tokens: int
    sid: str
    key: str
    raw_json_chars: int = 0


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def integer(value: Any) -> int | None:
    number = finite_number(value)
    if number is None:
        return None
    return int(number)


def prompt_usage(usage: Mapping[str, Any] | None) -> int | None:
    """Return authoritative input + cache creation + cache read prompt tokens."""
    if not isinstance(usage, Mapping):
        return None
    values: list[int] = []
    for field in USAGE_FIELDS:
        value = integer(usage.get(field, 0))
        if value is None or value < 0:
            return None
        values.append(value)
    return sum(values)


def usage_components(usage: Mapping[str, Any] | None) -> dict[str, int] | None:
    total = prompt_usage(usage)
    if total is None or not isinstance(usage, Mapping):
        return None
    return {
        "input_tokens": integer(usage.get("input_tokens", 0)) or 0,
        "cache_creation_input_tokens": integer(
            usage.get("cache_creation_input_tokens", 0)
        )
        or 0,
        "cache_read_input_tokens": integer(usage.get("cache_read_input_tokens", 0))
        or 0,
        "total_prompt_tokens": total,
        "output_tokens": max(0, integer(usage.get("output_tokens", 0)) or 0),
    }


def percentile(values: Sequence[float | int], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(float(value) for value in values)
    if q <= 0:
        return ordered[0]
    if q >= 1:
        return ordered[-1]
    position = (len(ordered) - 1) * q
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def distribution(values: Sequence[float | int]) -> dict[str, float | int | None]:
    if not values:
        return {
            "n": 0,
            "min": None,
            "p10": None,
            "p25": None,
            "median": None,
            "p75": None,
            "p90": None,
            "max": None,
        }
    return {
        "n": len(values),
        "min": min(values),
        "p10": percentile(values, 0.10),
        "p25": percentile(values, 0.25),
        "median": median(values),
        "p75": percentile(values, 0.75),
        "p90": percentile(values, 0.90),
        "max": max(values),
    }


def compact_json(value: Any) -> str:
    try:
        return json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
    except (TypeError, ValueError):
        return str(value)


def textual_chars(value: Any) -> int:
    """Count payload characters without counting transcript bookkeeping twice."""
    if isinstance(value, str):
        return len(value)
    if isinstance(value, list):
        return sum(textual_chars(item) for item in value)
    if isinstance(value, dict):
        # Content blocks are serialized structured prompt data. Counting their compact
        # JSON is more faithful than counting Python repr and retains tool arguments.
        return len(compact_json(value))
    return 0


def content_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(content_text(item) for item in value)
    if isinstance(value, dict):
        for key in ("content", "text", "file"):
            if key in value:
                nested = content_text(value[key])
                if nested:
                    return nested
        return compact_json(value)
    return ""


def split_system_reminders(text: str) -> tuple[int, int]:
    reminder_chars = sum(
        len(match.group(0)) for match in SYSTEM_REMINDER_RE.finditer(text)
    )
    return max(0, len(text) - reminder_chars), reminder_chars


def add_text(
    buckets: collections.Counter[str], text: str, ordinary_bucket: str
) -> None:
    ordinary, reminders = split_system_reminders(text)
    if ordinary:
        buckets[ordinary_bucket] += ordinary
    if reminders:
        buckets["system_reminder"] += reminders


def hook_script_name(attachment: Mapping[str, Any]) -> str:
    command = str(attachment.get("command") or "")
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()
    scripts = [
        os.path.basename(part)
        for part in parts
        if part.endswith((".sh", ".py", ".js", ".ts"))
    ]
    if scripts:
        return scripts[-1]
    return str(attachment.get("hookName") or "unknown")


def additional_context_hook_name(attachment: Mapping[str, Any]) -> str:
    """Recover actionable producer names where old records only stored the event."""
    text = content_text(attachment.get("content"))
    upper = text[:300].upper()
    if upper.startswith("## ENTITIES") or "ENTITY TABLE" in upper:
        return "memory-entities.sh"
    if "MEMORY DIGEST" in upper:
        return "memory-digest.sh"
    if upper.startswith("MEMORY ROUTER"):
        return "context-doc-router.sh"
    return str(attachment.get("hookName") or "unknown")


def tool_name_map(rows: Sequence[TranscriptRow]) -> dict[str, str]:
    names: dict[str, str] = {}
    for row in rows:
        value = row.value
        if value.get("type") != "assistant":
            continue
        message = value.get("message")
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") not in ("tool_use", "server_tool_use"):
                continue
            tool_id = block.get("id")
            name = block.get("name")
            if isinstance(tool_id, str) and name:
                names[tool_id] = str(name)
    return names


def attachment_buckets(
    attachment: Mapping[str, Any],
) -> collections.Counter[str]:
    buckets: collections.Counter[str] = collections.Counter()
    attachment_type = str(attachment.get("type") or "unknown")

    if attachment_type == "skill_listing":
        buckets["skill_listing"] += textual_chars(attachment.get("content"))
    elif attachment_type == "deferred_tools_delta":
        buckets["deferred_tools"] += textual_chars(attachment.get("addedLines"))
    elif attachment_type == "agent_listing_delta":
        buckets["agent_listing"] += textual_chars(attachment.get("addedLines"))
    elif attachment_type == "hook_success":
        content = attachment.get("content")
        if not content:
            stdout = attachment.get("stdout")
            content = stdout.rstrip("\n") if isinstance(stdout, str) else stdout
        buckets[f"hook:{hook_script_name(attachment)}"] += textual_chars(content)
    elif attachment_type == "hook_additional_context":
        name = additional_context_hook_name(attachment)
        buckets[f"hook:{name}"] += textual_chars(attachment.get("content"))
    elif attachment_type == "nested_memory":
        buckets["claude_md"] += textual_chars(attachment.get("content"))
    elif attachment_type == "file":
        path = str(
            attachment.get("displayPath") or attachment.get("filename") or "unknown"
        )
        bucket = "claude_md" if path.lower().endswith("claude.md") else f"file:{path}"
        buckets[bucket] += textual_chars(attachment.get("content"))
    elif attachment_type == "compact_file_reference":
        buckets["preserved_segment"] += len(
            str(attachment.get("displayPath") or attachment.get("filename") or "")
        )
    elif attachment_type == "invoked_skills":
        skills = attachment.get("skills")
        if isinstance(skills, list):
            for skill in skills:
                if not isinstance(skill, dict):
                    buckets["skill:unknown"] += textual_chars(skill)
                    continue
                name = str(
                    skill.get("name")
                    or skill.get("skill")
                    or skill.get("command")
                    or "unknown"
                )
                buckets[f"skill:{name}"] += textual_chars(skill)
    else:
        # Keep every ambient source named. Fields such as duration and UUID are
        # bookkeeping, so only content-bearing fields enter the estimate.
        for key in ("content", "addedLines", "skills", "text"):
            if key in attachment:
                buckets[f"attachment:{attachment_type}"] += textual_chars(
                    attachment.get(key)
                )
                break
    return buckets


def block_chars(value: Any) -> int:
    if isinstance(value, str):
        return len(value)
    if isinstance(value, list):
        return sum(block_chars(item) for item in value)
    if not isinstance(value, dict):
        return 0
    block_type = value.get("type")
    if block_type in ("text", "thinking"):
        key = "thinking" if block_type == "thinking" else "text"
        return textual_chars(value.get(key))
    if block_type == "tool_result":
        return block_chars(value.get("content"))
    if "content" in value:
        return block_chars(value.get("content"))
    return textual_chars(value)


def record_buckets(
    value: Mapping[str, Any], tools: Mapping[str, str]
) -> collections.Counter[str]:
    buckets: collections.Counter[str] = collections.Counter()
    record_type = value.get("type")

    if record_type == "attachment":
        attachment = value.get("attachment")
        if isinstance(attachment, Mapping):
            buckets.update(attachment_buckets(attachment))
        return buckets

    if record_type not in ("user", "assistant", "system"):
        return buckets

    if record_type == "system":
        if value.get("subtype") != "compact_boundary":
            text = value.get("content")
            if isinstance(text, str):
                add_text(buckets, text, "system_reminder")
        return buckets

    message = value.get("message")
    if not isinstance(message, Mapping):
        return buckets
    content = message.get("content")
    compact_summary = bool(value.get("isCompactSummary"))

    if isinstance(content, str):
        if compact_summary:
            buckets["compaction_summary"] += len(content)
        else:
            add_text(
                buckets,
                content,
                "user_messages" if record_type == "user" else "assistant_text",
            )
        return buckets

    if not isinstance(content, list):
        return buckets

    for block in content:
        if isinstance(block, str):
            bucket = (
                "compaction_summary"
                if compact_summary
                else ("user_messages" if record_type == "user" else "assistant_text")
            )
            add_text(buckets, block, bucket)
            continue
        if not isinstance(block, Mapping):
            continue
        block_type = str(block.get("type") or "")
        if compact_summary:
            buckets["compaction_summary"] += block_chars(block)
        elif block_type == "thinking":
            buckets["assistant_thinking"] += textual_chars(block.get("thinking"))
        elif block_type == "text":
            add_text(
                buckets,
                str(block.get("text") or ""),
                "user_messages" if record_type == "user" else "assistant_text",
            )
        elif block_type in ("tool_use", "server_tool_use"):
            name = str(block.get("name") or "unknown")
            buckets[f"tool_call:{name}"] += textual_chars(block.get("input"))
        elif block_type in (
            "tool_result",
            "server_tool_result",
            "web_search_tool_result",
        ):
            tool_id = str(block.get("tool_use_id") or "")
            name = tools.get(tool_id, "unknown")
            buckets[f"tool_result:{name}"] += block_chars(block.get("content"))
        else:
            ordinary = "user_messages" if record_type == "user" else "assistant_text"
            buckets[ordinary] += block_chars(block)
    return buckets


def rows_buckets(
    rows: Sequence[TranscriptRow],
    start: int,
    stop: int,
    tools: Mapping[str, str],
) -> collections.Counter[str]:
    buckets: collections.Counter[str] = collections.Counter()
    for row in rows[start:stop]:
        if row.value.get("type") in PROMPT_RECORD_TYPES:
            buckets.update(record_buckets(row.value, tools))
    return buckets


def boundary_post_rows_buckets(
    rows: Sequence[TranscriptRow],
    start: int,
    stop: int,
    tools: Mapping[str, str],
) -> collections.Counter[str]:
    """Count post-boundary payloads except durable state, which is rebuilt below."""
    buckets: collections.Counter[str] = collections.Counter()
    for row in rows[start:stop]:
        value = row.value
        if value.get("type") == "attachment":
            attachment = value.get("attachment")
            if (
                isinstance(attachment, Mapping)
                and attachment.get("type") in DURABLE_ATTACHMENT_TYPES
            ):
                continue
        if value.get("type") in PROMPT_RECORD_TYPES:
            buckets.update(record_buckets(value, tools))
    return buckets


def _delta_state(
    state: dict[str, str],
    attachment: Mapping[str, Any],
    added_names_key: str,
    removed_names_key: str,
) -> None:
    names = attachment.get(added_names_key)
    lines = attachment.get("addedLines")
    if isinstance(names, list) and isinstance(lines, list):
        for offset, line in enumerate(lines):
            name = str(names[offset]) if offset < len(names) else f"line-{offset}"
            state[name] = str(line)
    elif isinstance(lines, list):
        for offset, line in enumerate(lines):
            state[f"line-{offset}:{line}"] = str(line)
    removed = attachment.get(removed_names_key)
    if isinstance(removed, list):
        for name in removed:
            state.pop(str(name), None)


def durable_ambient_buckets(
    rows: Sequence[TranscriptRow], stop: int
) -> collections.Counter[str]:
    """Reconstruct stable prompt attachments current at ``stop``.

    Claude Code records a skill listing and nested memory payload when they enter
    the prompt, not on every later request. Compaction does not remove the stable
    prompt. Delta listings are replayed into state so each active line is counted
    once rather than once per historical attachment record.
    """
    skill_listing: Any = None
    deferred_tools: dict[str, str] = {}
    agent_listing: dict[str, str] = {}
    nested_memories: dict[str, Any] = {}
    for row in rows[:stop]:
        value = row.value
        if value.get("type") != "attachment":
            continue
        attachment = value.get("attachment")
        if not isinstance(attachment, Mapping):
            continue
        attachment_type = attachment.get("type")
        if attachment_type == "skill_listing":
            skill_listing = attachment.get("content")
        elif attachment_type == "deferred_tools_delta":
            _delta_state(
                deferred_tools,
                attachment,
                "addedNames",
                "removedNames",
            )
        elif attachment_type == "agent_listing_delta":
            _delta_state(
                agent_listing,
                attachment,
                "addedTypes",
                "removedTypes",
            )
        elif attachment_type == "nested_memory":
            path = str(
                attachment.get("path")
                or attachment.get("displayPath")
                or f"unknown-{row.line_no}"
            )
            nested_memories[path] = attachment.get("content")

    buckets: collections.Counter[str] = collections.Counter()
    buckets["skill_listing"] = textual_chars(skill_listing)
    buckets["deferred_tools"] = sum(len(line) for line in deferred_tools.values())
    buckets["agent_listing"] = sum(len(line) for line in agent_listing.values())
    buckets["claude_md"] = sum(
        textual_chars(content) for content in nested_memories.values()
    )
    return +buckets


def read_transcript(path: Path) -> Transcript:
    rows: list[TranscriptRow] = []
    malformed = 0
    non_object = 0
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line_no, line in enumerate(handle, 1):
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except (json.JSONDecodeError, UnicodeDecodeError, RecursionError):
                    malformed += 1
                    continue
                if not isinstance(value, dict):
                    non_object += 1
                    continue
                rows.append(TranscriptRow(line_no, value))
    except OSError:
        raise
    return Transcript(path, tuple(rows), malformed, non_object)


def session_id(transcript: Transcript) -> str:
    for row in transcript.rows:
        sid = row.value.get("sessionId")
        if isinstance(sid, str) and sid:
            return sid
    return transcript.path.stem


def transcript_paths() -> list[Path]:
    return sorted(
        path
        for path in TRANSCRIPT_ROOT.glob("*/*.jsonl")
        if "/subagents/" not in str(path)
    )


def call_key(value: Mapping[str, Any], index: int) -> str:
    message = value.get("message")
    message_id = message.get("id") if isinstance(message, Mapping) else None
    return str(value.get("requestId") or message_id or value.get("uuid") or index)


def calls_in_rows(rows: Sequence[TranscriptRow]) -> list[Call]:
    calls: list[Call] = []
    segment_keys: set[str] = set()
    for index, row in enumerate(rows):
        value = row.value
        if (
            value.get("subtype") == "compact_boundary"
            or value.get("type") == "last-prompt"
        ):
            # Request IDs can be replayed after compaction or session resume.
            # Within one such segment, however, Claude Code may interleave user
            # tool-result rows between fragments of the same API response.
            segment_keys.clear()
        if value.get("type") != "assistant":
            continue
        message = value.get("message")
        if not isinstance(message, Mapping):
            continue
        usage = usage_components(message.get("usage"))
        if usage is None:
            continue
        key = call_key(value, index)
        if key in segment_keys:
            continue
        segment_keys.add(key)
        calls.append(
            Call(
                index=index,
                key=key,
                input_tokens=usage["total_prompt_tokens"],
                usage=usage,
                model=str(message.get("model")) if message.get("model") else None,
                version=str(value.get("version")) if value.get("version") else None,
                request_id=str(value.get("requestId"))
                if value.get("requestId")
                else None,
            )
        )
    return calls


def boundary_indices(rows: Sequence[TranscriptRow]) -> list[int]:
    return [
        index
        for index, row in enumerate(rows)
        if row.value.get("subtype") == "compact_boundary"
    ]


def has_boundary(rows: Sequence[TranscriptRow], start: int, stop: int) -> bool:
    return any(
        row.value.get("subtype") == "compact_boundary" for row in rows[start:stop]
    )


def bucket_content_class(bucket: str) -> str:
    """Map named attribution buckets to one of the two fitted tokenization classes."""
    if bucket in {
        "claude_md",
        "skill_listing",
        "deferred_tools",
        "agent_listing",
    } or bucket.startswith(("hook:", "skill:", "file:", "attachment:")):
        return "prose"
    return "structured"


def calibration_samples(transcript: Transcript) -> list[CalibrationSample]:
    """Build independent calibration anchors from CC's compactMetadata.postTokens.

    postTokens describes the compacted conversation payload. Durable ambient
    attachments are deliberately excluded here because they live in the stable
    prefix, but are added back when composing the full first post-compact prompt.
    """
    rows = transcript.rows
    tools = tool_name_map(rows)
    calls = calls_in_rows(rows)
    sid = session_id(transcript)
    samples: list[CalibrationSample] = []
    boundaries = boundary_indices(rows)
    for number, index in enumerate(boundaries):
        metadata = rows[index].value.get("compactMetadata")
        if not isinstance(metadata, Mapping):
            continue
        target = integer(metadata.get("postTokens"))
        if target is None or target <= 0:
            continue
        next_boundary = (
            boundaries[number + 1] if number + 1 < len(boundaries) else len(rows)
        )
        first = call_after_boundary(calls, index, next_boundary)
        if first is None:
            continue
        preserved, _ = preserved_rows(rows, index, metadata)
        buckets: collections.Counter[str] = collections.Counter()
        for preserved_row in preserved:
            buckets.update(record_buckets(preserved_row.value, tools))
        buckets.update(boundary_post_rows_buckets(rows, index + 1, first.index, tools))
        prose = sum(
            chars
            for bucket, chars in buckets.items()
            if bucket_content_class(bucket) == "prose"
        )
        structured = sum(
            chars
            for bucket, chars in buckets.items()
            if bucket_content_class(bucket) == "structured"
        )
        if prose + structured <= 0:
            continue
        raw_json_chars = sum(
            len(compact_json(candidate.value))
            for candidate in rows[index + 1 : first.index]
        )
        boundary_uuid = str(
            rows[index].value.get("uuid") or f"line-{rows[index].line_no}"
        )
        samples.append(
            CalibrationSample(
                prose_chars=prose,
                structured_chars=structured,
                target_tokens=target,
                sid=sid,
                key=f"{sid}:{boundary_uuid}:line-{rows[index].line_no}",
                raw_json_chars=raw_json_chars,
            )
        )
    return samples


def _metric_summary(
    actual: Sequence[float], predicted: Sequence[float]
) -> dict[str, Any]:
    pairs = [
        (float(target), float(estimate))
        for target, estimate in zip(actual, predicted)
        if target > 0 and math.isfinite(target) and math.isfinite(estimate)
    ]
    if not pairs:
        return {
            "n": 0,
            "r2": None,
            "mae_tokens": None,
            "median_absolute_percentage_error_pct": None,
            "p90_absolute_percentage_error_pct": None,
            "estimates_exceeded_target": 0,
            "excess_tokens": distribution([]),
        }
    targets = [target for target, _ in pairs]
    errors = [estimate - target for target, estimate in pairs]
    mean_target = sum(targets) / len(targets)
    sse = sum(error * error for error in errors)
    sst = sum((target - mean_target) ** 2 for target in targets)
    apes = [100.0 * abs(error) / target for target, error in zip(targets, errors)]
    excess = [error for error in errors if error > 0]
    return {
        "n": len(pairs),
        "r2": 1.0 - sse / sst if sst > 0 else (1.0 if sse == 0 else None),
        "mae_tokens": sum(abs(error) for error in errors) / len(errors),
        "median_absolute_percentage_error_pct": median(apes),
        "p90_absolute_percentage_error_pct": percentile(apes, 0.90),
        "estimates_exceeded_target": len(excess),
        "excess_tokens": distribution(excess),
    }


def _calibration_partition(
    samples: Sequence[CalibrationSample],
) -> tuple[list[CalibrationSample], list[CalibrationSample], str]:
    if len(samples) < 10:
        return list(samples), list(samples), "all_samples_reused_below_10"
    fit: list[CalibrationSample] = []
    heldout: list[CalibrationSample] = []
    for sample in samples:
        digest = hashlib.sha256(sample.key.encode("utf-8")).digest()
        (heldout if int.from_bytes(digest[:4], "big") % 5 == 0 else fit).append(sample)
    if not fit or not heldout:
        return list(samples), list(samples), "all_samples_reused_degenerate_split"
    return fit, heldout, "stable_sha256_80_20"


def fit_calibration(
    samples: Sequence[CalibrationSample],
) -> dict[str, Any]:
    """Fit tokens = prose_slope*chars + structured_slope*chars through the origin."""
    if not samples:
        return {
            "state": "unavailable",
            "method": "two_feature_through_origin_ols_against_compactMetadata.postTokens",
            "samples_total": 0,
            "classes": {},
            "combined_validation": _metric_summary([], []),
        }
    fit, heldout, split_policy = _calibration_partition(samples)
    pp = sum(sample.prose_chars**2 for sample in fit)
    ps = sum(sample.prose_chars * sample.structured_chars for sample in fit)
    ss = sum(sample.structured_chars**2 for sample in fit)
    py = sum(sample.prose_chars * sample.target_tokens for sample in fit)
    sy = sum(sample.structured_chars * sample.target_tokens for sample in fit)
    determinant = pp * ss - ps * ps
    if determinant <= 0:
        return fit_calibration(())
    prose_slope = (py * ss - sy * ps) / determinant
    structured_slope = (sy * pp - py * ps) / determinant
    if prose_slope <= 0 or structured_slope <= 0:
        return fit_calibration(())

    slopes = {"prose": prose_slope, "structured": structured_slope}
    combined_predictions = [
        sample.prose_chars * prose_slope + sample.structured_chars * structured_slope
        for sample in heldout
    ]
    pooled_denominator = sum(
        (sample.prose_chars + sample.structured_chars) ** 2 for sample in fit
    )
    pooled_numerator = sum(
        (sample.prose_chars + sample.structured_chars) * sample.target_tokens
        for sample in fit
    )
    if pooled_denominator <= 0 or pooled_numerator <= 0:
        return fit_calibration(())
    pooled_slope = pooled_numerator / pooled_denominator
    pooled_validation = _metric_summary(
        [sample.target_tokens for sample in heldout],
        [
            (sample.prose_chars + sample.structured_chars) * pooled_slope
            for sample in heldout
        ],
    )
    classes: dict[str, Any] = {}
    for class_name, field, other_name, other_field in (
        ("prose", "prose_chars", "structured", "structured_chars"),
        ("structured", "structured_chars", "prose", "prose_chars"),
    ):
        class_slope = slopes[class_name]
        other_slope = slopes[other_name]
        actual: list[float] = []
        predicted: list[float] = []
        exceeded_authoritative = 0
        for sample in heldout:
            chars = getattr(sample, field)
            if chars <= 0:
                continue
            estimate = chars * class_slope
            partial_target = (
                sample.target_tokens - getattr(sample, other_field) * other_slope
            )
            if partial_target > 0:
                actual.append(partial_target)
                predicted.append(estimate)
            exceeded_authoritative += estimate > sample.target_tokens
        metrics = _metric_summary(actual, predicted)
        heldout_r2 = finite_number(metrics.get("r2"))
        reliable = heldout_r2 is not None and heldout_r2 > 0
        classes[class_name] = {
            "chars_per_token": 1.0 / class_slope,
            "reliable": reliable,
            "reliability_state": (
                "reliable_positive_heldout_r2"
                if reliable
                else "unreliable_nonpositive_heldout_r2"
            ),
            "attribution_ratio": ("class_fitted" if reliable else "pooled_combined"),
            "samples_fit": sum(getattr(sample, field) > 0 for sample in fit),
            "samples_validation": sum(getattr(sample, field) > 0 for sample in heldout),
            "validation_target": (f"postTokens_minus_fitted_{other_name}_component"),
            "estimates_exceeded_authoritative_total": exceeded_authoritative,
            **metrics,
        }

    raw_ratios = [
        sample.raw_json_chars / sample.target_tokens
        for sample in samples
        if sample.raw_json_chars > 0 and sample.target_tokens > 0
    ]
    return {
        "state": "fitted",
        "method": "two_feature_through_origin_ols_against_compactMetadata.postTokens",
        "samples_total": len(samples),
        "samples_fit": len(fit),
        "samples_validation": len(heldout),
        "split_policy": split_policy,
        "classes": classes,
        "pooled": {
            "chars_per_token": 1.0 / pooled_slope,
            "samples_fit": len(fit),
            "samples_validation": len(heldout),
            "reliable": (
                finite_number(pooled_validation.get("r2")) is not None
                and float(pooled_validation["r2"]) > 0
            ),
            "reliability_state": (
                "reliable_positive_heldout_r2"
                if finite_number(pooled_validation.get("r2")) is not None
                and float(pooled_validation["r2"]) > 0
                else "unreliable_nonpositive_heldout_r2"
            ),
            **pooled_validation,
        },
        "combined_validation": _metric_summary(
            [sample.target_tokens for sample in heldout],
            combined_predictions,
        ),
        "post_tokens_anchor": {
            "target": "compactMetadata.postTokens",
            "raw_json_chars_per_token": distribution(raw_ratios),
            "note": (
                "raw JSON chars are an independent diagnostic only; fitted features "
                "count prompt payload chars and exclude durable stable-prefix attachments"
            ),
        },
    }


def calibration_public(calibration: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: calibration.get(key)
        for key in (
            "state",
            "method",
            "samples_total",
            "samples_fit",
            "samples_validation",
            "split_policy",
            "classes",
            "pooled",
            "combined_validation",
            "post_tokens_anchor",
            "anchor_probes",
        )
        if key in calibration
    }


def estimate_and_reconcile(
    char_buckets: Mapping[str, int],
    authoritative_tokens: int,
    calibration: Mapping[str, Any],
) -> tuple[dict[str, int], dict[str, Any]]:
    """Estimate named sources and expose a signed authoritative residual.

    A negative residual is intentionally retained as a calibration failure. No
    bucket is silently rescaled to manufacture a plausible reconciliation.
    """
    positive = {key: value for key, value in char_buckets.items() if value > 0}
    class_data = calibration.get("classes")
    class_data = class_data if isinstance(class_data, Mapping) else {}
    pooled_data = calibration.get("pooled")
    pooled_ratio = finite_number(
        pooled_data.get("chars_per_token") if isinstance(pooled_data, Mapping) else None
    )
    ratio_map: dict[str, float] = {}
    class_methods: dict[str, str] = {}
    for name in ("prose", "structured"):
        details = class_data.get(name)
        class_ratio = finite_number(
            details.get("chars_per_token") if isinstance(details, Mapping) else None
        )
        reliable = isinstance(details, Mapping) and details.get("reliable") is True
        if reliable and class_ratio is not None and class_ratio > 0:
            ratio_map[name] = float(class_ratio)
            class_methods[name] = f"class_fitted:{name}"
        elif pooled_ratio is not None and pooled_ratio > 0:
            ratio_map[name] = float(pooled_ratio)
            class_methods[name] = f"pooled_combined:{name}_unreliable"
    if len(ratio_map) < 2:
        return {"system_and_tools": authoritative_tokens}, {
            "raw_estimated_tokens": 0.0,
            "reconciliation_scale": None,
            "estimation_overflow_tokens": 0.0,
            "calibration_failure": False,
            "downscaled": False,
            "class_estimated_tokens": {},
            "class_attribution_methods": {},
            "bucket_estimation_methods": {"system_and_tools": "authoritative_residual"},
            "residual_basis": "authoritative_total_minus_parsed_estimates",
        }

    raw = {
        key: value / ratio_map[bucket_content_class(key)]
        for key, value in positive.items()
    }
    raw_total = sum(raw.values())
    allocated = {key: int(round(value)) for key, value in raw.items()}
    allocated = {key: value for key, value in allocated.items() if value > 0}
    allocated["system_and_tools"] = authoritative_tokens - sum(allocated.values())
    class_estimates: dict[str, float] = collections.defaultdict(float)
    for key, value in raw.items():
        class_estimates[bucket_content_class(key)] += value
    bucket_methods = {key: class_methods[bucket_content_class(key)] for key in raw}
    bucket_methods["system_and_tools"] = "authoritative_residual"
    overflow = max(0.0, raw_total - authoritative_tokens)
    return dict(sorted(allocated.items())), {
        "raw_estimated_tokens": raw_total,
        "reconciliation_scale": 1.0,
        "estimation_overflow_tokens": overflow,
        "calibration_failure": overflow > 0,
        "downscaled": False,
        "class_estimated_tokens": dict(sorted(class_estimates.items())),
        "class_attribution_methods": dict(sorted(class_methods.items())),
        "bucket_estimation_methods": dict(sorted(bucket_methods.items())),
        "residual_basis": "authoritative_total_minus_parsed_estimates",
    }


def preserved_rows(
    rows: Sequence[TranscriptRow],
    boundary_index: int,
    metadata: Mapping[str, Any],
) -> tuple[list[TranscriptRow], str]:
    by_uuid = {
        str(row.value.get("uuid")): row
        for row in rows[:boundary_index]
        if row.value.get("uuid")
    }
    messages = metadata.get("preservedMessages")
    if isinstance(messages, Mapping):
        uuids = messages.get("allUuids") or messages.get("uuids")
        if isinstance(uuids, list):
            selected = [by_uuid[str(uuid)] for uuid in uuids if str(uuid) in by_uuid]
            if selected:
                return selected, "preservedMessages.allUuids"

    segment = metadata.get("preservedSegment")
    if isinstance(segment, Mapping):
        head = str(segment.get("headUuid") or "")
        tail = str(segment.get("tailUuid") or "")
        indices = {
            str(row.value.get("uuid")): index
            for index, row in enumerate(rows[:boundary_index])
            if row.value.get("uuid")
        }
        if head in indices:
            start = indices[head]
            stop = indices.get(tail, boundary_index - 1) + 1
            if start < stop <= boundary_index:
                return [
                    row
                    for row in rows[start:stop]
                    if row.value.get("type") in PROMPT_RECORD_TYPES
                ], "preservedSegment.head_to_tail"
    return [], "unavailable"


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _command_paths(command: str, base: Path = CONFIG_REPO) -> set[Path]:
    paths: set[Path] = set()
    try:
        parts = shlex.split(command)
    except ValueError:
        parts = command.split()
    for part in parts:
        part = part.replace("${STRATA_HOME}", str(CONFIG_REPO))
        part = part.replace("$STRATA_HOME", str(CONFIG_REPO))
        candidate = Path(os.path.expandvars(os.path.expanduser(part)))
        if not candidate.is_absolute() and part.endswith((".sh", ".py", ".js", ".ts")):
            candidate = base / candidate
        try:
            resolved = candidate.resolve()
            resolved.relative_to(CONFIG_REPO.resolve())
        except (OSError, ValueError):
            continue
        if resolved.suffix in (".sh", ".py", ".js", ".ts"):
            paths.add(resolved)
    return paths


def configured_compaction_paths(
    settings_path: Path = SETTINGS_PATH,
) -> list[str]:
    """Discover the live compaction-stack scripts and their local dependencies."""
    try:
        settings = json.loads(settings_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    hooks = settings.get("hooks") if isinstance(settings, Mapping) else None
    hooks = hooks if isinstance(hooks, Mapping) else {}
    selected: set[Path] = set()
    for event, groups in hooks.items():
        if event not in ("PreCompact", "SessionStart", "PreToolUse"):
            continue
        if not isinstance(groups, list):
            continue
        for group in groups:
            if not isinstance(group, Mapping):
                continue
            for hook in group.get("hooks") or []:
                if not isinstance(hook, Mapping):
                    continue
                command = str(hook.get("command") or "")
                command_lower = command.lower()
                if not any(
                    marker in command_lower
                    for marker in ("pre-compaction", "post-compaction", "resume-read")
                ):
                    continue
                selected.update(_command_paths(command))

    # Shell wrappers commonly exec a sibling Python implementation. Follow only
    # source references rooted under the config repo so discovery remains bounded.
    pending = list(selected)
    source_re = re.compile(r"[\w./${}-]+\.(?:sh|py|js|ts)")
    while pending:
        path = pending.pop()
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for token in source_re.findall(text):
            token = token.replace("${STRATA_HOME}", str(CONFIG_REPO))
            token = token.replace("$STRATA_HOME", str(CONFIG_REPO))
            token = token.replace("${CLAUDE_CONFIG_DIR}", str(CONFIG_REPO))
            token = token.replace("$CLAUDE_CONFIG_DIR", str(CONFIG_REPO))
            candidate = Path(os.path.expandvars(os.path.expanduser(token)))
            if not candidate.is_absolute():
                candidate = path.parent / candidate
            try:
                resolved = candidate.resolve()
                resolved.relative_to(CONFIG_REPO.resolve())
            except (OSError, ValueError):
                continue
            if resolved.exists() and resolved not in selected:
                selected.add(resolved)
                pending.append(resolved)
    return sorted(str(path.relative_to(CONFIG_REPO)) for path in selected)


def load_regime_history(
    repo: Path = CONFIG_REPO,
    paths: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """Return chronological git regimes for the discovered compaction stack."""
    relevant = list(paths) if paths is not None else configured_compaction_paths()
    if not relevant:
        return []
    command = [
        "git",
        "-C",
        str(repo),
        "log",
        "--all",
        "--format=%H%x09%cI%x09%s",
        "--",
        *relevant,
    ]
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    history: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        parts = line.split("\t", 2)
        if len(parts) != 3:
            continue
        parsed = parse_timestamp(parts[1])
        if parsed is None:
            continue
        history.append(
            {
                "id": parts[0][:7],
                "commit": parts[0],
                "timestamp": parts[1],
                "timestamp_epoch": parsed.timestamp(),
                "subject": parts[2],
                "relevant_paths": relevant,
            }
        )
    history.sort(key=lambda item: item["timestamp_epoch"])
    if history:
        history[-1]["is_current"] = True
    return history


def regime_for_timestamp(
    timestamp: Any, history: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    if not history:
        return {
            "id": "unknown",
            "commit": None,
            "timestamp": None,
            "subject": "config history unavailable",
            "is_current": False,
            "basis": "git_log_of_discovered_compaction_stack_paths",
        }
    parsed = parse_timestamp(timestamp)
    if parsed is None:
        return {
            "id": "unknown",
            "commit": None,
            "timestamp": None,
            "subject": "timestamp unavailable",
            "is_current": False,
            "basis": "git_log_of_discovered_compaction_stack_paths",
        }
    candidates = [
        item
        for item in history
        if finite_number(item.get("timestamp_epoch")) is not None
        and float(item["timestamp_epoch"]) <= parsed.timestamp()
    ]
    if not candidates:
        return {
            "id": "pre-history",
            "commit": None,
            "timestamp": None,
            "subject": "before first relevant compaction-stack commit",
            "is_current": False,
            "basis": "git_log_of_discovered_compaction_stack_paths",
        }
    selected = candidates[-1]
    return {
        "id": selected.get("id"),
        "commit": selected.get("commit"),
        "timestamp": selected.get("timestamp"),
        "subject": selected.get("subject"),
        "is_current": bool(selected.get("is_current")),
        "basis": "git_log_of_discovered_compaction_stack_paths",
    }


def hooks_fired(rows: Sequence[TranscriptRow], start: int, stop: int) -> dict[str, Any]:
    counts: collections.Counter[str] = collections.Counter()
    for row in rows[max(0, start) : stop]:
        value = row.value
        if value.get("type") != "attachment":
            continue
        attachment = value.get("attachment")
        if not isinstance(attachment, Mapping):
            continue
        attachment_type = attachment.get("type")
        if attachment_type == "hook_success":
            counts[hook_script_name(attachment)] += 1
        elif attachment_type == "hook_additional_context":
            counts[additional_context_hook_name(attachment)] += 1
    names = sorted(counts)
    return {
        "names": names,
        "counts": dict(sorted(counts.items())),
        "set_id": "+".join(names) if names else "none-recorded",
        "basis": "hook_success_and_hook_additional_context_attachments",
    }


def infer_session_context_window(
    rows: Sequence[TranscriptRow],
    calls: Sequence[Call],
    boundaries: Sequence[TranscriptRow],
) -> tuple[int | None, str, dict[str, Any]]:
    max_call = max((call.input_tokens for call in calls), default=0)
    pre_values: list[int] = []
    for row in boundaries:
        metadata = row.value.get("compactMetadata")
        if isinstance(metadata, Mapping):
            value = integer(metadata.get("preTokens"))
            if value is not None:
                pre_values.append(value)
    max_pre = max(pre_values, default=0)
    evidence = {
        "max_observed_prompt_tokens": max_call,
        "max_observed_pre_tokens": max_pre,
        "explicit_extended_model_markers": [],
    }
    if max(max_call, max_pre) > BASE_CONTEXT_WINDOW:
        return (
            EXTENDED_CONTEXT_WINDOW,
            "session_observed_above_200k",
            evidence,
        )
    markers: set[str] = set()
    for row in rows:
        value = row.value
        for key in ("originalModel", "fallbackModel", "model"):
            model = value.get(key)
            if isinstance(model, str) and "[1m]" in model.lower():
                markers.add(f"{key}={model}")
        message = value.get("message")
        if isinstance(message, Mapping):
            model = message.get("model")
            if isinstance(model, str) and "[1m]" in model.lower():
                markers.add(f"message.model={model}")
    if markers:
        evidence["explicit_extended_model_markers"] = sorted(markers)
        return (
            EXTENDED_CONTEXT_WINDOW,
            "explicit_transcript_1m_model_marker",
            evidence,
        )
    return (
        None,
        "indeterminate_manual_session_never_reached_200k",
        evidence,
    )


def call_after_boundary(
    calls: Sequence[Call], boundary_index: int, next_boundary: int
) -> Call | None:
    for call in calls:
        if boundary_index < call.index < next_boundary and call.input_tokens > 0:
            return call
    return None


def previous_call(calls: Sequence[Call], boundary_index: int) -> Call | None:
    result = None
    for call in calls:
        if call.index >= boundary_index:
            break
        result = call
    return result


def boundary_refill(
    rows: Sequence[TranscriptRow],
    calls: Sequence[Call],
    first_call: Call,
    next_boundary: int,
    tools: Mapping[str, str],
    calibration: Mapping[str, Any],
) -> dict[str, Any]:
    segment_calls = [
        call
        for call in calls
        if first_call.index <= call.index < next_boundary and call.input_tokens > 0
    ]
    transitions = list(zip(segment_calls, segment_calls[1:]))
    net_deltas = [
        current.input_tokens - previous.input_tokens
        for previous, current in transitions
    ]
    positive_count = 0
    negative_count = 0
    bucket_tokens: collections.Counter[str] = collections.Counter()
    bucket_methods: dict[str, collections.Counter[str]] = collections.defaultdict(
        collections.Counter
    )
    positive_total = 0
    for previous, current in transitions:
        delta = current.input_tokens - previous.input_tokens
        if delta <= 0:
            negative_count += 1
            continue
        positive_count += 1
        positive_total += delta
        chars = rows_buckets(rows, previous.index, current.index, tools)
        estimates, diagnostics = estimate_and_reconcile(chars, delta, calibration)
        bucket_tokens.update(estimates)
        methods = diagnostics.get("bucket_estimation_methods")
        if isinstance(methods, Mapping):
            for bucket, method in methods.items():
                if bucket in estimates:
                    bucket_methods[str(bucket)][str(method)] += 1

    denominator = len(transitions)
    bucket_per_turn = (
        {key: value / denominator for key, value in sorted(bucket_tokens.items())}
        if denominator
        else {}
    )
    net_total = (
        segment_calls[-1].input_tokens - segment_calls[0].input_tokens
        if len(segment_calls) >= 2
        else 0
    )
    return {
        "model_turns": len(segment_calls),
        "transitions": denominator,
        "positive_growth_transitions": positive_count,
        "nonpositive_or_reset_transitions": negative_count,
        "starting_prompt_tokens": first_call.input_tokens,
        "ending_prompt_tokens": segment_calls[-1].input_tokens
        if segment_calls
        else first_call.input_tokens,
        "net_growth_tokens": net_total,
        "net_tokens_per_turn": net_total / denominator if denominator else None,
        "median_authoritative_delta_tokens": median(net_deltas) if net_deltas else None,
        "positive_tokens_added": positive_total,
        "positive_tokens_added_per_turn": positive_total / denominator
        if denominator
        else None,
        "bucket_tokens": dict(sorted(bucket_tokens.items())),
        "bucket_tokens_per_turn": bucket_per_turn,
        "bucket_estimation_methods": {
            bucket: "+".join(sorted(method_counts))
            for bucket, method_counts in sorted(bucket_methods.items())
        },
        "turn_definition": "successive distinct assistant API requests",
    }


def transcript_timestamp(rows: Sequence[TranscriptRow]) -> str:
    for row in reversed(rows):
        timestamp = row.value.get("timestamp")
        if isinstance(timestamp, str) and timestamp:
            return timestamp
    return "unknown"


def analyze_transcript(
    transcript: Transcript,
    calibration: Mapping[str, Any],
    regime_history: Sequence[Mapping[str, Any]] = (),
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = transcript.rows
    sid = session_id(transcript)
    tools = tool_name_map(rows)
    calls = calls_in_rows(rows)
    boundaries = boundary_indices(rows)
    boundary_rows: list[dict[str, Any]] = []
    session_window, window_basis, window_evidence = infer_session_context_window(
        rows, calls, [rows[index] for index in boundaries]
    )

    for boundary_number, index in enumerate(boundaries, 1):
        row = rows[index]
        boundary = row.value
        metadata = boundary.get("compactMetadata")
        metadata = metadata if isinstance(metadata, Mapping) else {}
        next_index = (
            boundaries[boundary_number]
            if boundary_number < len(boundaries)
            else len(rows)
        )
        first = call_after_boundary(calls, index, next_index)
        boundary_uuid = str(boundary.get("uuid") or f"line-{row.line_no}")
        timestamp = boundary.get("timestamp") or transcript_timestamp(rows)
        config_regime = regime_for_timestamp(timestamp, regime_history)
        before = previous_call(calls, index)
        fired = hooks_fired(
            rows,
            before.index + 1 if before else index + 1,
            first.index if first else next_index,
        )
        boundary_window = session_window
        boundary_window_basis = window_basis
        if boundary_window is None and metadata.get("trigger") == "auto":
            boundary_window = BASE_CONTEXT_WINDOW
            boundary_window_basis = "auto_compaction_without_extended_evidence"
        common = {
            "ts": timestamp,
            "sid": sid,
            "kind": KIND,
            "source": SOURCE,
            "schema": SCHEMA,
            "row_type": "boundary",
            # UUIDs can be replayed after resume. The physical line makes each actual
            # compact-boundary record distinct while remaining stable across reruns.
            "ledger_id": (
                f"v{SCHEMA}:boundary:{sid}:{boundary_uuid}:line-{row.line_no}"
            ),
            "boundary_uuid": boundary_uuid,
            "boundary_number": boundary_number,
            "boundary_line": row.line_no,
            "transcript_path": str(transcript.path),
            "trigger": metadata.get("trigger"),
            "pre_tokens": integer(metadata.get("preTokens")),
            "compact_metadata_post_tokens": integer(metadata.get("postTokens")),
            "duration_ms": integer(metadata.get("durationMs")),
            "malformed_lines_in_transcript": transcript.malformed_lines,
            "calibration": calibration_public(calibration),
            "config_regime": config_regime,
            "hooks_fired": fired,
            "context_window_tokens": boundary_window,
            "context_window_basis": boundary_window_basis,
            "context_window_evidence": window_evidence,
        }
        if first is None or first.input_tokens <= 0:
            common.update(
                {
                    "measurement_state": "missing_authoritative_post_usage",
                    "attribution_state": "unavailable",
                    "post_prompt_tokens": None,
                    "fill_pct": None,
                    "buckets": {},
                    "bucket_chars": {},
                    "refill": {
                        "model_turns": 0,
                        "transitions": 0,
                        "turn_definition": "successive distinct assistant API requests",
                    },
                }
            )
            boundary_rows.append(common)
            continue

        preserved, preserved_basis = preserved_rows(rows, index, metadata)
        char_buckets: collections.Counter[str] = collections.Counter()
        for preserved_row in preserved:
            char_buckets.update(record_buckets(preserved_row.value, tools))
        char_buckets.update(
            boundary_post_rows_buckets(rows, index + 1, first.index, tools)
        )
        char_buckets.update(durable_ambient_buckets(rows, first.index))
        estimates, reconciliation = estimate_and_reconcile(
            char_buckets, first.input_tokens, calibration
        )
        fill_pct = (
            100.0 * first.input_tokens / boundary_window if boundary_window else None
        )
        fill_pct_bounds = {
            "if_1m": 100.0 * first.input_tokens / EXTENDED_CONTEXT_WINDOW,
            "if_200k": 100.0 * first.input_tokens / BASE_CONTEXT_WINDOW,
        }

        pre_usage_total = None
        pre_usage_delta = None
        pre_usage_delta_pct = None
        if before:
            pre_usage_total = before.input_tokens + before.usage["output_tokens"]
            if common["pre_tokens"] is not None:
                pre_usage_delta = common["pre_tokens"] - pre_usage_total
                pre_usage_delta_pct = (
                    100.0 * pre_usage_delta / common["pre_tokens"]
                    if common["pre_tokens"]
                    else None
                )

        explicit_attachment_records = sum(
            1
            for candidate in rows[index + 1 : first.index]
            if candidate.value.get("type") == "attachment"
        )
        attribution_state = (
            "attributed"
            if preserved_basis != "unavailable" or explicit_attachment_records
            else "partial_legacy_unattributed"
        )
        common.update(
            {
                "measurement_state": "measured",
                "attribution_state": attribution_state,
                "attribution_notes": (
                    []
                    if attribution_state == "attributed"
                    else [
                        "older boundary has no preserved UUID list or post-boundary attachment records; residual includes content that cannot be named"
                    ]
                ),
                "model": first.model,
                "claude_code_version": first.version,
                "post_assistant_line": rows[first.index].line_no,
                "post_request_id": first.request_id,
                "usage": first.usage,
                "post_prompt_tokens": first.input_tokens,
                "fill_pct": fill_pct,
                "fill_pct_bounds_if_window_unknown": (
                    fill_pct_bounds if boundary_window is None else None
                ),
                "preserved_segment_basis": preserved_basis,
                "preserved_records_attributed": len(preserved),
                "post_boundary_attachment_records": explicit_attachment_records,
                "bucket_chars": dict(sorted(char_buckets.items())),
                "buckets": estimates,
                "bucket_sum_tokens": sum(estimates.values()),
                "reconciliation": reconciliation,
                "last_pre_boundary_usage_tokens": pre_usage_total,
                "pre_tokens_minus_last_usage": pre_usage_delta,
                "pre_tokens_minus_last_usage_pct": pre_usage_delta_pct,
                "refill": boundary_refill(
                    rows,
                    calls,
                    first,
                    next_index,
                    tools,
                    calibration,
                ),
            }
        )
        boundary_rows.append(common)

    measured = [
        item for item in boundary_rows if item["measurement_state"] == "measured"
    ]
    fills = [item["post_prompt_tokens"] for item in measured]
    fill_pcts = [item["fill_pct"] for item in measured if item["fill_pct"] is not None]
    session_buckets: collections.Counter[str] = collections.Counter()
    session_refill_buckets: collections.Counter[str] = collections.Counter()
    session_refill_transitions = 0
    session_refill_net = 0
    session_refill_positive = 0
    for item in measured:
        item_buckets = item.get("buckets")
        if isinstance(item_buckets, Mapping):
            session_buckets.update(
                {str(key): integer(value) or 0 for key, value in item_buckets.items()}
            )
        refill = item.get("refill")
        if not isinstance(refill, Mapping):
            continue
        session_refill_transitions += integer(refill.get("transitions")) or 0
        session_refill_net += integer(refill.get("net_growth_tokens")) or 0
        session_refill_positive += integer(refill.get("positive_tokens_added")) or 0
        refill_buckets = refill.get("bucket_tokens")
        if isinstance(refill_buckets, Mapping):
            session_refill_buckets.update(
                {str(key): integer(value) or 0 for key, value in refill_buckets.items()}
            )
    session_row = {
        "ts": transcript_timestamp(rows),
        "sid": sid,
        "kind": KIND,
        "source": SOURCE,
        "schema": SCHEMA,
        "row_type": "session",
        "ledger_id": f"v{SCHEMA}:session:{sid}",
        "transcript_path": str(transcript.path),
        "boundaries_detected": len(boundaries),
        "boundaries_measured": len(measured),
        "boundaries_missing_usage": len(boundaries) - len(measured),
        "boundaries_partial_legacy_unattributed": sum(
            item.get("attribution_state") == "partial_legacy_unattributed"
            for item in boundary_rows
        ),
        "trigger_counts": dict(
            sorted(
                collections.Counter(
                    str(item.get("trigger") or "unknown") for item in boundary_rows
                ).items()
            )
        ),
        "models": sorted(
            {
                str(item["model"])
                for item in measured
                if isinstance(item.get("model"), str)
            }
        ),
        "malformed_lines": transcript.malformed_lines,
        "non_object_lines": transcript.non_object_lines,
        "post_prompt_tokens_distribution": distribution(fills),
        "fill_pct_distribution_known_windows": distribution(fill_pcts),
        "context_window_tokens": session_window,
        "context_window_basis": window_basis,
        "context_window_evidence": window_evidence,
        "boundary_bucket_tokens": dict(sorted(session_buckets.items())),
        "refill": {
            "transitions": session_refill_transitions,
            "net_growth_tokens": session_refill_net,
            "net_tokens_per_turn": (
                session_refill_net / session_refill_transitions
                if session_refill_transitions
                else None
            ),
            "positive_tokens_added": session_refill_positive,
            "positive_tokens_added_per_turn": (
                session_refill_positive / session_refill_transitions
                if session_refill_transitions
                else None
            ),
            "bucket_tokens": dict(sorted(session_refill_buckets.items())),
            "bucket_tokens_per_turn": {
                key: value / session_refill_transitions
                for key, value in sorted(session_refill_buckets.items())
            }
            if session_refill_transitions
            else {},
            "turn_definition": "successive distinct assistant API requests",
        },
        "calibration": calibration_public(calibration),
    }
    first_positive_call = next(
        (call for call in calls if call.input_tokens > 0),
        None,
    )
    if not boundaries and first_positive_call is not None:
        floor_timestamp = rows[first_positive_call.index].value.get(
            "timestamp"
        ) or transcript_timestamp(rows)
        session_row["session_floor"] = {
            "state": "measured",
            "tokens": first_positive_call.input_tokens,
            "usage": first_positive_call.usage,
            "assistant_line": rows[first_positive_call.index].line_no,
            "timestamp": floor_timestamp,
            "config_regime": regime_for_timestamp(floor_timestamp, regime_history),
        }
    else:
        session_row["session_floor"] = {
            "state": (
                "not_applicable_session_has_compaction"
                if boundaries
                else "missing_first_assistant_usage"
            ),
            "tokens": None,
        }
    return boundary_rows, session_row


def atomic_write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True))
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def existing_ledger_ids(events_path: Path) -> set[str]:
    result: set[str] = set()
    try:
        with events_path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                if KIND not in line:
                    continue
                try:
                    row = json.loads(line)
                except (json.JSONDecodeError, RecursionError):
                    continue
                if (
                    isinstance(row, dict)
                    and row.get("kind") == KIND
                    and row.get("source") == SOURCE
                    and isinstance(row.get("ledger_id"), str)
                ):
                    result.add(row["ledger_id"])
    except FileNotFoundError:
        pass
    return result


def append_missing_events(
    rows: Sequence[Mapping[str, Any]], events_path: Path = EVENTS_PATH
) -> int:
    """Append each stable ledger entity at most once for this schema."""
    events_path.parent.mkdir(parents=True, exist_ok=True)
    known = existing_ledger_ids(events_path)
    missing: list[Mapping[str, Any]] = []
    for row in rows:
        ledger_id = row.get("ledger_id")
        if not isinstance(ledger_id, str) or ledger_id in known:
            continue
        known.add(ledger_id)
        missing.append(row)
    if not missing:
        return 0
    with events_path.open("a", encoding="utf-8") as handle:
        for row in missing:
            # Envelope fields are constructed last, matching telemetry-emit.sh's
            # payload-cannot-override invariant.
            payload = {
                key: value
                for key, value in row.items()
                if key not in ("ts", "sid", "kind", "source")
            }
            envelope = payload | {
                "ts": row.get("ts") or "unknown",
                "sid": row.get("sid") or "unknown",
                "kind": KIND,
                "source": SOURCE,
            }
            handle.write(json.dumps(envelope, ensure_ascii=False, sort_keys=True))
            handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    return len(missing)


def load_ledger(path: Path = LEDGER_PATH) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    malformed = 0
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except (json.JSONDecodeError, RecursionError):
                    malformed += 1
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except FileNotFoundError:
        pass
    return rows, malformed


def fallback_calibration() -> dict[str, Any] | None:
    rows, _ = load_ledger()
    for row in rows:
        calibration = row.get("calibration")
        if (
            isinstance(calibration, dict)
            and calibration.get("state") == "fitted"
            and isinstance(calibration.get("classes"), Mapping)
            and all(
                finite_number(
                    calibration["classes"].get(name, {}).get("chars_per_token")
                    if isinstance(calibration["classes"].get(name), Mapping)
                    else None
                )
                for name in ("prose", "structured")
            )
        ):
            result = dict(calibration)
            result["source"] = "existing_backfill"
            return result
    return None


def calibration_anchor_probes(
    skill_candidate: Mapping[str, Any] | None,
    calibration: Mapping[str, Any],
) -> list[dict[str, Any]]:
    classes = calibration.get("classes")
    classes = classes if isinstance(classes, Mapping) else {}
    prose = classes.get("prose")
    ratio = finite_number(
        prose.get("chars_per_token") if isinstance(prose, Mapping) else None
    )
    probes: list[dict[str, Any]] = []
    if ratio and ratio > 0:
        try:
            text = CLAUDE_MD_PATH.read_text(encoding="utf-8", errors="replace")
            chars = len(text)
            predicted = chars / ratio
            reference = 7_100
            probes.append(
                {
                    "name": str(CLAUDE_MD_PATH),
                    "content_class": "prose",
                    "chars": chars,
                    "bytes": CLAUDE_MD_PATH.stat().st_size,
                    "predicted_tokens": predicted,
                    "reference_tokens_approx": reference,
                    "difference_pct": 100.0 * (predicted - reference) / reference,
                    "selection": "fixed_known_file",
                }
            )
        except OSError:
            pass

        if skill_candidate:
            chars = integer(skill_candidate.get("chars")) or 0
            predicted = chars / ratio
            reference = 7_251
            probes.append(
                {
                    "name": "largest_initial_skill_listing_with_skillCount>=50",
                    "content_class": "prose",
                    "chars": chars,
                    "predicted_tokens": predicted,
                    "reference_tokens_approx": reference,
                    "difference_pct": 100.0 * (predicted - reference) / reference,
                    "skill_count": skill_candidate.get("skill_count"),
                    "timestamp": skill_candidate.get("timestamp"),
                    "transcript_path": skill_candidate.get("transcript_path"),
                    "line": skill_candidate.get("line"),
                    "selection": "largest_initial_listing_with_at_least_50_skills",
                }
            )
    return probes


def largest_skill_listing_probe(
    transcript: Transcript,
) -> dict[str, Any] | None:
    candidates: list[tuple[datetime, dict[str, Any]]] = []
    for row in transcript.rows:
        value = row.value
        if value.get("type") != "attachment":
            continue
        attachment = value.get("attachment")
        if not isinstance(attachment, Mapping):
            continue
        if (
            attachment.get("type") != "skill_listing"
            or attachment.get("isInitial") is not True
            or (integer(attachment.get("skillCount")) or 0) < 50
        ):
            continue
        timestamp = parse_timestamp(value.get("timestamp"))
        if timestamp is None:
            continue
        candidates.append(
            (
                timestamp,
                {
                    "timestamp_epoch": timestamp.timestamp(),
                    "timestamp": value.get("timestamp"),
                    "chars": textual_chars(attachment.get("content")),
                    "skill_count": integer(attachment.get("skillCount")),
                    "transcript_path": str(transcript.path),
                    "line": row.line_no,
                },
            )
        )
    return (
        max(candidates, key=lambda item: (item[1]["chars"], item[0]))[1]
        if candidates
        else None
    )


def cache_prefix_analysis(boundaries: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, str], list[int]] = collections.defaultdict(list)
    for row in boundaries:
        if row.get("measurement_state") != "measured":
            continue
        usage = row.get("usage")
        if not isinstance(usage, Mapping):
            continue
        cache_read = integer(usage.get("cache_read_input_tokens"))
        if not cache_read:
            continue
        key = (
            str(row.get("model") or "unknown"),
            str(row.get("claude_code_version") or "unknown"),
        )
        groups[key].append(cache_read)

    results = []
    reliable_groups = 0
    for (model, version), values in sorted(groups.items()):
        counts = collections.Counter(values)
        mode, mode_count = counts.most_common(1)[0]
        share = mode_count / len(values)
        reliable = len(values) >= 5 and share >= 0.80
        reliable_groups += int(reliable)
        results.append(
            {
                "model": model,
                "claude_code_version": version,
                "n": len(values),
                "modal_cache_read_tokens": mode,
                "modal_share": share,
                "unique_values": len(counts),
                "stable_prefix_reliable": reliable,
            }
        )
    return {
        "interpretation": (
            "cache_read is an exact transport component, but only model/version groups "
            "with >=5 boundaries and >=80% modal agreement are marked reliable as a "
            "stable-prefix diagnostic; it is never used as semantic attribution"
        ),
        "groups": results,
        "reliable_groups": reliable_groups,
        "total_groups": len(results),
    }


def _row_regime(row: Mapping[str, Any]) -> str:
    regime = row.get("config_regime")
    if isinstance(regime, Mapping):
        return str(regime.get("id") or "unknown")
    floor = row.get("session_floor")
    if isinstance(floor, Mapping):
        regime = floor.get("config_regime")
        if isinstance(regime, Mapping):
            return str(regime.get("id") or "unknown")
    return "unknown"


def summarize_boundaries(
    boundaries: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    measured = [row for row in boundaries if row.get("measurement_state") == "measured"]
    fill_tokens = [
        int(row["post_prompt_tokens"])
        for row in measured
        if integer(row.get("post_prompt_tokens")) is not None
    ]
    fill_pct = [
        float(row["fill_pct"])
        for row in measured
        if finite_number(row.get("fill_pct")) is not None
    ]
    window_groups: dict[str, list[float]] = collections.defaultdict(list)
    unknown_lower: list[float] = []
    unknown_upper: list[float] = []
    for row in measured:
        window = integer(row.get("context_window_tokens"))
        value = finite_number(row.get("fill_pct"))
        if window is not None and value is not None:
            window_groups[str(window)].append(value)
        elif isinstance(row.get("fill_pct_bounds_if_window_unknown"), Mapping):
            bounds = row["fill_pct_bounds_if_window_unknown"]
            lower = finite_number(bounds.get("if_1m"))
            upper = finite_number(bounds.get("if_200k"))
            if lower is not None and upper is not None:
                unknown_lower.append(lower)
                unknown_upper.append(upper)

    total_context = sum(fill_tokens)
    bucket_total: collections.Counter[str] = collections.Counter()
    bucket_values: dict[str, list[int]] = collections.defaultdict(list)
    bucket_methods: dict[str, collections.Counter[str]] = collections.defaultdict(
        collections.Counter
    )
    for row in measured:
        buckets = row.get("buckets")
        if not isinstance(buckets, Mapping):
            continue
        reconciliation = row.get("reconciliation")
        methods = (
            reconciliation.get("bucket_estimation_methods")
            if isinstance(reconciliation, Mapping)
            else None
        )
        for bucket, value in buckets.items():
            tokens = integer(value)
            if tokens is None:
                continue
            bucket_name = str(bucket)
            bucket_total[bucket_name] += tokens
            bucket_values[bucket_name].append(tokens)
            if isinstance(methods, Mapping) and bucket in methods:
                bucket_methods[bucket_name][str(methods[bucket])] += 1
    culprits = []
    for bucket, total in bucket_total.most_common():
        values = bucket_values[bucket]
        culprits.append(
            {
                "bucket": bucket,
                "estimation_method": (
                    "+".join(sorted(bucket_methods[bucket]))
                    if bucket_methods[bucket]
                    else "unknown"
                ),
                "median_tokens_when_present": median(values),
                "n": len(values),
                "boundary_coverage_pct": (
                    100.0 * len(values) / len(measured) if measured else None
                ),
                "total_tokens": total,
                "share_of_post_context_pct": (
                    100.0 * total / total_context if total_context else None
                ),
            }
        )

    refill_bucket_total: collections.Counter[str] = collections.Counter()
    refill_bucket_methods: dict[str, collections.Counter[str]] = (
        collections.defaultdict(collections.Counter)
    )
    refill_transitions = 0
    refill_net = 0
    refill_positive = 0
    for row in measured:
        refill = row.get("refill")
        if not isinstance(refill, Mapping):
            continue
        refill_transitions += integer(refill.get("transitions")) or 0
        refill_net += integer(refill.get("net_growth_tokens")) or 0
        refill_positive += integer(refill.get("positive_tokens_added")) or 0
        bucket_tokens = refill.get("bucket_tokens")
        methods = refill.get("bucket_estimation_methods")
        if isinstance(bucket_tokens, Mapping):
            for bucket, value in bucket_tokens.items():
                bucket_name = str(bucket)
                refill_bucket_total[bucket_name] += integer(value) or 0
                if isinstance(methods, Mapping) and bucket in methods:
                    refill_bucket_methods[bucket_name][str(methods[bucket])] += 1
    refill_culprits = [
        {
            "bucket": bucket,
            "estimation_method": (
                "+".join(sorted(refill_bucket_methods[bucket]))
                if refill_bucket_methods[bucket]
                else "unknown"
            ),
            "tokens_per_turn": (
                total / refill_transitions if refill_transitions else None
            ),
            "total_tokens": total,
            "share_of_positive_growth_pct": (
                100.0 * total / refill_positive if refill_positive else None
            ),
            "n": refill_transitions,
        }
        for bucket, total in refill_bucket_total.most_common()
    ]
    overflow = []
    class_overflow: collections.Counter[str] = collections.Counter()
    for row in measured:
        reconciliation = row.get("reconciliation")
        if not isinstance(reconciliation, Mapping):
            continue
        amount = finite_number(reconciliation.get("estimation_overflow_tokens")) or 0
        if amount > 0:
            overflow.append(amount)
        class_estimates = reconciliation.get("class_estimated_tokens")
        if not isinstance(class_estimates, Mapping):
            continue
        for class_name, estimate in class_estimates.items():
            if (
                finite_number(estimate) is not None
                and finite_number(row.get("post_prompt_tokens")) is not None
                and float(estimate) > float(row["post_prompt_tokens"])
            ):
                class_overflow[str(class_name)] += 1

    hook_sets: collections.Counter[str] = collections.Counter()
    for row in boundaries:
        fired = row.get("hooks_fired")
        if isinstance(fired, Mapping):
            hook_sets[str(fired.get("set_id") or "none-recorded")] += 1
    return {
        "n": len(measured),
        "boundaries_detected": len(boundaries),
        "boundaries_missing_authoritative_usage": len(boundaries) - len(measured),
        "boundaries_partial_legacy_unattributed": sum(
            row.get("attribution_state") == "partial_legacy_unattributed"
            for row in boundaries
        ),
        "fill_tokens": distribution(fill_tokens),
        "fill_pct": distribution(fill_pct),
        "unknown_context_window_n": len(unknown_lower),
        "unknown_window_fill_pct_bounds": {
            "if_all_1m": distribution(unknown_lower),
            "if_all_200k": distribution(unknown_upper),
        },
        "window_fill_pct": {
            window: distribution(values)
            for window, values in sorted(
                window_groups.items(), key=lambda item: int(item[0])
            )
        },
        "culprits": culprits,
        "refill": {
            "n": refill_transitions,
            "net_growth_tokens": refill_net,
            "net_tokens_per_turn": (
                refill_net / refill_transitions if refill_transitions else None
            ),
            "positive_tokens_added": refill_positive,
            "positive_tokens_added_per_turn": (
                refill_positive / refill_transitions if refill_transitions else None
            ),
            "culprits": refill_culprits,
        },
        "calibration_failures": {
            "n": len(overflow),
            "overflow_tokens": distribution(overflow),
            "class_estimate_exceeded_authoritative_total": dict(
                sorted(class_overflow.items())
            ),
            "downscaled_n": sum(
                bool((row.get("reconciliation") or {}).get("downscaled"))
                for row in measured
                if isinstance(row.get("reconciliation"), Mapping)
            ),
        },
        "hook_sets": [
            {"set_id": name, "n": count} for name, count in hook_sets.most_common()
        ],
    }


def _regime_metadata(
    boundaries: Sequence[Mapping[str, Any]],
    sessions: Sequence[Mapping[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in [*boundaries, *sessions]:
        regime = row.get("config_regime")
        if not isinstance(regime, Mapping):
            floor = row.get("session_floor")
            regime = floor.get("config_regime") if isinstance(floor, Mapping) else None
        if not isinstance(regime, Mapping):
            continue
        regime_id = str(regime.get("id") or "unknown")
        result[regime_id] = dict(regime)
    return result


def _floor_summary(
    sessions: Sequence[Mapping[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    by_regime: dict[str, list[int]] = collections.defaultdict(list)
    by_month: dict[str, list[int]] = collections.defaultdict(list)
    missing = 0
    for row in sessions:
        floor = row.get("session_floor")
        if not isinstance(floor, Mapping) or floor.get("state") != "measured":
            if (integer(row.get("boundaries_detected")) or 0) == 0:
                missing += 1
            continue
        tokens = integer(floor.get("tokens"))
        if tokens is None:
            continue
        regime = floor.get("config_regime")
        regime_id = (
            str(regime.get("id") or "unknown")
            if isinstance(regime, Mapping)
            else "unknown"
        )
        by_regime[regime_id].append(tokens)
        timestamp = parse_timestamp(floor.get("timestamp"))
        month = timestamp.strftime("%Y-%m") if timestamp else "unknown"
        by_month[month].append(tokens)
    return (
        {regime: distribution(values) for regime, values in sorted(by_regime.items())}
        | {"missing_first_usage_n": missing},
        {month: distribution(values) for month, values in sorted(by_month.items())},
    )


def _bucket_diff(
    current: Mapping[str, Any], baseline: Mapping[str, Any]
) -> list[dict[str, Any]]:
    current_map = {row["bucket"]: row for row in current.get("culprits", [])}
    baseline_map = {row["bucket"]: row for row in baseline.get("culprits", [])}
    names = set(current_map) | set(baseline_map)
    result = []
    for name in names:
        current_value = finite_number(
            current_map.get(name, {}).get("median_tokens_when_present")
        )
        baseline_value = finite_number(
            baseline_map.get(name, {}).get("median_tokens_when_present")
        )
        result.append(
            {
                "bucket": name,
                "current_median_tokens": current_value,
                "current_n": integer(current_map.get(name, {}).get("n")) or 0,
                "baseline_median_tokens": baseline_value,
                "baseline_n": integer(baseline_map.get(name, {}).get("n")) or 0,
                "delta_tokens": (
                    current_value - baseline_value
                    if current_value is not None and baseline_value is not None
                    else None
                ),
            }
        )
    return sorted(
        result,
        key=lambda row: abs(finite_number(row.get("delta_tokens")) or 0),
        reverse=True,
    )


def aggregate_report(
    rows: Sequence[Mapping[str, Any]],
    regime_selector: str = "current",
) -> dict[str, Any]:
    sessions = [row for row in rows if row.get("row_type") == "session"]
    boundaries = [row for row in rows if row.get("row_type") == "boundary"]
    metadata = _regime_metadata(boundaries, sessions)
    regime_ids = set(metadata) | {_row_regime(row) for row in boundaries}
    summaries = {
        regime: summarize_boundaries(
            [row for row in boundaries if _row_regime(row) == regime]
        )
        for regime in regime_ids
    }
    ordered = sorted(
        regime_ids,
        key=lambda regime: (
            parse_timestamp(metadata.get(regime, {}).get("timestamp"))
            or datetime.min.replace(tzinfo=timezone.utc)
        ),
    )
    current_id = next(
        (
            regime
            for regime in reversed(ordered)
            if metadata.get(regime, {}).get("is_current")
        ),
        ordered[-1] if ordered else "unknown",
    )
    selected_id = current_id if regime_selector == "current" else regime_selector
    if selected_id not in summaries:
        raise ValueError(
            f"unknown regime {regime_selector!r}; available: {', '.join(ordered)}"
        )
    prior_with_data = [
        regime
        for regime in ordered
        if regime != selected_id
        and summaries[regime]["n"] > 0
        and ordered.index(regime) < ordered.index(selected_id)
    ]
    baseline_id = prior_with_data[-1] if prior_with_data else None
    floor_by_regime, floor_trend = _floor_summary(sessions)
    corpus_boundary_summary = summarize_boundaries(boundaries)
    calibration = next(
        (
            row.get("calibration")
            for row in rows
            if isinstance(row.get("calibration"), Mapping)
            and row["calibration"].get("state") == "fitted"
        ),
        {},
    )
    return {
        "generated_at": utc_now(),
        "corpus": {
            "sessions_n": len(sessions),
            "sessions_with_compactions_n": sum(
                (integer(row.get("boundaries_detected")) or 0) > 0 for row in sessions
            ),
            "boundaries_detected_n": len(boundaries),
            "boundaries_measured_n": sum(
                row.get("measurement_state") == "measured" for row in boundaries
            ),
            "unknown_context_window_n": corpus_boundary_summary[
                "unknown_context_window_n"
            ],
            "calibration_failures": corpus_boundary_summary["calibration_failures"],
        },
        "selected_regime": {
            "id": selected_id,
            "metadata": metadata.get(selected_id, {}),
            "summary": summaries[selected_id],
        },
        "current_regime_id": current_id,
        "baseline_regimes": [
            {
                "id": regime,
                "metadata": metadata.get(regime, {}),
                "summary": summaries[regime],
            }
            for regime in reversed(ordered)
            if regime != selected_id
        ],
        "regime_diff": {
            "current_id": selected_id,
            "current_n": summaries[selected_id]["n"],
            "baseline_id": baseline_id,
            "baseline_n": summaries[baseline_id]["n"] if baseline_id else 0,
            "buckets": (
                _bucket_diff(summaries[selected_id], summaries[baseline_id])
                if baseline_id
                else []
            ),
        },
        "session_floor": {
            "by_regime": floor_by_regime,
            "monthly_trend": floor_trend,
            "operational_consequence": (
                "The first-turn floor is stable prompt overhead. Compaction adds its "
                "summary/preserved payload on top, so it cannot land a session below "
                "the floor."
            ),
            "current_vs_june": {
                "current_regime": floor_by_regime.get(current_id),
                "june": floor_trend.get("2026-06"),
            },
        },
        "calibration": calibration,
        "cache_prefix": cache_prefix_analysis(boundaries),
    }


def fmt_number(value: Any, digits: int = 0) -> str:
    number = finite_number(value)
    if number is None:
        return "n/a"
    if digits:
        return f"{number:,.{digits}f}"
    return f"{number:,.0f}"


def fmt_pct(value: Any) -> str:
    return f"{fmt_number(value, 1)}%"


def render_report(report: Mapping[str, Any]) -> str:
    selected = report["selected_regime"]
    summary = selected["summary"]
    fill = summary["fill_tokens"]
    fill_pct = summary["fill_pct"]
    refill = summary["refill"]
    calibration = report.get("calibration") or {}
    metadata = selected.get("metadata") or {}
    corpus = report.get("corpus") or {}
    lines = [
        "# Context Composition Ledger",
        "",
        (
            f"Corpus coverage: boundaries n={corpus.get('boundaries_measured_n', 0):,}/"
            f"{corpus.get('boundaries_detected_n', 0):,}; sessions "
            f"n={corpus.get('sessions_n', 0):,}. Primary view: config regime "
            f"`{selected['id']}` (n={summary['n']:,}), "
            f"{metadata.get('subject') or 'metadata unavailable'}."
        ),
        "",
        "## Current/selected regime: post-compaction fill",
        "",
        (
            f"Absolute fill n={fill['n']:,}: median {fmt_number(fill['median'])} tokens "
            f"(p10 {fmt_number(fill['p10'])}, p25 {fmt_number(fill['p25'])}, "
            f"p75 {fmt_number(fill['p75'])}, p90 {fmt_number(fill['p90'])}; "
            f"range {fmt_number(fill['min'])}–{fmt_number(fill['max'])})."
        ),
        (
            f"Window-normalized fill n={fill_pct['n']:,}: median "
            f"{fmt_pct(fill_pct['median'])} (p10 {fmt_pct(fill_pct['p10'])}, "
            f"p25 {fmt_pct(fill_pct['p25'])}, p75 {fmt_pct(fill_pct['p75'])}, "
            f"p90 {fmt_pct(fill_pct['p90'])}). Indeterminate windows are reported "
            "separately instead of silently dropped."
        ),
        (
            f"Indeterminate window n={summary.get('unknown_context_window_n', 0):,} "
            f"in this regime and n={corpus.get('unknown_context_window_n', 0):,} "
            "corpus-wide."
        ),
        "",
        "| context window | n | median fill | p25–p75 |",
        "|---:|---:|---:|---:|",
    ]
    for window, values in summary["window_fill_pct"].items():
        lines.append(
            f"| {int(window):,} | n={values['n']:,} | {fmt_pct(values['median'])} "
            f"| {fmt_pct(values['p25'])}–{fmt_pct(values['p75'])} |"
        )
    unknown_bounds = summary.get("unknown_window_fill_pct_bounds") or {}
    unknown_1m = unknown_bounds.get("if_all_1m") or {}
    unknown_200k = unknown_bounds.get("if_all_200k") or {}
    if unknown_1m.get("n"):
        lines.append(
            f"| unknown (bounded) | n={unknown_1m['n']:,} "
            f"| {fmt_pct(unknown_1m.get('median'))} if 1M / "
            f"{fmt_pct(unknown_200k.get('median'))} if 200k | n/a |"
        )
    lines.extend(
        [
            "",
            "## Ranked context consumers",
            "",
            "| bucket | attribution method | median tokens when present | n | share of post-compact context |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for culprit in summary["culprits"][:25]:
        lines.append(
            f"| {str(culprit['bucket']).replace('|', chr(92) + '|')} "
            f"| {culprit.get('estimation_method', 'unknown')} "
            f"| {fmt_number(culprit['median_tokens_when_present'])} "
            f"| n={culprit['n']:,} "
            f"| {fmt_pct(culprit['share_of_post_context_pct'])} |"
        )
    lines.extend(
        [
            "",
            "`system_and_tools` is authoritative total minus parsed calibrated "
            "estimates. It is a signed residual, not a measured system-prompt count.",
            "",
            "## Refill velocity",
            "",
            (
                f"Model-turn transitions n={refill['n']:,}: net "
                f"{fmt_number(refill['net_tokens_per_turn'], 1)} tokens/turn; positive "
                f"additions {fmt_number(refill['positive_tokens_added_per_turn'], 1)} "
                "tokens/turn."
            ),
            "",
            "| growth source | attribution method | estimated tokens/turn | n | share of positive growth |",
            "|---|---|---:|---:|---:|",
        ]
    )
    for culprit in refill["culprits"][:25]:
        lines.append(
            f"| {str(culprit['bucket']).replace('|', chr(92) + '|')} "
            f"| {culprit.get('estimation_method', 'unknown')} "
            f"| {fmt_number(culprit['tokens_per_turn'], 1)} "
            f"| n={culprit['n']:,} "
            f"| {fmt_pct(culprit['share_of_positive_growth_pct'])} |"
        )

    lines.extend(
        [
            "",
            "## Per-class calibration and independent probes",
            "",
            "| class | reliability | attribution ratio | chars/token | fit n | validation n | R² | median APE | estimate > partial target | class estimate > total |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for class_name, details in (calibration.get("classes") or {}).items():
        lines.append(
            f"| {class_name} | {details.get('reliability_state', 'unknown')} "
            f"| {details.get('attribution_ratio', 'unknown')} "
            f"| {fmt_number(details.get('chars_per_token'), 4)} "
            f"| n={fmt_number(details.get('samples_fit'))} "
            f"| n={fmt_number(details.get('n'))} "
            f"| {fmt_number(details.get('r2'), 3)} "
            f"| {fmt_pct(details.get('median_absolute_percentage_error_pct'))} "
            f"| n={fmt_number(details.get('estimates_exceeded_target'))} "
            f"| n={fmt_number(details.get('estimates_exceeded_authoritative_total'))} |"
        )
    pooled = calibration.get("pooled") or {}
    lines.append(
        f"\nPooled ratio used for unreliable classes: "
        f"{fmt_number(pooled.get('chars_per_token'), 4)} chars/token; "
        f"reliability `{pooled.get('reliability_state', 'unknown')}`; "
        f"held-out n={pooled.get('n', 0):,}, R² "
        f"{fmt_number(pooled.get('r2'), 3)}, median APE "
        f"{fmt_pct(pooled.get('median_absolute_percentage_error_pct'))}."
    )
    combined = calibration.get("combined_validation") or {}
    lines.append(
        f"\nCombined held-out postTokens fit: n={combined.get('n', 0):,}, "
        f"R² {fmt_number(combined.get('r2'), 3)}, median APE "
        f"{fmt_pct(combined.get('median_absolute_percentage_error_pct'))}, "
        f"estimates above target n={combined.get('estimates_exceeded_target', 0):,}."
    )
    anchor = (calibration.get("post_tokens_anchor") or {}).get(
        "raw_json_chars_per_token"
    ) or {}
    lines.append(
        f"Independent raw-JSON/postTokens check n={anchor.get('n', 0):,}: median "
        f"{fmt_number(anchor.get('median'), 3)} chars/token, IQR "
        f"{fmt_number(anchor.get('p25'), 3)}–{fmt_number(anchor.get('p75'), 3)}."
    )
    lines.extend(
        [
            "",
            "| independent probe | n | chars | predicted tokens | direct reference | difference |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for probe in calibration.get("anchor_probes") or []:
        lines.append(
            f"| {str(probe.get('name')).replace('|', chr(92) + '|')} "
            f"| n=1 "
            f"| {fmt_number(probe.get('chars'))} "
            f"| {fmt_number(probe.get('predicted_tokens'))} "
            f"| ~{fmt_number(probe.get('reference_tokens_approx'))} "
            f"| {fmt_pct(probe.get('difference_pct'))} |"
        )
    failures = summary.get("calibration_failures") or {}
    corpus_failures = corpus.get("calibration_failures") or {}
    lines.append(
        f"\nSelected-regime raw estimate overflow n={failures.get('n', 0):,}/"
        f"{summary['n']:,}; downscaled n={failures.get('downscaled_n', 0):,}. "
        f"Corpus-wide overflow n={corpus_failures.get('n', 0):,}/"
        f"{corpus.get('boundaries_measured_n', 0):,}; corpus-wide downscaled "
        f"n={corpus_failures.get('downscaled_n', 0):,}. Overflow is retained as a "
        "negative residual, never rescaled."
    )

    floor = report.get("session_floor") or {}
    floor_by_regime = floor.get("by_regime") or {}
    lines.extend(
        [
            "",
            "## Session floor",
            "",
            "| config regime | n | median first-turn prompt tokens | p25–p75 |",
            "|---|---:|---:|---:|",
        ]
    )
    for regime_id, values in floor_by_regime.items():
        if regime_id == "missing_first_usage_n":
            continue
        lines.append(
            f"| {regime_id} | n={values['n']:,} "
            f"| {fmt_number(values['median'])} "
            f"| {fmt_number(values['p25'])}–{fmt_number(values['p75'])} |"
        )
    lines.extend(
        [
            "",
            "| month | n | median first-turn prompt tokens |",
            "|---|---:|---:|",
        ]
    )
    for month, values in (floor.get("monthly_trend") or {}).items():
        lines.append(
            f"| {month} | n={values['n']:,} | {fmt_number(values['median'])} |"
        )
    floor_comparison = floor.get("current_vs_june") or {}
    current_floor = floor_comparison.get("current_regime") or {}
    june_floor = floor_comparison.get("june") or {}
    if current_floor.get("n") and june_floor.get("n"):
        change = (
            100.0
            * (float(current_floor["median"]) - float(june_floor["median"]))
            / float(june_floor["median"])
        )
        lines.append(
            f"\nCurrent regime floor n={current_floor['n']:,}, median "
            f"{fmt_number(current_floor['median'])}; June n={june_floor['n']:,}, "
            f"median {fmt_number(june_floor['median'])}: {fmt_pct(change)}."
        )
    lines.append(
        "\nOperational consequence: the first-turn floor is stable prompt overhead. "
        "Compaction adds the compacted payload on top, so it cannot land below the "
        f"floor; the selected-regime landing n={fill['n']:,}, median "
        f"{fmt_number(fill['median'])} tokens would occupy "
        f"{fmt_pct(100.0 * float(fill['median']) / BASE_CONTEXT_WINDOW if fill['median'] is not None else None)} "
        "of a 200k window rather than returning it near empty."
    )

    lines.extend(
        [
            "",
            "## Earlier regimes (separate baselines; never blended)",
            "",
            "| regime | n | median tokens | 200k fill (n) | 1M fill (n) | unknown n |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for baseline in report.get("baseline_regimes") or []:
        baseline_summary = baseline["summary"]
        base_200 = baseline_summary["window_fill_pct"].get("200000") or {}
        base_1m = baseline_summary["window_fill_pct"].get("1000000") or {}
        lines.append(
            f"| {baseline['id']} | n={baseline_summary['n']:,} "
            f"| {fmt_number(baseline_summary['fill_tokens']['median'])} "
            f"| {fmt_pct(base_200.get('median'))} (n={base_200.get('n', 0):,}) "
            f"| {fmt_pct(base_1m.get('median'))} (n={base_1m.get('n', 0):,}) "
            f"| n={baseline_summary.get('unknown_context_window_n', 0):,} |"
        )

    diff = report.get("regime_diff") or {}
    lines.extend(
        [
            "",
            (
                f"## Regime diff: {diff.get('current_id')} "
                f"(n={diff.get('current_n', 0):,}) versus "
                f"{diff.get('baseline_id') or 'none'} "
                f"(n={diff.get('baseline_n', 0):,})"
            ),
            "",
            "| bucket | current median (n) | baseline median (n) | delta |",
            "|---|---:|---:|---:|",
        ]
    )
    for item in (diff.get("buckets") or [])[:25]:
        lines.append(
            f"| {str(item['bucket']).replace('|', chr(92) + '|')} "
            f"| {fmt_number(item.get('current_median_tokens'))} "
            f"(n={item.get('current_n', 0):,}) "
            f"| {fmt_number(item.get('baseline_median_tokens'))} "
            f"(n={item.get('baseline_n', 0):,}) "
            f"| {fmt_number(item.get('delta_tokens'))} |"
        )

    lines.extend(["", "Actual hook sets recorded for the selected regime:", ""])
    for hook_set in summary.get("hook_sets") or []:
        lines.append(f"- n={hook_set['n']:,}: `{hook_set['set_id']}`")
    cache = report.get("cache_prefix") or {}
    lines.append(
        f"\nCache-read stable-prefix diagnostic: n={cache.get('reliable_groups', 0)}/"
        f"{cache.get('total_groups', 0)} model/version groups met the predeclared "
        ">=5 samples and >=80% modal-agreement rule. Cache-read is retained as an exact "
        "usage component but is not treated as semantic attribution."
    )
    return "\n".join(lines).rstrip() + "\n"


def resolve_session(value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_file():
        return path.resolve()
    matches = sorted(TRANSCRIPT_ROOT.glob(f"*/*{value}*.jsonl"))
    if not matches:
        raise FileNotFoundError(f"no transcript matched {value!r}")
    exact = [match for match in matches if match.stem == value]
    if exact:
        matches = exact
    if len(matches) != 1:
        raise ValueError(
            f"{value!r} matched {len(matches)} transcripts; pass an exact UUID or path"
        )
    return matches[0]


def backfill(
    ledger_path: Path = LEDGER_PATH,
    events_path: Path = EVENTS_PATH,
) -> tuple[list[dict[str, Any]], int]:
    paths = transcript_paths()
    samples: list[CalibrationSample] = []
    skill_candidate: dict[str, Any] | None = None
    sys.stderr.write(f"[calibration] scanning {len(paths)} transcripts\n")
    for number, path in enumerate(paths, 1):
        try:
            transcript = read_transcript(path)
            samples.extend(calibration_samples(transcript))
            candidate = largest_skill_listing_probe(transcript)
            if candidate and (
                skill_candidate is None
                or (
                    int(candidate["chars"]),
                    float(candidate["timestamp_epoch"]),
                )
                > (
                    int(skill_candidate["chars"]),
                    float(skill_candidate["timestamp_epoch"]),
                )
            ):
                skill_candidate = candidate
        except OSError as exc:
            sys.stderr.write(f"[skip calibration] {path}: {exc}\n")
        if number % 200 == 0:
            sys.stderr.write(f"  {number}/{len(paths)} calibration scan\n")
    calibration = fit_calibration(samples)
    calibration["anchor_probes"] = calibration_anchor_probes(
        skill_candidate, calibration
    )
    for class_name, details in (calibration.get("classes") or {}).items():
        sys.stderr.write(
            f"[calibration:{class_name}] chars/token={details.get('chars_per_token')} "
            f"fit_n={details.get('samples_fit')} validation_n={details.get('n')} "
            f"R2={details.get('r2')} "
            f"median_APE={details.get('median_absolute_percentage_error_pct')}% "
            f"over_total={details.get('estimates_exceeded_authoritative_total')}\n"
        )
    combined = calibration.get("combined_validation") or {}
    sys.stderr.write(
        f"[calibration:combined] validation_n={combined.get('n')} "
        f"R2={combined.get('r2')} "
        f"median_APE={combined.get('median_absolute_percentage_error_pct')}% "
        f"over={combined.get('estimates_exceeded_target')}\n"
    )
    regime_history = load_regime_history()
    if regime_history:
        sys.stderr.write(
            f"[regime] {len(regime_history)} git-derived regimes; "
            f"current={regime_history[-1]['id']} {regime_history[-1]['timestamp']}\n"
        )

    boundary_rows: list[dict[str, Any]] = []
    session_rows: list[dict[str, Any]] = []
    for number, path in enumerate(paths, 1):
        try:
            transcript = read_transcript(path)
            boundaries, session = analyze_transcript(
                transcript, calibration, regime_history
            )
        except (OSError, ValueError, TypeError) as exc:
            sys.stderr.write(f"[skip analysis] {path}: {exc}\n")
            continue
        boundary_rows.extend(boundaries)
        session_rows.append(session)
        if number % 200 == 0:
            sys.stderr.write(f"  {number}/{len(paths)} analyzed\n")

    rows = boundary_rows + session_rows
    rows.sort(
        key=lambda row: (
            str(row.get("sid") or ""),
            0 if row.get("row_type") == "boundary" else 1,
            integer(row.get("boundary_number")) or 0,
        )
    )
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOCK_PATH.open("a+") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        atomic_write_jsonl(ledger_path, rows)
        appended = append_missing_events(rows, events_path)
    sys.stderr.write(
        f"[done] {len(boundary_rows)} boundary + {len(session_rows)} session rows "
        f"-> {ledger_path}; {appended} new unified events\n"
    )
    return rows, appended


def analyze_one(path: Path) -> list[dict[str, Any]]:
    transcript = read_transcript(path)
    own = fit_calibration(calibration_samples(transcript))
    if own.get("samples_fit", 0) < 10:
        existing = fallback_calibration()
        if existing:
            own = existing
    boundaries, session = analyze_transcript(transcript, own, load_regime_history())
    return boundaries + [session]


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    modes = result.add_mutually_exclusive_group(required=True)
    modes.add_argument(
        "--backfill", action="store_true", help="analyze the full corpus"
    )
    modes.add_argument(
        "--session", metavar="UUID_OR_PATH", help="analyze one transcript to stdout"
    )
    modes.add_argument(
        "--report", action="store_true", help="report collected ledger rows"
    )
    result.add_argument("--json", action="store_true", help="structured report output")
    result.add_argument(
        "--regime",
        default="current",
        metavar="CURRENT_OR_COMMIT",
        help="report a git-derived config regime (default: current)",
    )
    result.add_argument(
        "--regime-diff",
        action="store_true",
        help="include the selected-versus-immediately-prior bucket view (also in text report)",
    )
    return result


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.backfill:
        rows, _ = backfill()
        report = aggregate_report(rows, args.regime)
        print(
            json.dumps(report, indent=2, sort_keys=True)
            if args.json
            else render_report(report),
            end="" if not args.json else "\n",
        )
        return 0
    if args.session:
        try:
            path = resolve_session(args.session)
            rows = analyze_one(path)
        except (OSError, ValueError) as exc:
            print(f"context_ledger.py: {exc}", file=sys.stderr)
            return 1
        for row in rows:
            print(json.dumps(row, ensure_ascii=False, sort_keys=True))
        return 0

    rows, malformed = load_ledger()
    if not rows:
        print(
            f"context_ledger.py: no ledger rows at {LEDGER_PATH}; run --backfill first",
            file=sys.stderr,
        )
        return 1
    try:
        report = aggregate_report(rows, args.regime)
    except ValueError as exc:
        print(f"context_ledger.py: {exc}", file=sys.stderr)
        return 1
    if malformed:
        report["malformed_ledger_rows_skipped"] = malformed
    print(
        json.dumps(report, indent=2, sort_keys=True)
        if args.json
        else render_report(report),
        end="" if not args.json else "\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
