#!/usr/bin/env python3
"""Automatically verify the staged privacy package; never change the index."""
import argparse
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

HOST = ("claude/hooks/gate-gh-public-actions.sh", "claude/hooks/gate-pre-push.sh", "claude/hooks/run-gates.sh",
        "claude/hooks/lib/privacy-decision.sh", "claude/hooks/lib/privacy-event.py", "claude/hooks/lib/privacy-scan.py",
        "claude/gates/tests/test-privacy-gates.sh", "claude/gates/tests/test-privacy-event.py",
        "codex/hooks/pre_tool_use.py")
PREFIX = "claude/hooks/privacy-decision/"


def code(text):
    # Strip comments and quoted examples, so they cannot falsely trip unsafe/hole checks.
    return re.sub(r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|#[^\n]*''', "", text)


def sources(directory):
    files = list(directory.glob("*.bend"))
    names = {f.name for f in files}
    for file in files:
        text = file.read_text()
        if re.search(r"@unsafe\b|\?[A-Za-z_]", code(text)):
            raise ValueError("unsafe/open proof marker in " + file.name)
        aliases = set()
        for line in text.splitlines():
            line = line.strip()
            if not line.startswith("import "):
                continue
            line = line.split("#", 1)[0].strip()
            if line == "import Base":
                if "Base" in aliases:
                    raise ValueError("duplicate Bend import binding in " + file.name + ": Base")
                aliases.add("Base")
                continue
            match = re.fullmatch(r"import \./([^/\s]+\.bend)(?: as ([A-Za-z_][\w.]*))?", line)
            if not match or match[1] not in names:
                raise ValueError("own Bend imports must stay inside the snapshotted package: " + line)
            alias = match[2] or match[1].removesuffix(".bend")
            if alias in aliases:
                raise ValueError("duplicate Bend import binding in " + file.name + ": " + alias)
            aliases.add(alias)


def claims(text):
    result, name = {}, None
    for line in text.splitlines():
        line = re.sub(r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|#[^\n]*''',
                      lambda m: "" if m[0].startswith("#") else m[0], line).rstrip()
        if not line.strip():
            continue
        match = re.fullmatch(r"law ([\w.]+):", line)
        if match:
            name = match[1]
            if name in result:
                raise ValueError("duplicate law: " + name)
            result[name] = []
        elif line[:1].isspace() and name:
            result[name].append(line.rstrip())
        else:
            name = None
    return result


def definitions(text):
    # LAWS-owned semantic predicates are requirements too: otherwise their
    # unmodified law text could be redirected by weakening a helper definition.
    result, name = {}, None
    for line in text.splitlines():
        line = re.sub(r'''"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|#[^\n]*''',
                      lambda m: "" if m[0].startswith("#") else m[0], line).rstrip()
        if not line.strip():
            continue
        match = re.fullmatch(r"def ([\w.]+)\(.*\) -> .*:", line)
        if match:
            name = match[1]
            if name in result:
                raise ValueError("duplicate requirement definition: " + name)
            result[name] = []
        elif line[:1].isspace() and name:
            result[name].append(line.rstrip())
        else:
            name = None
    return result


def foreign_repo_env(environ):
    """The environment without Git's repository-local variables.

    A hook runs with GIT_DIR, GIT_INDEX_FILE and their kin naming the live repository. The fixture
    suites run real init, config, reset and push in scratch repositories; with those variables
    inherited, every one of those commands lands in the live repository instead (a ticket: fixture
    remotes in its config, branches reset, a fixture branch pushed to its origin). githooks(5) says
    to clear them before touching another repository.
    """
    local = set(subprocess.check_output(["git", "rev-parse", "--local-env-vars"], text=True).split())
    return {name: value for name, value in environ.items() if name not in local}


def main(args):
    if args.sources_only:
        sources(Path(args.sources_only))
        return
    root = Path(args.repo or subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())
    def git(*argv):
        return subprocess.check_output(["git", "-C", str(root), *argv])
    tree = args.tree or git("write-tree").decode().strip()
    head = git("rev-parse", "HEAD").decode().strip()
    changed = git("diff", "--name-only", head, tree).decode().splitlines()
    relevant = [p for p in changed if p in HOST or p.startswith(PREFIX) and p.endswith((".bend", ".py", ".sh"))]
    if not relevant:
        return
    if not args.snapshot:
        parent = root / "claude/.local/privacy-bend"
        parent.mkdir(parents=True, exist_ok=True)
        snapshot = Path(tempfile.mkdtemp(prefix="staged-", dir=parent))
        paths = git("ls-tree", "-r", "--name-only", tree, PREFIX, *HOST).decode().splitlines()
        for path in paths:
            if path not in HOST and not path.endswith((".bend", ".py", ".sh")):
                continue
            target = snapshot / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(git("show", tree + ":" + path))
        checker = snapshot / PREFIX / "check-staged.py"
        if not checker.exists():
            raise ValueError("stage the privacy checker with this change")
        # All substantive validation and build/test scripts come from the frozen index.
        subprocess.run([sys.executable, str(checker), "--repo", str(root), "--tree", tree,
                        "--snapshot", str(snapshot)], check=True)
        return
    snapshot = Path(args.snapshot)
    source = snapshot / PREFIX
    sources(source)
    old_text = git("show", head + ":" + PREFIX + "LAWS.bend").decode()
    new_text = (source / "LAWS.bend").read_text()
    old, new = claims(old_text), claims(new_text)
    old_defs, new_defs = definitions(old_text), definitions(new_text)
    if os.environ.get("PRIVACY_REQUIREMENTS_ACK") != "1":
        imports = lambda text: {line.split("#", 1)[0].strip() for line in text.splitlines()
                                if line.strip().startswith("import ")}
        if not imports(old_text).issubset(imports(new_text)):
            raise ValueError("existing privacy law import changed/removed; owner authorization required")
        old_main = git("show", head + ":" + PREFIX + "Main.bend").decode()
        new_main = (source / "Main.bend").read_text()
        if not imports(old_main).issubset(imports(new_main)):
            raise ValueError("existing exported policy import changed/removed; owner authorization required")
        for name, claim in old.items():
            if new.get(name) != claim:
                raise ValueError("existing privacy law changed/removed: " + name + "; owner authorization required")
        for name, definition in old_defs.items():
            if new_defs.get(name) != definition:
                raise ValueError("existing privacy requirement definition changed/removed: " + name +
                                 "; owner authorization required")
    env = dict(foreign_repo_env(os.environ), BEND_NO_TELEMETRY="1", GATE_TEST_ROOT=str(snapshot / "claude"))
    policy = any(p.startswith(PREFIX) or p == "claude/hooks/lib/privacy-decision.sh" for p in relevant)
    if policy:
        subprocess.run(["python3", str(source / "test-integration.py")], env=env, check=True)
    subprocess.run(["python3", str(snapshot / "claude/gates/tests/test-privacy-event.py")], env=env, check=True)
    subprocess.run(["bash", str(snapshot / "claude/gates/tests/test-privacy-gates.sh")], env=env, check=True)
    print("privacy-staged: proved/generated policy and staged regressions passed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo")
    parser.add_argument("--tree")
    parser.add_argument("--snapshot")
    parser.add_argument("--sources-only")
    try:
        main(parser.parse_args())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print("privacy commit blocked: " + str(error), file=sys.stderr)
        sys.exit(1)
