#!/usr/bin/env python3
"""Probe machine-visible facts and preserve everything else as unknown."""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import stat
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from schema_tools import validate_instance

try:
    import tomllib
except ImportError:  # pragma: no cover - Python older than 3.11
    tomllib = None


UNKNOWN_QUESTIONS = {
    "reader_models": "Which models read these instructions now, and what relevant capabilities have you measured on representative tasks?",
    "runtime_capabilities": "Which tools and harness features are present in the running agent? Declare only capabilities visible in its presented tool surface.",
    "memory_system": "Which memory or state system is authoritative now, and how can the auditor verify it?",
    "retired_systems": "Which tools, routers, stores, paths, and workflow conventions were retired, and on what dates?",
    "delegation_contract": "Which delegation paths are supported today, and which limits or failure modes are verified?",
    "prompting_standard": "Which current prompting standard governs these files, and where is it documented?",
    "house_standards": "Which local rules are intentional current preferences rather than stale assumptions?",
    "known_incidents": "Which warnings or workarounds came from real incidents and still protect a live failure mode?",
}
ANSWER_STATUSES = {"declared", "unknown", "not_applicable"}
EVIDENCE_KINDS = {"command", "file", "runtime", "user", "measurement"}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sanitize(text: str, root: Path) -> str:
    value = str(text)
    home = str(Path.home())
    root_text = str(root)
    if root_text:
        value = value.replace(root_text, "$ROOT")
    if home:
        value = value.replace(home, "$HOME")
    return value


def evidence(kind: str, source: str, detail: str, root: Path) -> dict[str, str]:
    if kind not in EVIDENCE_KINDS:
        raise ValueError(f"invalid evidence kind: {kind}")
    return {
        "kind": kind,
        "source": sanitize(source, root),
        "detail": sanitize(detail, root),
    }


def fact(
    status: str,
    value: Any,
    evidence_rows: list[dict[str, str]],
    question: str | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "value": value,
        "evidence": evidence_rows,
        "question": question,
    }


def read_os_release() -> dict[str, str]:
    path = Path("/etc/os-release")
    result: dict[str, str] = {}
    if not path.is_file():
        return result
    for raw in path.read_text(errors="replace").splitlines():
        if "=" not in raw or raw.startswith("#"):
            continue
        key, value = raw.split("=", 1)
        result[key] = value.strip().strip('"')
    return result


def executable_inventory(
    root: Path, selected: list[str] | None = None
) -> dict[str, list[str]]:
    if selected:
        found: dict[str, list[str]] = {}
        for name in sorted(set(selected)):
            resolved = shutil.which(name)
            found[name] = [sanitize(resolved, root)] if resolved else []
        return found
    found: dict[str, list[str]] = {}
    for raw_dir in os.environ.get("PATH", "").split(os.pathsep):
        if not raw_dir:
            continue
        directory = Path(raw_dir)
        try:
            entries = list(directory.iterdir())
        except OSError:
            continue
        for entry in entries:
            try:
                mode = entry.stat().st_mode
            except OSError:
                continue
            if not stat.S_ISREG(mode) or not os.access(entry, os.X_OK):
                continue
            location = sanitize(str(entry), root)
            found.setdefault(entry.name, [])
            if location not in found[entry.name]:
                found[entry.name].append(location)
    return dict(sorted(found.items()))


def model_lanes(
    root: Path, model_map: Path | None
) -> tuple[str, Any, list[dict[str, str]], str | None]:
    path = model_map or root / "config" / "model-map.toml"
    if not path.is_file():
        return (
            "unknown",
            None,
            [evidence("file", str(path), "model map not found", root)],
            "Where are symbolic model lanes configured on this install?",
        )
    if tomllib is None:
        return (
            "unknown",
            None,
            [
                evidence(
                    "runtime",
                    "python",
                    "tomllib unavailable; model map was not parsed",
                    root,
                )
            ],
            "Parse the model map with a TOML reader and record every lane binding.",
        )
    try:
        data = tomllib.loads(path.read_text())
    except (OSError, ValueError) as exc:
        return (
            "unknown",
            None,
            [evidence("file", str(path), f"parse failed: {exc}", root)],
            "Repair or identify the authoritative model map before auditing delegation claims.",
        )
    lanes = data.get("lanes", {})
    if not isinstance(lanes, dict):
        lanes = {}
    value: dict[str, Any] = {}
    for name, binding in sorted(lanes.items()):
        model = binding if isinstance(binding, str) else None
        state = "bound"
        if not model:
            state = "empty"
        elif model.startswith("<") or "PICK_" in model:
            state = "placeholder"
        wrappers = []
        for candidate in (root / "bin" / name, root / "bin" / f"{name}.sh"):
            if candidate.exists():
                wrappers.append(sanitize(str(candidate), root))
        value[str(name)] = {"binding": model, "state": state, "wrappers": wrappers}
    status = "observed" if value else "unknown"
    question = (
        None
        if value
        else "The model map has no [lanes] entries; which delegation bindings are current?"
    )
    return (
        status,
        value or None,
        [evidence("file", str(path), "parsed [lanes] bindings", root)],
        question,
    )


def active_mcp_probe(root: Path, timeout_seconds: float | None) -> dict[str, Any]:
    if timeout_seconds is None:
        return fact(
            "unknown",
            None,
            [],
            "Choose an active-command timeout from this install's observed CLI latency, then rerun with --active-timeout-seconds to test available MCP list commands.",
        )
    rows: dict[str, Any] = {}
    ev: list[dict[str, str]] = []
    for cli in ("codex", "claude"):
        resolved = shutil.which(cli)
        if not resolved:
            rows[cli] = {"status": "unavailable", "exit_code": None, "output": ""}
            ev.append(evidence("command", f"command -v {cli}", "not found", root))
            continue
        try:
            proc = subprocess.run(
                [resolved, "mcp", "list"],
                cwd=root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                timeout=timeout_seconds,
                check=False,
            )
            output = sanitize(proc.stdout, root)
            rows[cli] = {
                "status": "responded" if proc.returncode == 0 else "error",
                "exit_code": proc.returncode,
                "output": output,
            }
            ev.append(
                evidence(
                    "command",
                    f"{cli} mcp list",
                    f"exit {proc.returncode}; timeout chosen by operator: {timeout_seconds}s",
                    root,
                )
            )
        except subprocess.TimeoutExpired as exc:
            stdout = (
                exc.stdout.decode(errors="replace")
                if isinstance(exc.stdout, bytes)
                else (exc.stdout or "")
            )
            stderr = (
                exc.stderr.decode(errors="replace")
                if isinstance(exc.stderr, bytes)
                else (exc.stderr or "")
            )
            rows[cli] = {
                "status": "timeout",
                "exit_code": None,
                "output": sanitize(stdout + stderr, root),
            }
            ev.append(
                evidence(
                    "command",
                    f"{cli} mcp list",
                    f"exceeded operator-chosen {timeout_seconds}s timeout",
                    root,
                )
            )
    statuses = {row["status"] for row in rows.values()}
    status = "observed" if statuses <= {"responded", "unavailable"} else "mixed"
    return fact(status, rows, ev, None)


def load_answers(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    data = json.loads(path.read_text())
    facts = data.get("facts", data)
    if not isinstance(facts, dict):
        raise ValueError("answers must be an object or contain a facts object")
    return facts


def merge_declared(facts: dict[str, Any], answers: dict[str, Any], root: Path) -> None:
    for name, answer in answers.items():
        if not isinstance(answer, dict):
            answer = {"value": answer}
        current = facts.get(name)
        if isinstance(current, dict) and current.get("status") in {"observed", "mixed"}:
            continue
        value = answer.get("value")
        status = answer.get("status", "declared")
        if status not in ANSWER_STATUSES:
            raise ValueError(f"invalid fact status for {name}: {status}")
        if status == "not_applicable":
            facts[name] = fact("not_applicable", None, [], None)
            continue
        if status == "unknown" or value is None:
            facts[name] = fact(
                "unknown",
                None,
                [],
                answer.get("question") or UNKNOWN_QUESTIONS.get(name),
            )
            continue
        source = answer.get("source", "ground-truth answers")
        detail = answer.get(
            "detail",
            "declared by the operator; verify against local evidence where possible",
        )
        supplied_evidence = answer.get("evidence")
        if isinstance(supplied_evidence, list):
            ev = [
                evidence(
                    str(row.get("kind", "user")),
                    str(row.get("source", source)),
                    str(row.get("detail", detail)),
                    root,
                )
                for row in supplied_evidence
                if isinstance(row, dict)
            ]
        else:
            ev = [evidence("user", str(source), str(detail), root)]
        if not ev:
            raise ValueError(
                f"declared fact {name} requires at least one evidence item"
            )
        facts[name] = fact("declared", value, ev, None)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path, required=True, help="Instruction-library root"
    )
    parser.add_argument("--output", type=Path, required=True, help="Output JSON path")
    parser.add_argument(
        "--answers", type=Path, help="Filled declarations to merge into unknown fields"
    )
    parser.add_argument("--model-map", type=Path, help="Override config/model-map.toml")
    parser.add_argument(
        "--cli-tool",
        action="append",
        help="Probe one corpus-relevant executable name; repeat to keep the published snapshot focused. Omission inventories all PATH executables.",
    )
    parser.add_argument(
        "--active-timeout-seconds",
        type=float,
        help="Operator-chosen timeout for MCP CLI health commands; omission preserves unknown",
    )
    args = parser.parse_args()
    if args.active_timeout_seconds is not None and args.active_timeout_seconds <= 0:
        parser.error("--active-timeout-seconds must be positive")
    root = args.root.resolve()
    timestamp = now_iso()
    os_release = read_os_release()
    facts: dict[str, Any] = {}
    facts["platform"] = fact(
        "observed",
        {
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "python": platform.python_version(),
            "os_release": os_release,
        },
        [
            evidence(
                "command",
                "platform + /etc/os-release",
                "read from the live probe process",
                root,
            )
        ],
        None,
    )
    inventory = executable_inventory(root, args.cli_tool)
    facts["cli_tools"] = fact(
        "observed",
        {"count": len(inventory), "executables": inventory},
        [
            evidence(
                "measurement",
                "PATH",
                "resolved the operator-selected corpus tool list with shutil.which"
                if args.cli_tool
                else "enumerated executable regular files in every readable PATH directory",
                root,
            )
        ],
        None,
    )
    lane_status, lane_value, lane_evidence, lane_question = model_lanes(
        root, args.model_map
    )
    facts["model_lanes"] = fact(lane_status, lane_value, lane_evidence, lane_question)
    facts["mcp_servers"] = active_mcp_probe(root, args.active_timeout_seconds)
    for name, question in UNKNOWN_QUESTIONS.items():
        facts.setdefault(name, fact("unknown", None, [], question))
    merge_declared(facts, load_answers(args.answers), root)
    result = {
        "schema_version": "1.0",
        "observed_at": timestamp,
        "root_label": root.name,
        "facts": dict(sorted(facts.items())),
    }
    schema_path = Path(__file__).resolve().parent.parent / "ground-truth.schema.json"
    schema = json.loads(schema_path.read_text())
    errors = validate_instance(result, schema)
    if errors:
        detail = "; ".join(errors)
        raise ValueError(f"ground truth failed schema validation: {detail}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")
    unknowns = sorted(
        name for name, row in facts.items() if row.get("status") == "unknown"
    )
    print(f"WROTE {args.output}")
    print(f"FACTS {len(facts)}; UNKNOWN {len(unknowns)}")
    for name in unknowns:
        print(f"  {name}: {facts[name].get('question')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
