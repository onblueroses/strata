#!/usr/bin/env python3
"""Move classified private content out, then sweep unknown vault roots.

The allowed set and mirror set are derived from one root-kind mapping. A mirror
was once flattened when only a prose allow-list changed; configure both through
BRAIN_ROOTS_FILE and update the vault rule book in the same change. Content
patterns are supplied separately and are deliberately absent from this code.
"""
import datetime as dt
import json
import os
import re
import shutil
import sys
from pathlib import Path

DEFAULT_ROOTS = {
    "Start here.md": "managed", "AGENTS.md": "managed", "CLAUDE.md": "managed",
    "0 Company": "managed", "1 CRM": "managed", "2 Market": "managed",
    "3 Research": "managed", "4 Calendar": "managed", "5 Inbox": "managed",
    "9 Agents": "managed",
}


def roots_from(path):
    roots = json.loads(Path(path).read_text(encoding="utf-8")) if path else DEFAULT_ROOTS
    if not isinstance(roots, dict) or not roots:
        raise ValueError("root configuration must be a nonempty name-to-kind object")
    for name, kind in roots.items():
        if not isinstance(name, str) or name in {"", ".", ".."} or "/" in name or name.startswith("."):
            raise ValueError(f"invalid root name: {name!r}")
        if kind not in {"managed", "mirror"}:
            raise ValueError(f"invalid root kind for {name!r}: {kind!r}")
    required = {"5 Inbox", "9 Agents", "AGENTS.md"}
    if not required.issubset(roots) or any(roots[name] != "managed" for name in required):
        raise ValueError("capture, trace, and rule-book roots must be managed")
    return roots


def root_sets(roots):
    """Both sets come from the same mapping; mirrors cannot be forgotten."""
    allowed = set(roots)
    mirrors = {name for name, kind in roots.items() if kind == "mirror"}
    return allowed, mirrors


def classifier_from(path):
    """Load a narrow folder/type/index-title classifier from a private config."""
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    required = {"folder_pattern", "record_type", "index_type", "index_title_pattern", "reason"}
    if not isinstance(config, dict) or not required <= config.keys():
        raise ValueError("content classifier needs folder, type, index-title and reason fields")
    if not all(isinstance(config[key], str) and config[key] for key in required):
        raise ValueError("content classifier fields must be nonempty strings")
    return {
        "folder": re.compile(config["folder_pattern"], re.I),
        "record_type": config["record_type"].casefold(),
        "index_type": config["index_type"].casefold(),
        "index_title": re.compile(config["index_title_pattern"], re.I),
        "reason": config["reason"],
    }


def visible_files(folder, vault):
    for path in sorted(folder.rglob("*")):
        if path.is_file() and not any(part.startswith(".") for part in path.relative_to(vault).parts):
            yield path


def member_files(vault, mirrors):
    """Visible files outside agent apparatus and external mirrors, including retired roots."""
    for entry in sorted(vault.iterdir()):
        if entry.name.startswith(".") or entry.name == "9 Agents" or entry.name in mirrors:
            continue
        if entry.is_file():
            yield entry
        elif entry.is_dir():
            yield from visible_files(entry, vault)


def frontmatter(path):
    if path.suffix != ".md":
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---\n", 4)
    return text[4:end] if end >= 0 else ""


def field(fm, name):
    match = re.search(rf"^{re.escape(name)}:\s*(.+)$", fm, re.M)
    return match.group(1).strip().strip("\"'") if match else ""


def is_excluded_content(path, vault, classifier):
    rel = path.relative_to(vault)
    if any(classifier["folder"].search(part) for part in rel.parts[:-1]):
        return True
    fm = frontmatter(path)
    kind = field(fm, "type").casefold()
    # Prefix match, as the source has it: a subtype of the record type is the same material.
    if kind.startswith(classifier["record_type"]):
        return True
    return kind.startswith(classifier["index_type"]) and bool(classifier["index_title"].search(field(fm, "title")))


def free_name(captures, name):
    target = captures / name
    n = 2
    while target.exists():
        target = captures / f"{Path(name).stem}-{n}{Path(name).suffix}"
        n += 1
    return target


def free_holding(holding, day, old_rel):
    target = holding / day / old_rel
    n = 2
    while target.exists():
        old = Path(old_rel)
        target = holding / day / old.with_name(f"{old.stem}-{n}{old.suffix}")
        n += 1
    return target


def append_log(trace, now, message, dry_run):
    if dry_run:
        return
    trace.parent.mkdir(parents=True, exist_ok=True)
    if not trace.exists():
        trace.write_text(f"---\nschema: 1\ntype: trace\ntitle: Retired-path sweep\nsource: sweep\ndate: {now:%Y-%m-%d}\nauthor: sweep/system\n---\n\n# Retired-path sweep\n\n", encoding="utf-8")
    with trace.open("a", encoding="utf-8") as log:
        log.write(f"- {now:%Y-%m-%dT%H:%MZ} {message}\n")


def sweep_excluded(vault, mirrors, classifier, holding, manifest, vault_host_path,
                   min_age, now, trace, dry_run):
    found = [path for path in member_files(vault, mirrors)
             if is_excluded_content(path, vault, classifier)]
    if not found:
        return 0, [], set()
    youngest = min(now - dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
                   for path in found)
    if youngest < min_age:
        print(f"classified: {len(found)} file(s), batch still being written; waiting")
        return 0, [], set(found)
    day = now.strftime("%Y-%m-%d")
    parents = []
    for path in found:
        old_rel = str(path.relative_to(vault))
        target = free_holding(holding, day, old_rel)
        print(f"out {old_rel} -> {target}")
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(target))
            manifest.parent.mkdir(parents=True, exist_ok=True)
            with manifest.open("a", encoding="utf-8") as out:
                out.write(f"{path.name} | {vault_host_path}/{old_rel} | {day} | {classifier['reason']}\n")
        append_log(trace, now, f"moved out of vault `{old_rel}` -> holding `{target}`", dry_run)
        parents.append(path.parent)
    return len(found), parents, set(found)


def prune_empty(dirs, vault, allowed, dry_run):
    """Remove empty folders, deepest first; keep the sections and their record folders."""
    for d in sorted(set(dirs), key=lambda p: -len(p.parts)):
        while d != vault and d.exists():
            rel = d.relative_to(vault)
            keep = rel.parts[0] in allowed and len(rel.parts) <= 2
            try:
                if keep or any(d.iterdir()):
                    break
            except OSError:
                break
            print(f"rmdir {rel}")
            if not dry_run:
                d.rmdir()
            d = d.parent


def annotate(path, old_rel):
    if path.suffix != ".md":
        return
    text = path.read_text(encoding="utf-8", errors="replace")
    if not text.startswith("---\n"):
        title_match = re.search(r"^# (.+)$", text, re.M)
        title = title_match.group(1).strip() if title_match else path.stem.replace("-", " ")
        text = f"---\nschema: 1\ntype: capture\ntitle: {json.dumps(title)}\nswept_from: {json.dumps(old_rel)}\n---\n\n" + text
    else:
        end = text.find("\n---\n", 4)
        if end < 0:
            return
        fm, body = text[4:end], text[end + 5:]
        lines = fm.split("\n")
        if not re.search(r"^title:", fm, re.M):
            title_match = re.search(r"^# (.+)$", body, re.M)
            title = title_match.group(1).strip() if title_match else path.stem.replace("-", " ")
            lines.append("title: " + json.dumps(title))
        if not re.search(r"^swept_from:", fm, re.M):
            lines.append("swept_from: " + json.dumps(old_rel))
        text = "---\n" + "\n".join(lines) + "\n---\n" + body
    path.write_text(text, encoding="utf-8")


def sweep(vault, roots, min_age, dry_run=False, now=None, *, classifier=None,
          holding=None, manifest=None, vault_host_path=None):
    now = now or dt.datetime.now(dt.timezone.utc)
    allowed, mirrors = root_sets(roots)
    assert mirrors <= allowed
    captures = vault / "5 Inbox" / "captures"
    trace = vault / "9 Agents" / "machine" / "traces" / "retired-path-sweep.md"
    excluded, parents, claimed = 0, [], set()
    if classifier is not None:
        if holding is None or manifest is None:
            raise ValueError("classified-content sweep needs holding and manifest paths")
        holding, manifest = Path(holding).resolve(), Path(manifest).resolve()
        if holding.is_relative_to(vault.resolve()) or manifest.is_relative_to(vault.resolve()):
            raise ValueError("holding and manifest must stay outside the vault")
        excluded, parents, claimed = sweep_excluded(
            vault, mirrors, classifier, holding, manifest, vault_host_path or str(vault),
            min_age, now, trace, dry_run)
    moved = 0
    for entry in sorted(vault.iterdir()):
        if entry.name.startswith(".") or entry.name in allowed:
            continue
        paths = [entry] if entry.is_file() else visible_files(entry, vault) if entry.is_dir() else []
        for path in paths:
            if path in claimed:
                continue
            age = now - dt.datetime.fromtimestamp(path.stat().st_mtime, dt.timezone.utc)
            old_rel = str(path.relative_to(vault))
            if age < min_age:
                print(f"skip (young) {old_rel}")
                continue
            target = free_name(captures, path.name)
            new_rel = str(target.relative_to(vault))
            print(f"move {old_rel} -> {new_rel}")
            if not dry_run:
                captures.mkdir(parents=True, exist_ok=True)
                path.rename(target)
                annotate(target, old_rel)
            append_log(trace, now, f"moved `{old_rel}` -> `{new_rel}`", dry_run)
            parents.append(path.parent)
            moved += 1
    # retired root folders go entirely, even when they never held a file
    parents.extend(e for e in vault.iterdir() if e.is_dir() and e.name not in allowed and not e.name.startswith("."))
    prune_empty(parents, vault, allowed, dry_run)
    verb = "would move" if dry_run else "moved"
    print(f"{verb} out of vault: {excluded}; {verb} into captures: {moved}")
    return moved


def main():
    vault = Path(os.environ["BRAIN_VAULT_PATH"]).resolve()
    roots = roots_from(os.environ.get("BRAIN_ROOTS_FILE"))
    min_age = dt.timedelta(minutes=int(os.environ.get("BRAIN_SWEEP_MIN_AGE_MIN", "30")))
    classifier = classifier_from(os.environ["BRAIN_CONTENT_CLASSIFIER_FILE"])
    holding = Path(os.environ["BRAIN_SWEEP_HOLDING"])
    manifest = Path(os.environ.get("BRAIN_SWEEP_MANIFEST", str(holding.parent / "manifest.txt")))
    sweep(vault, roots, min_age, "--dry-run" in sys.argv[1:], classifier=classifier,
          holding=holding, manifest=manifest,
          vault_host_path=os.environ.get("BRAIN_VAULT_HOST_PATH", str(vault)))


if __name__ == "__main__":
    main()
