#!/usr/bin/env python3
"""Diagnose the installed DeepSeek primary lifecycle without a model call."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
from typing import Any


try:
    import install as setup_install
    import runtime_overlay as runtime_overlay_writer
except ImportError:  # pragma: no cover - installed script imports its adjacent copy.
    from . import install as setup_install
    from . import runtime_overlay as runtime_overlay_writer


EXPECTED_DSH_VERSION = "0.1.0-rc.6"
# A local composed-config dump measured below 0.6s on this installation; five
# seconds is its explicit pre-spend failure budget, not a model-call timeout.
CONFIG_TIMEOUT_SECONDS = 5.0
PLUGIN_START = re.compile(r"^- id: (?P<identifier>[^\s]+)$")


def check(status: str, detail: str) -> dict[str, str]:
    return {"status": status, "detail": detail}


def plugin_block(config: str, identifier: str) -> str | None:
    lines = config.splitlines()
    start: int | None = None
    for index, line in enumerate(lines):
        match = PLUGIN_START.fullmatch(line)
        if match and match.group("identifier") == identifier:
            start = index
            break
    if start is None:
        return None
    end = len(lines)
    for index in range(start + 1, len(lines)):
        if PLUGIN_START.fullmatch(lines[index]):
            end = index
            break
    return "\n".join(lines[start:end])


def block_has_line(block: str, expected: str) -> bool:
    return expected in {line.strip() for line in block.splitlines()}


def block_field_lines(block: str, field: str) -> list[str]:
    prefix = f"{field}:"
    return [
        line.strip()
        for line in block.splitlines()
        if line.strip().startswith(prefix)
    ]


def managed_check(primary_root: Path) -> dict[str, str]:
    manifest_path = primary_root / setup_install.MANIFEST_NAME
    try:
        if primary_root.is_symlink() or not primary_root.is_dir():
            return check("fail", f"primary root is not a regular directory: {primary_root}")
        if primary_root.stat().st_mode & 0o777 != 0o700:
            return check("fail", f"primary root mode is not 0700: {primary_root}")
        files = setup_install.load_manifest(manifest_path)
    except RuntimeError as exc:
        return check("fail", str(exc))
    except OSError as exc:
        return check("fail", f"managed root is unreadable: {exc}")
    if not files:
        return check("fail", f"managed manifest is absent or empty: {manifest_path}")
    try:
        if manifest_path.stat().st_mode & 0o777 != 0o600:
            return check("fail", f"managed manifest mode is not 0600: {manifest_path}")
    except OSError as exc:
        return check("fail", f"managed manifest is unreadable: {exc}")
    expected_modes = {
        artifact.target.as_posix(): artifact.mode
        for artifact in setup_install.source_artifacts(primary_root)
    }
    if set(files) != set(expected_modes):
        return check("fail", "managed manifest target set does not match this doctor")
    failures: list[str] = []
    for relative, expected in sorted(files.items()):
        path = primary_root / relative
        try:
            setup_install.validate_parent(
                primary_root, Path(relative).parent, create=False
            )
            observed = setup_install.snapshot(path)
            if not observed.exists:
                failures.append(f"{relative}: not a regular file")
            elif observed.digest != expected:
                failures.append(f"{relative}: hash mismatch")
            elif observed.mode is None or observed.mode & 0o777 != expected_modes[relative]:
                failures.append(f"{relative}: mode mismatch")
        except (OSError, RuntimeError) as exc:
            failures.append(f"{relative}: {exc}")
    if failures:
        return check("fail", "; ".join(failures))
    return check("ok", f"{len(files)} managed files match the manifest")


def authority_check(
    primary_root: Path, delegated_home: Path, delegated_overlay: Path
) -> dict[str, str]:
    try:
        if primary_root.resolve() == delegated_home.resolve():
            return check("fail", "primary and delegated DSH homes are identical")
        agents = (primary_root / "AGENTS.md").read_text(encoding="utf-8")
        delegated = delegated_overlay.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        return check("fail", f"authority surface unreadable: {exc}")
    if "user-facing primary DeepSeek" not in agents:
        return check("fail", "primary AGENTS.md lacks its root authority marker")
    if "Delegated DeepSeek agents never call `memo note`" not in agents:
        return check("fail", "primary AGENTS.md lacks the delegate memory boundary")
    if "delegated subagent" not in delegated:
        return check("fail", "delegated overlay lacks its delegated-role marker")
    if "primary DeepSeek may call" in delegated:
        return check("fail", "delegated overlay contains primary memory authority")
    return check("ok", "primary and delegated homes and authority markers are distinct")


def launcher_check(primary_root: Path, launcher_link: Path) -> dict[str, str]:
    expected = primary_root / "bin" / "dsh-primary"
    if not os.path.lexists(launcher_link):
        return check("fail", f"launcher link is absent: {launcher_link}")
    if not launcher_link.is_symlink():
        return check("fail", f"launcher path is not a symlink: {launcher_link}")
    target = os.readlink(launcher_link)
    if target != str(expected):
        return check("fail", f"launcher points to {target}, expected {expected}")
    if not expected.is_file() or not os.access(expected, os.X_OK):
        return check("fail", f"installed launcher is not executable: {expected}")
    return check("ok", f"launcher resolves to {expected}")


def driver_check(driver_bin: Path) -> dict[str, str]:
    if not driver_bin.is_file() or not os.access(driver_bin, os.X_OK):
        return check("fail", f"DSH driver is not executable: {driver_bin}")
    try:
        result = subprocess.run(
            [str(driver_bin), "--version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=CONFIG_TIMEOUT_SECONDS,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return check("fail", f"DSH version probe failed: {exc}")
    version = result.stdout.strip()
    if result.returncode != 0:
        return check("fail", f"DSH version probe exited {result.returncode}")
    if version != EXPECTED_DSH_VERSION:
        return check("fail", f"DSH version is {version!r}, expected {EXPECTED_DSH_VERSION}")
    return check("ok", f"DSH {version}")


def composed_config_check(
    *,
    primary_root: Path,
    driver_bin: Path,
    model: str,
    runtime_overlay: Path | None = None,
    static_overlay: Path | None = None,
) -> dict[str, str]:
    if model not in {"deepseek-v4-flash", "deepseek-v4-pro"}:
        return check("fail", f"unsupported primary model: {model}")
    if runtime_overlay is None and model != "deepseek-v4-flash":
        with tempfile.TemporaryDirectory(prefix="dsh-primary-doctor-") as directory:
            generated = Path(directory) / "runtime-overlay.json"
            runtime_overlay_writer.write_overlay(
                generated,
                Path(directory) / "sessions",
                model,
            )
            return composed_config_check(
                primary_root=primary_root,
                driver_bin=driver_bin,
                model=model,
                runtime_overlay=generated,
                static_overlay=static_overlay,
            )
    expected_session_root = primary_root / "sessions"
    if runtime_overlay is not None:
        try:
            expected_session_root = runtime_overlay_writer.read_overlay(
                runtime_overlay, model
            )
        except ValueError as exc:
            return check("fail", str(exc))

    installed_overlay = primary_root / "primary-overlay.yml"
    overlay = static_overlay or installed_overlay
    overlay_snapshots: list[tuple[Path, setup_install.Snapshot]] = []
    if static_overlay is not None:
        if runtime_overlay is None or static_overlay.parent != runtime_overlay.parent:
            return check(
                "fail", "static and runtime overlays must share one per-run root"
            )
        try:
            installed_snapshot = setup_install.snapshot(installed_overlay)
            static_snapshot = setup_install.snapshot(static_overlay)
        except RuntimeError as exc:
            return check("fail", str(exc))
        if (
            not installed_snapshot.exists
            or not static_snapshot.exists
            or installed_snapshot.digest != static_snapshot.digest
            or static_snapshot.mode is None
            or static_snapshot.mode & 0o777 != 0o600
        ):
            return check(
                "fail", "per-run static overlay does not match the managed 0600 source"
            )
        overlay_snapshots = [
            (installed_overlay, installed_snapshot),
            (static_overlay, static_snapshot),
        ]
    environment = os.environ.copy()
    environment.update(
        {
            "DSH_HOME": str(primary_root),
            "DSH_PRIMARY_MODEL": model,
            "DSH_PERMISSION_MODE": "danger-full-access",
            "DSH_TELEMETRY_DISABLED": "1",
        }
    )
    try:
        command = [
            str(driver_bin),
            "--profile",
            "headless",
            "--patch",
            str(overlay),
        ]
        if runtime_overlay is not None:
            command.extend(["--patch", str(runtime_overlay)])
        command.append("--dump-config")
        result = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            env=environment,
            timeout=CONFIG_TIMEOUT_SECONDS,
            shell=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return check("fail", f"composed configuration probe failed: {exc}")
    try:
        for path, observed in overlay_snapshots:
            setup_install.require_snapshot(path, observed)
    except RuntimeError as exc:
        return check("fail", str(exc))
    if result.returncode != 0:
        detail = " ".join((result.stderr or result.stdout).split())
        return check("fail", f"composed configuration exited {result.returncode}: {detail}")
    if "prime-inference" in result.stdout.lower():
        return check("fail", "composed configuration contains the forbidden provider")

    required_lines = {
        "agent-default-model": [
            "provider: deepseek-official",
            f"model: {model}",
        ],
        "llm-deepseek": ["baseURL: https://api.deepseek.com"],
        "web-search-deepseek": [
            "baseURL: https://api.deepseek.com/anthropic/v1"
        ],
        "agent-instructions": [
            f"dshHome: {primary_root}",
            "- AGENTS.md",
        ],
        "skill-filesystem": [f"dshHome: {primary_root}"],
        "session-persistence-jsonl": [f"root: {expected_session_root}"],
    }
    failures: list[str] = []
    for identifier, expected_lines in required_lines.items():
        block = plugin_block(result.stdout, identifier)
        if block is None:
            failures.append(f"missing plugin {identifier}")
            continue
        for expected_line in expected_lines:
            if not block_has_line(block, expected_line):
                failures.append(f"{identifier} lacks exact line {expected_line!r}")
    singleton_fields = {
        "agent-default-model": {
            "provider": "provider: deepseek-official",
            "model": f"model: {model}",
        },
        "llm-deepseek": {"baseURL": "baseURL: https://api.deepseek.com"},
        "web-search-deepseek": {
            "baseURL": "baseURL: https://api.deepseek.com/anthropic/v1"
        },
        "agent-instructions": {"dshHome": f"dshHome: {primary_root}"},
        "skill-filesystem": {"dshHome": f"dshHome: {primary_root}"},
        "session-persistence-jsonl": {
            "root": f"root: {expected_session_root}"
        },
    }
    for identifier, fields in singleton_fields.items():
        block = plugin_block(result.stdout, identifier)
        if block is None:
            continue
        for field, expected_line in fields.items():
            if block_field_lines(block, field) != [expected_line]:
                failures.append(
                    f"{identifier} must contain exactly one {field!r} field"
                )
    system_prompt = plugin_block(result.stdout, "system-prompt")
    if system_prompt is None:
        failures.append("missing plugin system-prompt")
    elif "root user-facing primary DeepSeek operator" not in system_prompt:
        failures.append("system-prompt lacks the primary-role marker")
    for identifier in setup_install.NATIVE_CHILD_SURFACES:
        block = plugin_block(result.stdout, identifier)
        if block is not None and not block_has_line(block, "disabled: true"):
            failures.append(f"native child surface {identifier} is not disabled")
    if failures:
        return check("fail", "; ".join(failures))
    return check("ok", f"official provider, {model}, and isolated primary roots compose")


def diagnose(
    *,
    primary_root: Path,
    launcher_link: Path,
    delegated_home: Path,
    driver_bin: Path,
    delegated_overlay: Path,
    run_composed_config: bool = True,
    model: str = "deepseek-v4-flash",
    runtime_overlay: Path | None = None,
    static_overlay: Path | None = None,
) -> dict[str, Any]:
    checks: dict[str, dict[str, str]] = {
        "managed_layer": managed_check(primary_root),
        "authority_isolation": authority_check(
            primary_root, delegated_home, delegated_overlay
        ),
        "launcher": launcher_check(primary_root, launcher_link),
    }
    if run_composed_config:
        checks["driver"] = driver_check(driver_bin)
        if checks["driver"]["status"] == "ok":
            checks["composed_config"] = composed_config_check(
                primary_root=primary_root,
                driver_bin=driver_bin,
                model=model,
                runtime_overlay=runtime_overlay,
                static_overlay=static_overlay,
            )
        else:
            checks["composed_config"] = check(
                "fail", "not attempted because the driver check failed"
            )
    return {
        "ok": all(value["status"] == "ok" for value in checks.values()),
        "primary_root": str(primary_root),
        "checks": checks,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--primary-root",
        type=Path,
        default=Path.home() / ".local" / "share" / "dsh-primary",
    )
    parser.add_argument(
        "--launcher-link",
        type=Path,
        default=Path.home() / ".local" / "bin" / "dsh-primary",
    )
    parser.add_argument(
        "--delegated-home",
        type=Path,
        default=Path.home() / ".local" / "share" / "dsh-driver" / "home",
    )
    parser.add_argument(
        "--driver-bin",
        type=Path,
        default=Path.home()
        / ".local"
        / "share"
        / "dsh-driver"
        / "node_modules"
        / ".bin"
        / "dsh",
    )
    parser.add_argument(
        "--delegated-overlay",
        type=Path,
        default=Path.home() / ".config" / "delegate" / "dsh" / "dsh-agent.yml",
    )
    parser.add_argument(
        "--model",
        choices=("deepseek-v4-flash", "deepseek-v4-pro"),
        default="deepseek-v4-flash",
    )
    parser.add_argument(
        "--runtime-overlay",
        type=Path,
        help="per-run provider/model/session overlay created by dsh-primary",
    )
    parser.add_argument(
        "--static-overlay",
        type=Path,
        help="per-run copy of the managed static primary overlay",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--preflight",
        action="store_true",
        help="run the same offline refusal gate used before paid dispatch",
    )
    return parser.parse_args()


def main() -> int:
    arguments = parse_args()
    report = diagnose(
        primary_root=arguments.primary_root.expanduser().absolute(),
        launcher_link=arguments.launcher_link.expanduser().absolute(),
        delegated_home=arguments.delegated_home.expanduser().absolute(),
        driver_bin=arguments.driver_bin.expanduser().absolute(),
        delegated_overlay=arguments.delegated_overlay.expanduser().absolute(),
        model=arguments.model,
        runtime_overlay=(
            arguments.runtime_overlay.expanduser().absolute()
            if arguments.runtime_overlay is not None
            else None
        ),
        static_overlay=(
            arguments.static_overlay.expanduser().absolute()
            if arguments.static_overlay is not None
            else None
        ),
    )
    if arguments.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        for name, result in report["checks"].items():
            print(f"{result['status'].upper():4} {name}: {result['detail']}")
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
