#!/usr/bin/env python3
"""Validate the portable setup tree without third-party dependencies."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tomllib
from pathlib import Path

ROLE_SPECS = {
    "adversarial-reviewer": ("gpt-5.6-sol", "read-only"),
    "docs-researcher": ("gpt-5.6-luna", "read-only"),
    "implementation-worker": ("gpt-5.6-terra", "workspace-write"),
    "knowledge-lookup": ("gpt-5.6-luna", "read-only"),
    "load-bearing-worker": ("gpt-5.6-sol", "workspace-write"),
    "mechanical-worker": ("gpt-5.6-luna", "workspace-write"),
    "systems-researcher": ("gpt-5.6-terra", "read-only"),
}
FORBIDDEN_TOP_LEVEL = {
    ".claude", ".codex", ".local", "agents", "bin", "commands", "config",
    "hooks", "telemetry", "tests", "workspace", "current-setup",
    "CONFIG.md", "MIGRATION.md", "SETUP.md", "settings.json",
    "strata.env", "ruff.toml", "pyrightconfig.json",
}
LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
ABSOLUTE_PATH_RE = re.compile(r"(?<![A-Za-z0-9])/(?:home|Users|root|tmp)(?:/|\b)")
CREDENTIAL_RE = re.compile(
    r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"
    r"|\b(?:sk-|ghp_|github_pat_|xox[baprs]-)[A-Za-z0-9_-]{12,}"
    r"|\bBearer\s+[A-Za-z0-9._~-]{16,}"
    r"|\b(?:api[_-]?key|access[_-]?token|client[_-]?secret)\s*[:=]\s*['\"][^$<{\"']{8,}",
    re.IGNORECASE,
)


def tracked_paths(root: Path) -> list[Path]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            check=True, capture_output=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise RuntimeError("Validation requires a Git checkout") from exc
    return [Path(raw) for raw in result.stdout.decode().split("\0") if raw]


def check_roles(root: Path, errors: list[str]) -> None:
    directory = root / "codex" / "agents"
    if not directory.is_dir():
        errors.append("missing codex/agents directory")
        return
    actual = {p.stem for p in directory.glob("*.toml")}
    for name in sorted(set(ROLE_SPECS) - actual):
        errors.append(f"missing native role: codex/agents/{name}.toml")
    for name in sorted(actual - set(ROLE_SPECS)):
        errors.append(f"unexpected native role: codex/agents/{name}.toml")
    for name, (model, sandbox) in ROLE_SPECS.items():
        path = directory / f"{name}.toml"
        if not path.is_file():
            continue
        try:
            with path.open("rb") as stream:
                data = tomllib.load(stream)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            errors.append(f"{path.relative_to(root)} is not valid TOML: {exc}")
            continue
        if data.get("name") != name:
            errors.append(f"{path.relative_to(root)} has the wrong name")
        if data.get("model") != model:
            errors.append(f"{path.relative_to(root)} has model {data.get('model')!r}, expected {model!r}")
        if data.get("sandbox_mode") != sandbox:
            errors.append(f"{path.relative_to(root)} has sandbox_mode {data.get('sandbox_mode')!r}, expected {sandbox!r}")
        if not isinstance(data.get("description"), str) or not data["description"].strip():
            errors.append(f"{path.relative_to(root)} needs a non-empty description")
        if not isinstance(data.get("developer_instructions"), str) or not data["developer_instructions"].strip():
            errors.append(f"{path.relative_to(root)} needs developer_instructions")


def check_config(root: Path, errors: list[str]) -> None:
    path = root / "codex" / "config.example.toml"
    if not path.is_file():
        errors.append("missing codex/config.example.toml")
        return
    try:
        with path.open("rb") as stream:
            data = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        errors.append(f"{path.relative_to(root)} is not valid TOML: {exc}")
        return
    if data.get("model_provider") != "openai":
        errors.append("codex/config.example.toml must select the openai provider")
    if data.get("service_tier") != "default":
        errors.append("codex/config.example.toml must use the default service tier")


def check_links(root: Path, errors: list[str]) -> None:
    for relative in tracked_paths(root):
        path = root / relative
        if path.suffix != ".md" or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"cannot read {path.relative_to(root)}: {exc}")
            continue
        for target in LINK_RE.findall(text):
            target = target.strip().strip("<>")
            if not target or target.startswith(("#", "http://", "https://", "mailto:")):
                continue
            target_path = target.split("#", 1)[0].split("?", 1)[0]
            if target_path and not (path.parent / target_path).exists():
                errors.append(f"broken relative link in {path.relative_to(root)}: {target}")


def check_skill_frontmatter(root: Path, errors: list[str]) -> None:
    paths = sorted((root / "skills").rglob("SKILL.md")) if (root / "skills").is_dir() else []
    if not paths:
        errors.append("no skills/*/SKILL.md files found")
        return
    for path in paths:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"cannot read {path.relative_to(root)}: {exc}")
            continue
        if not lines or lines[0].strip() != "---":
            errors.append(f"{path.relative_to(root)} must start with YAML frontmatter")
            continue
        try:
            end = lines.index("---", 1)
        except ValueError:
            errors.append(f"{path.relative_to(root)} has unterminated YAML frontmatter")
            continue
        fields = {line.split(":", 1)[0].strip() for line in lines[1:end] if ":" in line}
        for required in ("name", "description"):
            if required not in fields:
                errors.append(f"{path.relative_to(root)} frontmatter lacks {required}")


def check_forbidden_and_secrets(root: Path, errors: list[str]) -> None:
    paths = tracked_paths(root)
    for relative in paths:
        if not (root / relative).exists():
            continue
        if relative.parts and relative.parts[0] in FORBIDDEN_TOP_LEVEL:
            errors.append(f"forbidden legacy path is present: {relative}")
    for relative in paths:
        path = root / relative
        if not path.is_file() or ".git" in relative.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if ABSOLUTE_PATH_RE.search(text):
            errors.append(f"machine absolute path found in {relative}")
        if CREDENTIAL_RE.search(text):
            errors.append(f"credential-like value found in {relative}")


def check_native_setup(root: Path, errors: list[str]) -> None:
    required = (
        "providers.toml", "claude/README.md", "claude/settings.example.json",
        "claude/hooks.example.json", "codex/hooks.example.json",
        "deepseek/AGENTS.md", "deepseek/AGENTS.delegate.md", "deepseek/primary-overlay.example.yml",
        "deepseek/codex-provider.example.toml", "deepseek/provider.env.example",
        "deepseek/launch-adapter.sh", "kimi/config.example.toml", "kimi/AGENTS.md",
        "delegation/codex-run.py", "integrations/hook_adapter.py", "integrations/adapters.example.json",
    )
    for name in required:
        if not (root / name).is_file():
            errors.append(f"missing native setup artifact: {name}")
    for relative in tracked_paths(root):
        path = root / relative
        if not path.is_file():
            continue
        if path.suffix in {".json", ".toml"}:
            try:
                text = path.read_text()
                json.loads(text) if path.suffix == ".json" else tomllib.loads(text)
            except (ValueError, OSError) as exc:
                errors.append(f"invalid native configuration {relative}: {exc}")
    route_file = root / "providers.toml"
    if route_file.is_file():
        try:
            routes = tomllib.loads(route_file.read_text())["routes"]
            for name in ("claude", "codex", "dsh_primary", "dsh_agent", "ds_flash", "ds_pro", "ds_codex", "kimi"):
                if name not in routes:
                    errors.append(f"missing provider route: {name}")
            for name in ("dsh_primary", "dsh_agent", "ds_flash", "ds_pro", "ds_codex"):
                if not routes.get(name, {}).get("spend_authorization_required"):
                    errors.append(f"metered route lacks spend boundary: {name}")
        except (ValueError, KeyError) as exc:
            errors.append(f"invalid provider inventory: {exc}")
    for name in ("code-reviewer", "knowledge-lookup", "orchestrator", "quick-research", "web-mapper"):
        path = root / "claude" / "agents" / f"{name}.md"
        if not path.is_file() or not path.read_text().startswith("---\n"):
            errors.append(f"missing native Claude agent/frontmatter: {name}")
    for name in ("pickup-context", "close-session", "cold-email", "outreach-atlas", "research-viz", "triage", "end", "context-save", "deploy"):
        if not (root / "skills" / name / "SKILL.md").is_file():
            errors.append(f"missing active personal skill: {name}")
    for name in ("claude/hooks.example.json", "codex/hooks.example.json"):
        path = root / name
        if not path.is_file():
            continue
        try:
            config = json.loads(path.read_text())
            privacy = []
            for group in config["hooks"]["PreToolUse"]:
                for hook in group["hooks"]:
                    if hook["command"].endswith(" privacy"):
                        privacy.append(hook)
            if len(privacy) != 1 or privacy[0].get("timeout", 0) < 40:
                errors.append(f"{name} needs one combined privacy adapter with sufficient timeout")
        except (ValueError, KeyError, TypeError) as exc:
            errors.append(f"invalid hook registration {name}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    root = parser.parse_args().root.resolve()
    errors: list[str] = []
    for required in ("AGENTS.md", "README.md", "runtime.md"):
        if not (root / required).is_file():
            errors.append(f"missing required root file: {required}")
    shared = root / "CLAUDE.md"
    if not shared.is_symlink() or shared.readlink() != Path("AGENTS.md"):
        errors.append("CLAUDE.md must link to AGENTS.md")
    check_native_setup(root, errors)
    check_roles(root, errors)
    check_config(root, errors)
    check_links(root, errors)
    check_skill_frontmatter(root, errors)
    check_forbidden_and_secrets(root, errors)
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"setup validation failed with {len(errors)} error(s)", file=sys.stderr)
        return 1
    print(f"setup validation passed: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
