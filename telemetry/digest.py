#!/usr/bin/env python3
"""Render a public-stream-backed digest over strata's unified telemetry."""

from __future__ import annotations

import argparse
import collections
import json
import math
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from typing import Any


# Runtime path contract (matches telemetry/unify.py and the emitters).
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
STRATA_HOME = os.environ.get("STRATA_HOME") or os.path.dirname(_SCRIPT_DIR)
KB_DIR = os.environ.get("KB_DIR") or f"{STRATA_HOME}/workspace"
STATE_DIR = os.environ.get("STATE_DIR") or f"{KB_DIR}/state"
TEL_DIR = os.environ.get("STRATA_TELEMETRY_DIR") or f"{STATE_DIR}/telemetry"

THIS_DIR = Path(_SCRIPT_DIR)
UNIFY = THIS_DIR / "unify.py"


def sid8(value: Any) -> str:
    """Join full and shortened session identifiers on their shared prefix."""
    if value is None:
        return ""
    text = str(value).strip()
    return text[:8] if text else ""


def skill_key(value: Any) -> str:
    """Normalize a public skill-run name."""
    if not isinstance(value, str):
        return ""
    text = value.strip().lower()
    if text.startswith("/"):
        text = text[1:]
    text = os.path.basename(text)
    if text.endswith(".md"):
        text = text[:-3]
    return text


def parse_ts(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        dt = datetime.fromisoformat(text)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        try:
            dt = dt.astimezone(timezone.utc)
        except (OSError, ValueError):
            return None
    return dt.astimezone(timezone.utc)


def fmt_int(value: int | float | None) -> str:
    if value is None:
        return "0"
    return f"{int(value):,}"


def fmt_pct(num: int | float, den: int | float) -> str:
    if not den:
        return "n/a"
    return f"{(100.0 * num / den):.1f}%"


def fmt_float(value: float | None, digits: int = 3) -> str:
    if value is None or not math.isfinite(value):
        return "n/a"
    return f"{value:.{digits}f}"


def fmt_dt(dt: datetime | None) -> str:
    if dt is None:
        return "unknown"
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def fmt_age(dt: datetime | None) -> str:
    if dt is None:
        return "unknown"
    seconds = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds())
    if seconds < 120:
        return f"{int(seconds)}s ago"
    if seconds < 7200:
        return f"{seconds / 60.0:.1f}m ago"
    if seconds < 172800:
        return f"{seconds / 3600.0:.1f}h ago"
    return f"{seconds / 86400.0:.1f}d ago"


def md_escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def to_float(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        out = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(out):
        return None
    return out


def load_events(since_days: int | None) -> tuple[list[dict[str, Any]], list[str]]:
    """Read the one public event surface by invoking telemetry/unify.py."""
    notes: list[str] = []
    if not UNIFY.exists():
        return [], [f"missing normalizer: {UNIFY}"]

    try:
        proc = subprocess.run(
            [sys.executable, str(UNIFY)],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=60,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return [], [f"could not run {UNIFY}: {exc.__class__.__name__}: {exc}"]

    if proc.returncode != 0:
        notes.append(
            f"unify.py exited {proc.returncode}; parsed whatever it wrote to stdout"
        )
    if proc.stderr.strip():
        notes.append(f"unify.py stderr: {proc.stderr.strip()}")

    cutoff: datetime | None = None
    if since_days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=since_days)

    events: list[dict[str, Any]] = []
    bad_lines = 0
    dropped_for_since = 0
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            bad_lines += 1
            continue
        if not isinstance(event, dict):
            bad_lines += 1
            continue
        if cutoff is not None:
            ts = parse_ts(event.get("ts"))
            if ts is None or ts < cutoff:
                dropped_for_since += 1
                continue
        events.append(event)

    if bad_lines:
        notes.append(f"skipped {bad_lines} unparseable unified JSONL lines")
    if dropped_for_since:
        notes.append(
            f"--since dropped {dropped_for_since} events outside the window "
            "or without parseable timestamps"
        )
    return events, notes


def analyze_header(
    events: list[dict[str, Any]], notes: list[str], since_days: int | None
) -> dict[str, Any]:
    timestamps = [parse_ts(event.get("ts")) for event in events]
    timestamps = [ts for ts in timestamps if ts is not None]
    kind_counts = collections.Counter(
        str(event.get("kind") or "unknown") for event in events
    )
    source_counts = collections.Counter(
        str(event.get("source") or "unknown") for event in events
    )
    sessions = {sid8(event.get("sid")) for event in events if sid8(event.get("sid"))}
    return {
        "total_events": len(events),
        "date_start": min(timestamps).isoformat() if timestamps else None,
        "date_end": max(timestamps).isoformat() if timestamps else None,
        "sessions_sid8": len(sessions),
        "kind_counts": dict(kind_counts.most_common()),
        "source_counts": dict(source_counts.most_common()),
        "since_days": since_days,
        "notes": notes,
    }


def retry_storms(tool_fails: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_sid: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for event in tool_fails:
        ts = parse_ts(event.get("ts"))
        if ts is None:
            continue
        by_sid[sid8(event.get("sid"))].append({"event": event, "ts": ts})

    storms: list[dict[str, Any]] = []
    window = timedelta(minutes=5)
    for session, rows in by_sid.items():
        rows.sort(key=lambda row: row["ts"])
        left = 0
        for right, row in enumerate(rows):
            while row["ts"] - rows[left]["ts"] > window:
                left += 1
            count = right - left + 1
            if count >= 3:
                storms.append(
                    {
                        "sid8": session,
                        "count": count,
                        "window_seconds": int(window.total_seconds()),
                        "start": rows[left]["ts"].isoformat(),
                        "end": row["ts"].isoformat(),
                    }
                )
    storms.sort(key=lambda row: (-row["count"], row["sid8"], row["start"]))
    return storms[:8]


def analyze_friction(events: list[dict[str, Any]]) -> dict[str, Any]:
    hook_blocks = [event for event in events if event.get("kind") == "hook_block"]
    hook_counts = collections.Counter(
        (
            str(event.get("hook") or "unknown"),
            str(event.get("reason") or "unknown"),
        )
        for event in hook_blocks
    )
    top_hook_blocks = [
        {"hook": hook, "reason": reason, "count": count}
        for (hook, reason), count in hook_counts.most_common(8)
    ]

    tool_fails = [event for event in events if event.get("kind") == "tool_fail"]
    fail_counts = collections.Counter(
        (
            str(event.get("tool") or event.get("hook") or "unknown"),
            str(
                event.get("reason")
                or event.get("error")
                or event.get("cmd")
                or "unknown"
            ),
        )
        for event in tool_fails
    )
    top_tool_fails = [
        {"tool": tool, "reason": reason, "count": count}
        for (tool, reason), count in fail_counts.most_common(8)
    ]

    notes: list[str] = []
    if not hook_blocks:
        notes.append("no hook_block data yet")
    if tool_fails and all(
        not any(event.get(field) for field in ("tool", "reason", "error", "cmd"))
        for event in tool_fails
    ):
        notes.append(
            "tool_fail events exist, but records do not expose tool or failure detail"
        )
    if not tool_fails:
        notes.append("no tool_fail data yet")

    storms = retry_storms(tool_fails)
    if not storms:
        notes.append(
            "no retry-storm proxy hit: threshold is at least 3 tool_fail events "
            "in 5 minutes for one sid8"
        )

    return {
        "hook_block_count": len(hook_blocks),
        "top_hook_blocks": top_hook_blocks,
        "tool_fail_count": len(tool_fails),
        "top_tool_fails": top_tool_fails,
        "retry_storms": storms,
        "notes": notes,
    }


def analyze_delegation(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Summarize the public lane/exit/dur_s delegation envelope."""
    delegations = [event for event in events if event.get("kind") == "delegation"]
    by_lane: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for event in delegations:
        by_lane[str(event.get("lane") or "unknown")].append(event)

    lanes: list[dict[str, Any]] = []
    for lane, rows in sorted(by_lane.items()):
        exit_counts = collections.Counter(
            "unknown"
            if to_float(row.get("exit")) is None
            else str(int(to_float(row.get("exit")) or 0))
            for row in rows
        )
        successes = exit_counts.get("0", 0)
        durations = [to_float(row.get("dur_s")) for row in rows]
        durations = [duration for duration in durations if duration is not None]
        lanes.append(
            {
                "lane": lane,
                "count": len(rows),
                "success": successes,
                "success_rate": successes / len(rows) if rows else None,
                "median_duration_s": median(durations) if durations else None,
                "exit_counts": dict(exit_counts.most_common()),
            }
        )

    return {
        "delegation_count": len(delegations),
        "lanes": lanes,
        "notes": [] if delegations else ["no delegation data yet"],
    }


def analyze_serial_wait(events: list[dict[str, Any]]) -> dict[str, Any]:
    """Diagnose sequential delegation from public completion times and durations."""
    eps = timedelta(seconds=1)
    by_sid: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    total_delegations = 0
    for event in events:
        if event.get("kind") != "delegation":
            continue
        total_delegations += 1
        sid = event.get("sid")
        if not sid or sid == "unknown":
            continue
        end = parse_ts(event.get("ts"))
        duration_s = to_float(event.get("dur_s"))
        if end is None or duration_s is None or duration_s < 0:
            continue
        duration_ms = duration_s * 1000.0
        by_sid[str(sid)].append(
            {
                "start": end - timedelta(seconds=duration_s),
                "end": end,
                "dur_ms": duration_ms,
                "lane": str(event.get("lane") or "?"),
            }
        )

    sessions: list[dict[str, Any]] = []
    aggregate_duration_ms = 0.0
    aggregate_busy_ms = 0.0
    attributed = 0
    for sid, dispatches in by_sid.items():
        dispatches.sort(key=lambda dispatch: dispatch["start"])
        count = len(dispatches)
        duration_ms = sum(dispatch["dur_ms"] for dispatch in dispatches)

        busy_ms = 0.0
        current_start = dispatches[0]["start"]
        current_end = dispatches[0]["end"]
        for dispatch in dispatches[1:]:
            if dispatch["start"] < current_end:
                current_end = max(current_end, dispatch["end"])
            else:
                busy_ms += (current_end - current_start).total_seconds() * 1000.0
                current_start = dispatch["start"]
                current_end = dispatch["end"]
        busy_ms += (current_end - current_start).total_seconds() * 1000.0

        longest = 0
        run = 0
        max_end: datetime | None = None
        for dispatch in dispatches:
            if max_end is None or dispatch["start"] >= max_end - eps:
                run += 1
            else:
                run = 1
            longest = max(longest, run)
            max_end = (
                dispatch["end"] if max_end is None else max(max_end, dispatch["end"])
            )

        parallelism = duration_ms / busy_ms if busy_ms > 0 else 1.0
        lanes = collections.Counter(dispatch["lane"] for dispatch in dispatches)
        sessions.append(
            {
                "sid8": sid8(sid),
                "n": count,
                "sum_ms": duration_ms,
                "busy_ms": busy_ms,
                "parallelism": parallelism,
                "longest_serial_run": longest,
                "lanes": dict(lanes.most_common()),
            }
        )
        attributed += count
        aggregate_duration_ms += duration_ms
        aggregate_busy_ms += busy_ms

    if not sessions:
        return {
            "available": False,
            "delegations_total": total_delegations,
            "delegations_attributed": 0,
            "notes": [
                "no delegation events carry a known sid, parseable timestamp, "
                f"and non-negative dur_s ({total_delegations} total)"
            ],
        }

    flagged = sorted(
        sessions,
        key=lambda session: (
            session["longest_serial_run"],
            session["sum_ms"],
        ),
        reverse=True,
    )[:10]
    return {
        "available": True,
        "delegations_total": total_delegations,
        "delegations_attributed": attributed,
        "sessions_with_delegation": len(sessions),
        "outsourced_hours_total": round(aggregate_duration_ms / 3.6e6, 2),
        "wall_busy_hours_total": round(aggregate_busy_ms / 3.6e6, 2),
        "overall_parallelism": round(aggregate_duration_ms / aggregate_busy_ms, 2)
        if aggregate_busy_ms > 0
        else 1.0,
        "serial_sessions": flagged,
        "notes": [
            "diagnostic only: parallelism 1.0 means fully serial; values above 1 "
            "show concurrent fan-out",
            "longest_serial_run counts dispatches that begin only after all earlier "
            "dispatches have ended",
        ],
    }


def safe_section(
    name: str, func: Any, fallback: dict[str, Any] | None = None
) -> dict[str, Any]:
    try:
        return func()
    except Exception as exc:
        out = dict(fallback or {})
        notes = out.setdefault("notes", [])
        notes.append(f"{name} failed: {exc.__class__.__name__}: {exc}")
        out["available"] = False
        return out


def build_top_signals(report: dict[str, Any]) -> list[str]:
    signals: list[str] = []

    serial = report.get("serial_wait", {})
    if serial.get("available"):
        worst = (serial.get("serial_sessions") or [{}])[0]
        if (worst.get("longest_serial_run") or 0) >= 3:
            signals.append(
                "Serial-wait: overall delegation parallelism "
                f"{serial.get('overall_parallelism')}x; worst session ran "
                f"{worst.get('longest_serial_run')} dispatches back-to-back."
            )

    friction = report.get("friction", {})
    if friction.get("tool_fail_count") or friction.get("hook_block_count"):
        signals.append(
            f"Friction: {fmt_int(friction.get('tool_fail_count', 0))} tool failures "
            f"and {fmt_int(friction.get('hook_block_count', 0))} hook blocks."
        )

    delegation = report.get("delegation", {})
    if not delegation.get("delegation_count"):
        signals.append("No delegation events are present in the selected window.")
    return signals[:5]


def build_report(since_days: int | None) -> dict[str, Any]:
    events, load_notes = load_events(since_days)
    generated_at = datetime.now(timezone.utc).isoformat()

    header = safe_section(
        "header", lambda: analyze_header(events, load_notes, since_days)
    )

    report = {
        "generated_at": generated_at,
        "unify": str(UNIFY),
        "window": {"since_days": since_days},
        "header": header,
        "delegation": safe_section("delegation", lambda: analyze_delegation(events)),
        "friction": safe_section("friction", lambda: analyze_friction(events)),
        "serial_wait": safe_section("serial wait", lambda: analyze_serial_wait(events)),
    }
    report["top_signals"] = build_top_signals(report)
    return report


def table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    if not rows:
        return []
    lines = [
        "| " + " | ".join(md_escape(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(md_escape(cell) for cell in row) + " |")
    return lines


def render_header(report: dict[str, Any]) -> list[str]:
    header = report["header"]
    lines = ["## 1. Unified Stream"]
    lines.append(f"- Total events: {fmt_int(header.get('total_events'))}")
    lines.append(
        f"- Date span: {fmt_dt(parse_ts(header.get('date_start')))} to "
        f"{fmt_dt(parse_ts(header.get('date_end')))}"
    )
    lines.append(f"- Sessions: {fmt_int(header.get('sessions_sid8'))} sid8 prefixes")
    if header.get("since_days") is not None:
        lines.append(f"- Window: last {header.get('since_days')} days")
    else:
        lines.append("- Window: all unified data")
    if header.get("notes"):
        lines.append("- Notes: " + "; ".join(str(note) for note in header["notes"]))

    kind_rows = [
        [kind, fmt_int(count)]
        for kind, count in (header.get("kind_counts") or {}).items()
    ]
    lines.append("")
    lines.append("### Per-kind tally")
    lines.extend(table(["kind", "count"], kind_rows) or ["No events found."])
    return lines


def render_delegation(report: dict[str, Any]) -> list[str]:
    section = report["delegation"]
    lines = ["## 2. Delegation Summary"]
    if not section.get("delegation_count"):
        lines.append("No delegation data yet.")
    else:
        rows = []
        for row in section.get("lanes") or []:
            exits = ", ".join(
                f"{key}={value}" for key, value in row.get("exit_counts", {}).items()
            )
            rows.append(
                [
                    row["lane"],
                    fmt_int(row["count"]),
                    fmt_pct(row.get("success", 0), row.get("count", 0)),
                    fmt_float(row.get("median_duration_s"), 1),
                    exits,
                ]
            )
        lines.extend(
            table(["lane", "count", "success-rate", "median s", "exits"], rows)
        )
    if section.get("notes"):
        lines.append("")
        lines.append("Notes: " + "; ".join(str(note) for note in section["notes"]))
    return lines


def render_friction(report: dict[str, Any]) -> list[str]:
    section = report["friction"]
    lines = ["## 3. Friction and Rework"]
    lines.append(f"- hook_block events: {fmt_int(section.get('hook_block_count', 0))}")
    if section.get("top_hook_blocks"):
        rows = [
            [row["hook"], row["reason"], fmt_int(row["count"])]
            for row in section["top_hook_blocks"]
        ]
        lines.extend(table(["hook", "reason", "count"], rows))
    else:
        lines.append("- Top hook blocks: no data yet")

    lines.append(f"- tool_fail events: {fmt_int(section.get('tool_fail_count', 0))}")
    if section.get("top_tool_fails"):
        rows = [
            [row["tool"], row["reason"], fmt_int(row["count"])]
            for row in section["top_tool_fails"]
        ]
        lines.extend(table(["tool", "reason/cmd", "count"], rows))
    else:
        lines.append("- Top tool failures: no data yet")

    if section.get("retry_storms"):
        rows = [
            [row["sid8"], fmt_int(row["count"]), row["start"], row["end"]]
            for row in section["retry_storms"]
        ]
        lines.append("- Retry-storm proxy hits:")
        lines.extend(table(["sid8", "count", "start", "end"], rows))
    else:
        lines.append("- Retry-storm proxy hits: none")

    if section.get("notes"):
        lines.append("")
        lines.append("Notes: " + "; ".join(str(note) for note in section["notes"]))
    return lines


def render_serial_wait(report: dict[str, Any]) -> list[str]:
    section = report.get("serial_wait") or {}
    lines = ["## 4. Serial-Wait Diagnostic"]
    if not section.get("available"):
        lines.append("- Unavailable: " + "; ".join(section.get("notes", ["no data"])))
        return lines

    lines.append(
        f"- {section.get('sessions_with_delegation', 0)} sessions with attributed "
        f"delegations ({fmt_int(section.get('delegations_attributed'))}/"
        f"{fmt_int(section.get('delegations_total'))} events); "
        f"{section.get('outsourced_hours_total')}h lane compute over "
        f"{section.get('wall_busy_hours_total')}h wall-clock; overall parallelism "
        f"{section.get('overall_parallelism')}x."
    )
    rows = [
        [
            session["sid8"],
            fmt_int(session["n"]),
            fmt_int(session["longest_serial_run"]),
            f"{session['sum_ms'] / 60000.0:.1f}",
            f"{session['busy_ms'] / 60000.0:.1f}",
            f"{session['parallelism']:.2f}x",
            ", ".join(
                f"{key}={value}" for key, value in (session.get("lanes") or {}).items()
            ),
        ]
        for session in section.get("serial_sessions", [])
    ]
    if rows:
        lines.append("")
        lines.append("### Most-serial sessions")
        lines.extend(
            table(
                [
                    "sid",
                    "n",
                    "longest run",
                    "dispatch min",
                    "wall min",
                    "parallelism",
                    "lanes",
                ],
                rows,
            )
        )
    for note in section.get("notes", []):
        lines.append(f"- {note}")
    return lines


def render_markdown(report: dict[str, Any]) -> str:
    lines = ["# Public Telemetry Digest"]
    lines.append(f"Generated: {fmt_dt(parse_ts(report.get('generated_at')))}")
    lines.append("")
    lines.append("## Top Signals")
    top = report.get("top_signals") or []
    if top:
        lines.extend(f"- {signal}" for signal in top)
    else:
        lines.append(
            "- No high-signal findings yet; the unified stream is empty or unavailable."
        )

    renderers = [
        render_header,
        render_delegation,
        render_friction,
        render_serial_wait,
    ]
    for renderer in renderers:
        lines.append("")
        lines.extend(renderer(report))
    return "\n".join(lines).rstrip() + "\n"


def _has_git_metadata_ancestor(path: str) -> bool:
    current = os.path.realpath(path)
    while True:
        marker = os.path.join(current, ".git")
        try:
            if os.path.isfile(marker):
                return True
            if os.path.isdir(marker):
                entries = set(os.listdir(marker))
                if "HEAD" in entries or "commondir" in entries:
                    return True
        except OSError:
            return True
        parent = os.path.dirname(current)
        if parent == current:
            return False
        current = parent


def out_path_is_safe(path: str) -> bool:
    """Refuse a tracked digest destination and fail closed inside git metadata."""
    raw = os.path.expanduser(path)
    if os.path.islink(raw):
        return False
    target = os.path.realpath(raw)
    parent = os.path.dirname(target) or "."
    if not os.path.isdir(parent):
        return False
    git_env = os.environ.copy()
    for key in (
        "GIT_CEILING_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_DIR",
        "GIT_INDEX_FILE",
        "GIT_WORK_TREE",
    ):
        git_env.pop(key, None)
    try:
        top = subprocess.run(
            ["git", "-C", parent, "rev-parse", "--show-toplevel"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
            env=git_env,
        )
    except Exception:
        return not _has_git_metadata_ancestor(parent)
    if top.returncode != 0:
        return not _has_git_metadata_ancestor(parent)
    toplevel = top.stdout.strip()
    if not toplevel:
        return False
    rel_target = os.path.relpath(target, os.path.realpath(toplevel))
    if rel_target == ".." or rel_target.startswith(f"..{os.sep}"):
        return False
    try:
        check = subprocess.run(
            ["git", "-C", toplevel, "check-ignore", "-q", "--", rel_target],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
            env=git_env,
        )
    except Exception:
        return False
    return check.returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json", action="store_true", help="emit structured findings as JSON"
    )
    parser.add_argument("--out", help="write the digest to PATH instead of stdout")
    parser.add_argument(
        "--since",
        type=int,
        metavar="DAYS",
        help="only include events from the last DAYS",
    )
    args = parser.parse_args(argv)

    if args.since is not None and args.since < 0:
        parser.error("--since must be non-negative")

    if args.out and not out_path_is_safe(args.out):
        print(
            f"digest.py: refusing --out {args.out}: it is inside a git work tree "
            "and not gitignored, and the digest can contain raw query text. "
            "Emitting to stdout instead.",
            file=sys.stderr,
        )
        args.out = None

    report = build_report(args.since)
    if args.json:
        output = json.dumps(report, indent=2, sort_keys=True) + "\n"
    else:
        output = render_markdown(report)

    if args.out:
        try:
            Path(args.out).write_text(output, encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            print(f"digest.py: could not write {args.out}: {exc}", file=sys.stderr)
            print(output, end="")
            return 1
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
