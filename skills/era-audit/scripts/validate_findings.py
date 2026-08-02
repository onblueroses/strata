#!/usr/bin/env python3
"""Validate findings against the JSON schema, corpus manifest, and exact source quotes."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from schema_tools import validate_instance


CATEGORIES = {
    "hand-holding",
    "small-context",
    "distrust-scaffolding",
    "stale-facts",
    "old-delegation",
    "obsolete-workaround",
    "register-miscalibration",
}
DISPOSITIONS = {"REWRITE", "MODERNIZE", "TOUCH-UP", "CURRENT"}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def validate_schema(data: Any, schema_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text())
    return [f"schema {error}" for error in validate_instance(data, schema)]


def safe_source_path(root: Path, relative: str) -> Path | None:
    unresolved = root / relative
    if Path(relative).is_absolute() or unresolved.is_symlink():
        return None
    resolved = unresolved.resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        return None
    return resolved


def load_sources(
    root: Path | None,
    manifest: dict[str, Any] | None,
    expected_files: set[str] | None,
) -> tuple[dict[str, str], dict[str, str]]:
    sources: dict[str, str] = {}
    hashes: dict[str, str] = {}
    if manifest:
        for row in manifest["files"]:
            if isinstance(row.get("content"), str):
                sources[row["file"]] = row["content"]
            hashes[row["file"]] = row["sha256"]
    if root:
        if expected_files is None:
            raise ValueError(
                "root quote validation requires a corpus file list in the findings"
            )
        for relative in expected_files:
            path = safe_source_path(root, relative)
            if path is None or not path.is_file():
                continue
            try:
                text = path.read_text()
            except (OSError, UnicodeDecodeError):
                continue
            sources.setdefault(relative, text)
            hashes.setdefault(relative, sha256_text(text))
    return sources, hashes


def manifest_from_public_artifact(
    data: dict[str, Any], root: Path
) -> tuple[dict[str, Any], list[str]]:
    """Rebuild frozen content only when the current root matches every recorded hash."""
    errors: list[str] = []
    corpus = data.get("audit", {}).get("corpus", {})
    public_files = corpus.get("files")
    if not isinstance(public_files, list):
        return {"files": []}, [
            "audit.corpus.files is unavailable for current-root validation"
        ]
    files: list[dict[str, Any]] = []
    for index, row in enumerate(public_files):
        if not isinstance(row, dict) or not isinstance(row.get("file"), str):
            errors.append(f"audit.corpus.files[{index}] is not a valid file record")
            continue
        path = safe_source_path(root, row["file"])
        if path is None:
            errors.append(
                f"current-root validation rejects unsafe corpus path: {row['file']}"
            )
            continue
        if not path.is_file():
            errors.append(f"current root is missing frozen corpus file: {row['file']}")
            continue
        try:
            content = path.read_text()
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"cannot read current corpus file {row['file']}: {exc}")
            continue
        files.append({**row, "content": content})
    manifest = {
        key: corpus.get(key)
        for key in (
            "captured_at",
            "git_commit",
            "git_dirty",
            "file_count",
            "bytes",
            "lines",
            "include_patterns",
            "exclude_patterns",
            "batch_basis",
        )
    }
    manifest["files"] = files
    return manifest, errors


def manual_validation(
    data: Any, sources: dict[str, str], expected_files: set[str] | None
) -> list[str]:
    errors: list[str] = []
    if not isinstance(data, dict) or not isinstance(data.get("files"), list):
        return ["findings must be an object containing a files array"]
    rows = data["files"]
    seen: set[str] = set()
    for index, row in enumerate(rows):
        where = f"files[{index}]"
        if not isinstance(row, dict):
            errors.append(f"{where}: record is not an object")
            continue
        path = row.get("file")
        if not isinstance(path, str) or not path:
            errors.append(f"{where}: file is missing")
            continue
        if path in seen:
            errors.append(f"{where}: duplicate disposition for {path}")
        seen.add(path)
        if row.get("disposition") not in DISPOSITIONS:
            errors.append(f"{where}: invalid disposition {row.get('disposition')!r}")
        findings = row.get("stale_findings")
        if not isinstance(findings, list):
            errors.append(f"{where}: stale_findings is not an array")
            continue
        source = sources.get(path)
        if sources and source is None:
            errors.append(
                f"{where}: source file unavailable for quote validation: {path}"
            )
        for finding_index, finding in enumerate(findings):
            fwhere = f"{where}.stale_findings[{finding_index}]"
            if not isinstance(finding, dict):
                errors.append(f"{fwhere}: finding is not an object")
                continue
            quote = finding.get("quote")
            if not isinstance(quote, str) or not quote:
                errors.append(f"{fwhere}: quote is empty")
            elif source is not None and quote not in source:
                errors.append(
                    f"{fwhere}: quote is not verbatim in {path}: {quote[:120]!r}"
                )
            if finding.get("category") not in CATEGORIES:
                errors.append(f"{fwhere}: invalid category {finding.get('category')!r}")
            for field in ("why_stale", "fix_direction"):
                if (
                    not isinstance(finding.get(field), str)
                    or not finding[field].strip()
                ):
                    errors.append(f"{fwhere}: {field} is empty")
            refs = finding.get("ground_truth_refs")
            if (
                not isinstance(refs, list)
                or not refs
                or not all(isinstance(ref, str) and ref for ref in refs)
            ):
                errors.append(
                    f"{fwhere}: ground_truth_refs must be a nonempty string array"
                )
    if expected_files is not None:
        missing = sorted(expected_files - seen)
        extra = sorted(seen - expected_files)
        if missing:
            errors.append(f"missing file dispositions: {missing}")
        if extra:
            errors.append(f"unexpected file dispositions: {extra}")
    return errors


def aggregate_validation(data: dict[str, Any], manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    rows = data["files"]
    audit = data.get("audit", {})
    finding_count = sum(
        len(row.get("stale_findings", [])) for row in rows if isinstance(row, dict)
    )
    disposition_counts = Counter(
        row.get("disposition") for row in rows if isinstance(row, dict)
    )
    category_counts = Counter(
        finding.get("category")
        for row in rows
        if isinstance(row, dict)
        for finding in row.get("stale_findings", [])
        if isinstance(finding, dict)
    )
    comparisons = {
        "audit.finding_count": (audit.get("finding_count"), finding_count),
        "audit.disposition_counts": (
            audit.get("disposition_counts"),
            dict(sorted(disposition_counts.items())),
        ),
        "audit.category_counts": (
            audit.get("category_counts"),
            dict(sorted(category_counts.items())),
        ),
    }
    corpus = audit.get("corpus", {})
    public_files = [
        {key: row[key] for key in ("file", "sha256", "bytes", "lines", "batch")}
        for row in manifest["files"]
    ]
    for field in (
        "captured_at",
        "git_commit",
        "git_dirty",
        "file_count",
        "bytes",
        "lines",
        "include_patterns",
        "exclude_patterns",
    ):
        comparisons[f"audit.corpus.{field}"] = (corpus.get(field), manifest.get(field))
    comparisons["audit.corpus.files"] = (corpus.get("files"), public_files)
    for label, (actual, expected) in comparisons.items():
        if actual != expected:
            errors.append(f"{label} does not match recomputed or frozen value")
    for index, row in enumerate(manifest["files"]):
        content = row.get("content")
        if not isinstance(content, str):
            errors.append(f"manifest.files[{index}]: frozen content is missing")
            continue
        if hashlib.sha256(content.encode()).hexdigest() != row.get("sha256"):
            errors.append(f"manifest.files[{index}]: frozen content hash mismatch")
        if len(content.encode()) != row.get("bytes"):
            errors.append(f"manifest.files[{index}]: frozen byte count mismatch")
        if len(content.splitlines()) != row.get("lines"):
            errors.append(f"manifest.files[{index}]: frozen line count mismatch")
    return errors


def reference_resolves(ground_truth: dict[str, Any], reference: str) -> bool:
    parts = reference.split(".")
    facts = ground_truth.get("facts", {})
    if not parts or parts[0] not in facts:
        return False
    value: Any = facts[parts[0]]
    for part in parts[1:]:
        if isinstance(value, dict) and part in value:
            value = value[part]
        elif (
            isinstance(value, dict)
            and isinstance(value.get("value"), dict)
            and part in value["value"]
        ):
            value = value["value"][part]
        else:
            return False
    return True


def ground_truth_validation(data: dict[str, Any], ground_truth_path: Path) -> list[str]:
    errors: list[str] = []
    if not ground_truth_path.is_file():
        return [f"ground-truth snapshot is unavailable: {ground_truth_path}"]
    raw = ground_truth_path.read_bytes()
    ground_truth = json.loads(raw)
    recorded = data.get("audit", {}).get("ground_truth", {})
    if recorded.get("sha256") != hashlib.sha256(raw).hexdigest():
        errors.append("audit.ground_truth.sha256 does not match the frozen snapshot")
    unknowns = sorted(
        name
        for name, row in ground_truth.get("facts", {}).items()
        if isinstance(row, dict) and row.get("status") == "unknown"
    )
    if recorded.get("unknown_fields") != unknowns:
        errors.append(
            "audit.ground_truth.unknown_fields does not match the frozen snapshot"
        )
    for row_index, row in enumerate(data.get("files", [])):
        if not isinstance(row, dict):
            continue
        for finding_index, finding in enumerate(row.get("stale_findings", [])):
            if not isinstance(finding, dict):
                continue
            for reference in finding.get("ground_truth_refs", []):
                if not reference_resolves(ground_truth, reference):
                    errors.append(
                        f"files[{row_index}].stale_findings[{finding_index}]: "
                        f"unresolved ground-truth reference {reference!r}"
                    )
    return errors


def drift_report(root: Path, manifest: dict[str, Any]) -> dict[str, list[str]]:
    changed: list[str] = []
    missing: list[str] = []
    for row in manifest["files"]:
        path = root / row["file"]
        if not path.is_file():
            missing.append(row["file"])
            continue
        if hashlib.sha256(path.read_bytes()).hexdigest() != row["sha256"]:
            changed.append(row["file"])
    return {"changed": sorted(changed), "missing": sorted(missing)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--findings", type=Path, required=True)
    parser.add_argument("--root", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument(
        "--schema-only",
        action="store_true",
        help="Validate JSON structure without claiming quote validation",
    )
    args = parser.parse_args()
    data = json.loads(args.findings.read_text())
    errors = validate_schema(data, args.schema)
    if args.schema_only:
        if errors:
            print(f"FAIL {len(errors)} schema validation error(s)")
            for error in errors:
                print(f"- {error}")
            return 1
        print(
            f"PASS schema={args.schema.name} files={len(data['files'])} mode=schema-only"
        )
        return 0
    if not args.manifest and not args.root:
        parser.error(
            "full validation requires --manifest or a hash-matching --root; use --schema-only for structure alone"
        )
    root = args.root.resolve() if args.root else None
    if args.manifest:
        manifest = json.loads(args.manifest.read_text())
        ground_truth_path = args.manifest.parent / "ground-truth.snapshot.json"
        reconstruction_errors: list[str] = []
    else:
        assert root is not None
        manifest, reconstruction_errors = manifest_from_public_artifact(data, root)
        recorded_path = data.get("audit", {}).get("ground_truth", {}).get("path")
        if not isinstance(recorded_path, str) or not recorded_path:
            reconstruction_errors.append("audit.ground_truth.path is unavailable")
            ground_truth_path = Path("__missing_ground_truth__")
        else:
            findings_parent = args.findings.resolve().parent
            candidate = findings_parent / recorded_path
            if Path(recorded_path).is_absolute() or candidate.is_symlink():
                reconstruction_errors.append(
                    "audit.ground_truth.path must name a regular file beside the findings artifact"
                )
                ground_truth_path = Path("__missing_ground_truth__")
            else:
                ground_truth_path = candidate.resolve()
                if ground_truth_path.parent != findings_parent:
                    reconstruction_errors.append(
                        "audit.ground_truth.path must stay beside the findings artifact"
                    )
                    ground_truth_path = Path("__missing_ground_truth__")
    errors.extend(reconstruction_errors)
    expected = {row["file"] for row in manifest["files"]}
    sources, _ = load_sources(
        root,
        manifest,
        expected,
    )
    errors.extend(manual_validation(data, sources, expected))
    if isinstance(data, dict) and isinstance(data.get("files"), list):
        errors.extend(aggregate_validation(data, manifest))
        errors.extend(ground_truth_validation(data, ground_truth_path))
    if errors:
        print(f"FAIL {len(errors)} validation error(s)")
        for error in errors:
            print(f"- {error}")
        return 1
    finding_count = sum(len(row["stale_findings"]) for row in data["files"])
    print(
        f"PASS schema={args.schema.name} files={len(data['files'])} findings={finding_count} quotes=verbatim"
    )
    if root:
        drift = drift_report(root, manifest)
        print(f"DRIFT changed={len(drift['changed'])} missing={len(drift['missing'])}")
        for field in ("changed", "missing"):
            for path in drift[field]:
                print(f"  {field.upper()} {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
