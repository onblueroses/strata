#!/usr/bin/env python3
"""One verification entry; staged checks preserve existing requirements."""

import os
from pathlib import Path
import re
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent
FILES = ("memo", "selection.bend", "certificate.bend", "CONTRACT.bend", "RECOVERY.bend",
         "GEOMETRY.bend", "REFINE.bend", "RECOVERY_PROOF.bend", "PREFERENCE_CONTRACT.bend",
         "preference.bend", "PREFERENCE_PROOF.bend", "selection_cli.bend",
         "LAWS.bend", "PROOF.bend", "selection_native.c", "bend_selection.py",
         "BEND_TOOLCHAIN.json", "rational_reference.py", "objective_reference.py",
         "test_bend.py", "test.py", "check_selection.py")


def git_text(ref, name, required=True):
    result = subprocess.run(["git", "show", ref + ":" + name], cwd=ROOT, capture_output=True)
    if result.returncode:
        if required: raise RuntimeError("missing staged verification input: " + name)
        return None
    return result.stdout.decode()


def meaningful(text):
    return "\n".join(line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#"))


def claims(text):
    heads = list(re.finditer(r"^law ([A-Za-z0-9_]+):", text, re.M))
    return {head[1]: meaningful(text[head.start():heads[i+1].start() if i+1 < len(heads) else len(text)])
            for i, head in enumerate(heads)}


def definitions(text):
    heads = list(re.finditer(r"^def ([A-Za-z0-9_.]+)\(", text, re.M))
    return {head[1]: meaningful(text[head.start():heads[i+1].start() if i+1 < len(heads) else len(text)])
            for i, head in enumerate(heads)}


def semantic_blocks(text):
    heads = list(re.finditer(r"^(?:def|type|law) ([A-Za-z0-9_.]+)(?:\(| is|:)", text, re.M))
    return {head[1]: meaningful(text[head.start():heads[i+1].start() if i+1 < len(heads) else len(text)])
            for i, head in enumerate(heads)}


def preserve_imports(old, new):
    imports = lambda s: [line.split("#", 1)[0].strip() for line in
                         re.findall(r"^[ \t]*import[ \t]+[^\n]+", s, re.M)]
    before, after = imports(old), imports(new)
    bindings = [line.split()[-1] for line in after]
    if not set(before) <= set(after) or len(bindings) != len(set(bindings)):
        raise RuntimeError("requirement import binding changed or shadowed")


def preserve_requirements(old, new):
    if old["CONTRACT.bend"] is not None:
        before, after = definitions(old["CONTRACT.bend"]), definitions(new["CONTRACT.bend"])
        if any(after.get(name) != definition for name, definition in before.items()):
            raise RuntimeError("semantic CONTRACT changed; explicit requirement review needed")
        preserve_imports(old["CONTRACT.bend"], new["CONTRACT.bend"])
    if old["LAWS.bend"] is not None:
        before, after = claims(old["LAWS.bend"]), claims(new["LAWS.bend"])
        if not before.keys() <= after.keys():
            raise RuntimeError("existing named law removed")
        # The authorized first migration adds CONTRACT and strengthens the old
        # conservation trial. Once committed, semantic claims are frozen.
        if old["CONTRACT.bend"] is not None and any(after.get(name) != claim for name, claim in before.items()):
            raise RuntimeError("existing named law changed; explicit requirement review needed")
        if old["CONTRACT.bend"] is not None:
            preserve_imports(old["LAWS.bend"], new["LAWS.bend"])
    if old["selection.bend"] is not None:
        shape = lambda s: meaningful(re.search(r"type Chunks is Data:\n(?:  .*\n)+", s)[0])
        if shape(old["selection.bend"]) != shape(new["selection.bend"]):
            raise RuntimeError("contract chunk representation changed")
    if old.get("PREFERENCE_CONTRACT.bend") is not None:
        before, after = semantic_blocks(old["PREFERENCE_CONTRACT.bend"]), semantic_blocks(new["PREFERENCE_CONTRACT.bend"])
        if any(after.get(name) != block for name, block in before.items()):
            raise RuntimeError("semantic preference contract changed; explicit requirement review needed")
        preserve_imports(old["PREFERENCE_CONTRACT.bend"], new["PREFERENCE_CONTRACT.bend"])
    if old.get("selection_cli.bend") is not None:
        preserve_imports(old["selection_cli.bend"], new["selection_cli.bend"])


def run_checks(directory):
    env = dict(os.environ, OPTMEM_TELEMETRY="0")
    env.pop("OPTMEM_SELECTION", None)
    subprocess.run([sys.executable, "bend_selection.py", "--build"], cwd=directory, env=env, check=True)
    subprocess.run([sys.executable, "test_bend.py"], cwd=directory, env=env, check=True)
    fixtures = directory / ".local/test-fixtures"
    fixtures.mkdir(parents=True, exist_ok=True)
    env["TMPDIR"] = str(fixtures)
    # Preserve the existing suite's fixtures instead of removing them.
    code = "import shutil,runpy;shutil.rmtree=lambda *a,**k:None;runpy.run_path('test.py',run_name='__main__')"
    subprocess.run([sys.executable, "-c", code], cwd=directory, env=env, check=True)


def main():
    if sys.argv[1:] == ["--staged"]:
        tree = subprocess.run(["git", "write-tree"], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
        changed = subprocess.run(["git", "diff", "--name-only", "-z", "HEAD", tree], cwd=ROOT,
                                 capture_output=True, check=True).stdout.decode().split("\0")
        if not set(changed) & (set(FILES) | {".githooks/pre-commit"}):
            return
        staged = {name: git_text(tree, name) for name in FILES}
        entries = subprocess.run(["git", "ls-tree", "-z", tree, "--", *FILES], cwd=ROOT,
                                 capture_output=True, check=True).stdout.split(b"\0")
        modes = {}
        for entry in entries:
            if not entry: continue
            metadata, name = entry.split(b"\t", 1)
            mode, kind, _ = metadata.split()
            if mode not in (b"100644", b"100755") or kind != b"blob":
                raise RuntimeError("verification inputs must be regular files")
            modes[name.decode()] = int(mode, 8) & 0o777
        old = {name: git_text("HEAD", name, False) for name in
               ["CONTRACT.bend", "LAWS.bend", "selection.bend", "PREFERENCE_CONTRACT.bend", "selection_cli.bend"]}
        preserve_requirements(old, staged)
        snapshot = ROOT / ".local/bend/staged" / uuid.uuid4().hex
        snapshot.mkdir(parents=True)
        for name, code in staged.items():
            file = snapshot / name
            file.write_text(code)
            file.chmod(modes[name])
        subprocess.run([sys.executable, str(snapshot / "check_selection.py"), "--snapshot"], cwd=snapshot, check=True)
        final_tree = subprocess.run(["git", "write-tree"], cwd=ROOT, capture_output=True,
                                    text=True, check=True).stdout.strip()
        if final_tree != tree:
            raise RuntimeError("staging changed during verification; retry commit")
    elif sys.argv[1:] == ["--snapshot"]:
        run_checks(ROOT)
    elif not sys.argv[1:]:
        run_checks(ROOT)
        result = subprocess.run(["git", "config", "--local", "--get", "core.hooksPath"], cwd=ROOT, capture_output=True, text=True)
        if result.stdout.strip() not in ("", ".githooks"):
            raise RuntimeError("existing core.hooksPath needs integration: " + result.stdout.strip())
        subprocess.run(["git", "config", "--local", "core.hooksPath", ".githooks"], cwd=ROOT, check=True)
    else:
        raise RuntimeError("Usage: python3 check_selection.py [--staged | --snapshot]")


if __name__ == "__main__":
    try: main()
    except (RuntimeError, OSError, subprocess.SubprocessError) as exc: raise SystemExit(str(exc))
