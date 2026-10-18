"""Automatic, proof-gated Bend selector; persistence stays in memo.

Builds are immutable snapshots. The extension exposes only the certified entry.
Bend's generated C ABI is private: this bridge deliberately pins 2.0.32.
"""

import fcntl
from _blake2 import blake2b
from importlib.machinery import EXTENSION_SUFFIXES, ExtensionFileLoader, ModuleSpec
import os
import re
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
ARTIFACTS = os.path.join(ROOT, ".local", "bend")
CURRENT = os.path.join(ARTIFACTS, "current-native")
SOURCES = ("selection.bend", "CONTRACT.bend", "certificate.bend", "RECOVERY.bend",
           "GEOMETRY.bend", "REFINE.bend", "RECOVERY_PROOF.bend", "PREFERENCE_CONTRACT.bend",
           "preference.bend", "PREFERENCE_PROOF.bend", "selection_cli.bend",
           "LAWS.bend", "PROOF.bend", "selection_native.c", "bend_selection.py",
           "BEND_TOOLCHAIN.json", "check_selection.py")
MAX_TOTAL = (1 << 32) - 1
MAX_BLOCKS = 65535
VERSION = "bend 2.0.32"
ABI = sys.implementation.cache_tag
EXTENSION_SUFFIX = EXTENSION_SUFFIXES[0]
_CACHE = {}


class SelectionError(RuntimeError):
    pass


def digest(path):
    with open(path, "rb") as source:
        return blake2b(source.read(), digest_size=32).hexdigest()


def source_hashes():
    return {name: digest(os.path.join(ROOT, name)) for name in SOURCES}


def _run(argv, cwd, log, timeout=120, env=None):
    import subprocess
    try:
        result = subprocess.run(argv, cwd=cwd, env=dict(env or os.environ, BEND_NO_TELEMETRY="1"),
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                timeout=timeout, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SelectionError("selector build failed: " + str(exc)) from exc
    with log.open("ab") as out:
        out.write(result.stdout)
    if result.returncode:
        raise SelectionError("selector proof/build rejected: " + result.stdout.decode("utf-8", "replace")[-2000:])
    return result.stdout.decode("utf-8", "replace")


def instrument(code):
    """Checked CPU boundary adaptations, never selection rewrites."""
    fail = '''static void err_fail(const char* msg) {
  fflush(stdout);
  fprintf(stderr, "bend: %s\\n", msg);
  _exit(1);
}'''
    room = '''#define WL_ROOM(N) \\
  if (DEVICE && sp + (N) * CUBE >= e.mem + STAT_OFF + CUBE) { \\
    err_post(e.mem, ERR_DEEP); \\
    return 0; \\
  }'''
    spin = "#define WL_OPEN    { WL_BANK u32 rn;"
    for fragment in (fail, room, spin):
        if code.count(fragment) != 1:
            raise SelectionError("pinned Bend runtime fragment changed; bridge review required")
    code = code.replace(fail, "static void err_fail(const char* msg) { bridge_fail(msg); }")
    code = code.replace(room, room + ''' \\
  if (!DEVICE && (size_t)(N) >= BRIDGE_STACK_WORDS - (size_t)(sp - io_stk)) { \\
    err_post(e.mem, ERR_DEEP); \\
    return 0; \\
  }''')
    code = code.replace(spin, spin + " bridge_step();")
    for name in ("FID_ENTRY_STATUS", "CID_SOME", "CID_NONE", "CID_SELECTION_END", "CID_SELECTION_MORE"):
        if not re.search(r"^#define " + name + r" [0-9]+$", code, re.M):
            raise SelectionError("pinned Bend entry/constructors changed")
    return code


def _build_locked(expected):
    import json
    from hashlib import sha256
    from pathlib import Path
    import shutil
    import sysconfig
    import uuid
    if sysconfig.get_config_var("Py_GIL_DISABLED"):
        raise SelectionError("the native boundary requires CPython with the GIL")
    generation = Path(ARTIFACTS) / "native" / uuid.uuid4().hex
    snapshot = generation / "source"
    snapshot.mkdir(parents=True)
    for name in SOURCES:
        shutil.copyfile(os.path.join(ROOT, name), snapshot / name)
    if expected != {name: digest(snapshot / name) for name in SOURCES}:
        raise SelectionError("sources changed while snapshotting; retry")
    from check_selection import git_text, preserve_requirements
    requirements = ["CONTRACT.bend", "LAWS.bend", "selection.bend", "PREFERENCE_CONTRACT.bend", "selection_cli.bend"]
    try:
        preserve_requirements({name: git_text("HEAD", name, False) for name in requirements},
                              {name: (snapshot / name).read_text() for name in requirements})
    except RuntimeError as exc:
        raise SelectionError(str(exc)) from exc
    for name in SOURCES:
        if name.endswith(".bend") and re.search(r"@unsafe|\?TODO|\?hole", (snapshot / name).read_text()):
            raise SelectionError("unsafe or unfinished Bend source: " + name)
        if name.endswith(".bend"):
            aliases = re.findall(r"^[ \t]*import[ \t]+[^\n]+[ \t]+as[ \t]+([A-Za-z0-9_]+)",
                                 (snapshot / name).read_text(), re.M)
            if len(aliases) != len(set(aliases)):
                raise SelectionError("duplicate Bend import binding: " + name)
            for target in re.findall(r"^[ \t]*import[ \t]+([^\s]+)", (snapshot / name).read_text(), re.M):
                if target != "Base" and target not in {"./" + p for p in SOURCES if p.endswith(".bend")}:
                    raise SelectionError("unfrozen Bend import: " + target)
    log = generation / "build.log"
    toolchain = json.loads((snapshot / "BEND_TOOLCHAIN.json").read_text())
    installed = Path(os.environ.get("BEND_HOME", str(Path.home() / ".bend")))
    # The 2.0.32 executable finds Base and BendTT relative to bin/bend.
    # Retain those exact inputs so a later installer cannot change a rebuild.
    retained = (Path(ARTIFACTS) / "native").glob("*/toolchain")
    candidates = (installed, *retained)
    compiler = next((p for p in candidates if all((p / n).is_file() and sha256((p / n).read_bytes()).hexdigest() == h
                    for n, h in toolchain["files"].items())), None)
    if compiler is None:
        raise SelectionError("pinned Bend 2.0.32 compiler unavailable; see BEND_SELECTION.md")
    frozen = generation / "toolchain"
    for name in toolchain["files"]:
        (frozen / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(compiler / name, frozen / name)
    if {n: sha256((frozen / n).read_bytes()).hexdigest() for n in toolchain["files"]} != toolchain["files"]:
        raise SelectionError("compiler changed during snapshot")
    bend_command = [str(frozen / "bin/bend")]
    version = _run(bend_command + ["version"], snapshot, log).strip()
    clang = _run(["clang", "--version"], snapshot, log).splitlines()[0]
    if version != VERSION or not re.search(r"clang version (?:1[6-9]|[2-9][0-9])\.", clang):
        raise SelectionError("requires " + VERSION + " and Clang >=16" + "; found " + version + ", " + clang)
    proof = _run(bend_command + ["PROOF.bend"], snapshot, log)
    if "ALL PROOFS CHECK" not in proof:
        raise SelectionError("proof gate did not report success")
    lean = shutil.which("lean") or str(Path.home() / ".elan/bin/lean")
    lean_version = _run([lean, "--version"], snapshot, log).strip()
    if lean_version != toolchain["lean_version"]:
        raise SelectionError("pinned Lean 4.34.0 unavailable for Bend verdict")
    verdict_env = dict(os.environ, PATH=str(Path(lean).parent) + os.pathsep + os.environ.get("PATH", ""))
    verdict_env.pop("BENDTT", None)
    verdict = _run(bend_command + ["PROOF.bend", "--verdict"], snapshot, log, env=verdict_env)
    if "ALL PROOFS CHECK" not in verdict:
        raise SelectionError("Bend kernel verdict did not report success")
    emitted = snapshot / "selection.original.c"
    _run(bend_command + ["selection_cli.bend", "-o", str(emitted)], snapshot, log)
    generated = snapshot / "selection.generated.c"
    generated.write_text(instrument(emitted.read_text()))
    binary = generation / ("_optmem_selection" + EXTENSION_SUFFIX)
    _run(["clang", "-O3", "-shared", "-fPIC", "-fvisibility=hidden", "-fno-strict-aliasing",
          "-I" + sysconfig.get_path("include"), str(snapshot / "selection_native.c"),
          "-o", str(binary), "-pthread", "-lm"], snapshot, log)
    smoke = """from importlib.machinery import ExtensionFileLoader, ModuleSpec
import sys
p=sys.argv[1]
l=ExtensionFileLoader('_optmem_selection',p)
m=l.create_module(ModuleSpec('_optmem_selection',l,origin=p));l.exec_module(m)
assert m.cover(0,1)==[]
assert m.cover(1,1)==[(0,1)]
assert m.cover(7,1)==[(0,4),(4,6),(6,7)]
assert m.cover(8,3)==[(0,4),(4,6),(6,8)]
assert m.cover_status(7,3)==(0,[(0,4),(4,6),(6,7)])
assert len(m.cover(4294967295,208))==208
assert len(m.cover(65535,65534))==65534
for t,b in [(False,1),(1,0),(4294967296,1),(65536,65536)]:
 try:m.cover(t,b)
 except (ValueError,OverflowError):pass
 else:raise AssertionError('bad input accepted')
print('Native ABI smoke passes.')
"""
    _run([sys.executable, "-c", smoke, str(binary)], snapshot, log, timeout=20)
    if source_hashes() != expected:
        raise SelectionError("sources changed during proof/build; retry")
    manifest = {"format": 2, "version": version, "clang": clang, "abi": ABI,
                "sources": expected, "binary_name": binary.name, "binary": digest(binary),
                "emitted": digest(emitted), "generated": digest(generated),
                "toolchain": toolchain}
    (generation / "manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    (generation / "receipt").write_text(_receipt(expected, binary.name, digest(binary)))
    staging = Path(ARTIFACTS) / (".current-native-" + generation.name)
    staging.symlink_to(Path("native") / generation.name, target_is_directory=True)
    os.replace(staging, CURRENT)
    return str(generation)


def _receipt(expected, name, binary_hash):
    return "\n".join(["2", VERSION, ABI, name] + [key + " " + expected[key] for key in SOURCES] + [binary_hash, ""])


def _checked(expected):
    try:
        generation = os.path.realpath(CURRENT, strict=True)
        name = "_optmem_selection" + EXTENSION_SUFFIX
        with open(os.path.join(generation, "receipt")) as source:
            receipt = source.read()
        if receipt != _receipt(expected, name, digest(os.path.join(generation, name))):
            return None
        return generation
    except (OSError, ValueError, TypeError):
        return None


def build(force=False):
    os.makedirs(ARTIFACTS, exist_ok=True)
    with open(os.path.join(ARTIFACTS, "native.lock"), "a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        expected = source_hashes()
        generation = None if force else _checked(expected)
        return generation or _build_locked(expected)


def checked_module():
    # Content digests on every public request also detect edits preserving mtime.
    expected = source_hashes()
    generation = _checked(expected) or build()
    # Resolve and hash exactly one immutable generation before loading it.
    if generation not in _CACHE:
        binary = os.path.join(generation, "_optmem_selection" + EXTENSION_SUFFIX)
        loader = ExtensionFileLoader("_optmem_selection", binary)
        module = loader.create_module(ModuleSpec("_optmem_selection", loader, origin=binary))
        loader.exec_module(module)
        _CACHE[generation] = module
    return _CACHE[generation]


def validate_request(total, budget):
    if type(total) is not int or not 0 <= total <= MAX_TOTAL:
        raise SelectionError("total must be an exact integer in 0..2^32-1")
    if type(budget) is not int or not 1 <= budget <= MAX_TOTAL:
        raise SelectionError("budget must be an exact integer in 1..2^32-1")
    if min(total, budget) > MAX_BLOCKS:
        raise SelectionError("selection resource limit: at most 65535 requested blocks")


def cover(total, budget):
    validate_request(total, budget)
    try:
        status, ranges = checked_module().cover_status(total, budget)
        if status:
            import warnings
            path = "fast" if status == 1 else "proved"
            warnings.warn("OptMem selector used certified " + path + " recovery; preferred candidate failed validation",
                          RuntimeWarning, stacklevel=2)
        return ranges
    except (ValueError, OverflowError, OSError, ImportError, RuntimeError, RuntimeWarning) as exc:
        raise SelectionError(str(exc)) from exc


def select_many(requests):
    return [cover(total, budget) for total, budget in requests]


if __name__ == "__main__":
    import subprocess
    if sys.argv[1:] not in (["--build"], ["--check"]):
        raise SystemExit("Usage: python3 bend_selection.py --build | --check")
    try:
        generation = build(force=True)
        print("Checked selector: " + str(generation))
        if sys.argv[1:] == ["--check"]:
            subprocess.run([sys.executable, os.path.join(ROOT, "check_selection.py")], cwd=ROOT, check=True)
    except (SelectionError, OSError, subprocess.SubprocessError) as exc:
        raise SystemExit(str(exc))
