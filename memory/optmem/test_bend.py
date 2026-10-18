#!/usr/bin/env python3
"""Synthetic proof, parity, native boundary, lifecycle and integration checks."""

import concurrent.futures
from hashlib import sha256
from importlib.machinery import SourceFileLoader
import json
import os
from pathlib import Path
import random
import re
import signal
import statistics
import subprocess
import sys
import time
import unittest
import uuid
import warnings
from unittest.mock import patch

import bend_selection as bend
import objective_reference
import rational_reference

ROOT = Path(__file__).resolve().parent
memo = SourceFileLoader("memo_bend_test", str(ROOT / "memo")).load_module()


def fixture(total=5324, budget=30):
    store = ROOT / ".local/bend/fixtures" / uuid.uuid4().hex
    (store / "TREE").mkdir(parents=True)
    (store / "LOG.txt").write_bytes(b"".join(
        memo.pad("#%d 2026-01-01 synthetic memory %d" % (i, i), memo.LOG_REC)
        for i in range(total)))
    depth = 1
    while 1 << depth <= total:
        width = 1 << depth
        (store / "TREE" / str(width)).write_bytes(b"".join(
            memo.pad("synthetic summary %d/%d" % (width, i), memo.TREE_REC)
            for i in range(total // width)))
        depth += 1
    (store / "config").write_text("WAKE_LINES=%d\n" % budget)
    return store


def cli(store, backend=None):
    env = dict(os.environ, MEMORY_DIR=str(store), OPTMEM_TELEMETRY="0")
    env.pop("OPTMEM_SELECTION", None)
    if backend:
        env["OPTMEM_SELECTION"] = backend
    return subprocess.run([sys.executable, str(ROOT / "memo"), "wake"], env=env,
                          capture_output=True, timeout=20)


class BendSelectionTest(unittest.TestCase):
    def test_differential(self):
        cases = [(t, b) for t in range(1, 257) for b in range(1, min(t + 1, 41))]
        rng = random.Random(7)
        cases += [(rng.randint(257, bend.MAX_TOTAL), rng.choice([1, 2, 8, 16, 30, 64, 208, 512]))
                  for _ in range(300)]
        cases += [(t, b) for d in range(9, 32) for t in [(1 << d)-1, 1 << d, (1 << d)+1]
                  for b in [1, 2, 30, 208]]
        cases += [(0, 1), (5324, 30), (65535, 1001), (65535, 10000),
                  (65535, 65534), (65535, 65535), (1, bend.MAX_TOTAL),
                  (bend.MAX_TOTAL, 1000), (bend.MAX_TOTAL, 208)]
        for total, budget in cases:
            self.assertEqual(bend.cover(total, budget), memo.cover_python(total, budget), (total, budget))
        print("\n%d original-Python/certified-native cases agree" % len(cases))

    def test_independent_quality_oracles(self):
        module = bend.checked_module()
        for total in range(257):
            for budget in range(1, min(total + 1, 21)):
                status, ranges = module.cover_status(total, budget)
                self.assertEqual(status, 0, (total, budget))
                self.assertEqual(ranges, rational_reference.select(total, budget), (total, budget))
        for total in range(1, 49):
            best = {}
            for widths in objective_reference.partitions(total, total.bit_length()-1):
                candidate = objective_reference.score(total, widths)
                if len(widths) not in best or candidate < best[len(widths)][0]:
                    best[len(widths)] = (candidate, widths)
            for budget, (_, expected) in best.items():
                status, ranges = module.cover_status(total, budget)
                self.assertEqual(status, 0, (total, budget))
                self.assertEqual(tuple(hi-lo for lo, hi in ranges), expected, (total, budget))
        self.assertNotEqual(rational_reference.select(24, 11), rational_reference.select(24, 12)[:11])

    def test_status_and_warning(self):
        module = bend.checked_module()
        self.assertEqual(module.cover_status(9, 6)[0], 0)
        self.assertEqual(module.cover_status(9, 6)[1], rational_reference.select(9, 6))
        class Recovered:
            def cover_status(self, total, budget):
                return 1, [(0, 4), (4, 6), (6, 7)]
        with patch.object(bend, "checked_module", return_value=Recovered()), \
             warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter("always")
            self.assertEqual(bend.cover(7, 3), [(0, 4), (4, 6), (6, 7)])
            self.assertEqual(len(seen), 1)
            self.assertIn("certified fast recovery", str(seen[0].message))
        with patch.object(bend, "checked_module", return_value=Recovered()), \
             warnings.catch_warnings():
            warnings.simplefilter("error", RuntimeWarning)
            with self.assertRaisesRegex(bend.SelectionError, "certified fast recovery"):
                bend.cover(7, 3)

    def test_budget_and_bounds(self):
        self.assertEqual(bend.cover(7, 1), [(0, 4), (4, 6), (6, 7)])
        self.assertEqual(bend.cover(0, 1), [])
        for t, b in [(-1, 1), (1 << 32, 1), (True, 1), (False, 1), (0.0, 1),
                     (1, 0), (1, 1 << 32), (1, 1.5), (65536, 65536)]:
            with self.assertRaises(bend.SelectionError): bend.cover(t, b)
            with self.assertRaises((ValueError, OverflowError, TypeError)):
                bend.checked_module().cover(t, b)

    def test_real_cli_default(self):
        store = fixture()
        before = {p: p.read_bytes() for p in store.rglob("*") if p.is_file()}
        recovery, default = cli(store, "python"), cli(store)
        self.assertEqual(default.returncode, 0, default.stderr)
        self.assertEqual(recovery.stdout, default.stdout)
        self.assertEqual(before, {p: p.read_bytes() for p in store.rglob("*") if p.is_file()})
        with patch.object(bend, "checked_module", side_effect=bend.SelectionError("rejected")):
            with self.assertRaises(bend.SelectionError): bend.cover(5324, 30)

    def test_proof_controls(self):
        generation = bend.build()
        compiler = Path(generation) / "toolchain/bin/bend"
        base = {name: (ROOT / name).read_text() for name in bend.SOURCES if name.endswith(".bend")}
        selection_proof = re.search(r"def Laws.selection_conserves\([^\n]+\):\n.*?(?=\ndef Laws.raw_stays)",
                                    base["PROOF.bend"], re.S).group()
        mutations = [
            {"certificate.bend": ("    case True{}:\n      Some{xs}", "    case True{}:\n      None{}")},
            {"certificate.bend": ("    case False{}:\n      None{}", "    case False{}:\n      Some{xs}")},
            {"certificate.bend": ("Nat.is_eq(Nat.mod(lo, w), 0n)", "True{}")},
            {"certificate.bend": ("Nat.is_eq(lo, total)", "True{}")},
            {"selection_cli.bend": ("C.certify(result, U32.to_nat(total), U32.to_nat(budget))", "None{}")},
            {"RECOVERY.bend": ("append_raw(scale(seed_word(p, tail)))", "scale(seed_word(p, tail))")},
            {"selection_cli.bend": ("(1,Some{xs})", "(3,Some{xs})")},
            {"selection.bend": ('''def choose(+root: Nat, fuel: Nat, +budget: Nat, +total: U32, +xs: Chunks) -> Chunks:
  +base = U32.from_nat(length(xs))
  +b = U32.from_nat(budget)
  branch(Chunks, U32.is_le(b, base), u => xs, u => (
    +q = find_q(root, fuel, 0, b, total, base, b)
    finish_target(q, total, budget, xs,
      find_fraction(root, root, total, q, base, b, None{}))))''',
                                '''def choose(+root: Nat, fuel: Nat, +budget: Nat, +total: U32, +xs: Chunks) -> Chunks:
  xs'''),
             "PROOF.bend": (selection_proof, "def Laws.selection_conserves(root, fuel, budget, total, xs):\n  {==}\n")},
            {"preference.bend": ("check_witness(P.worst(xs,total),xs,total,target)", "True{}")},
            {"preference.bend": ("check_witness(P.worst(xs,total),xs,total,target)", "False{}"),
             "PREFERENCE_PROOF.bend": ("witness_sound(P.worst(xs,total),xs,total,target,checked)",
                                       "absurd(P.Preferred(xs,total,target),false_true(checked))")},
        ]
        for i, change in enumerate([None] + mutations):
            snapshot = ROOT / ".local/bend/proof-controls" / uuid.uuid4().hex
            snapshot.mkdir(parents=True)
            for name, code in base.items():
                if change and name in change:
                    old, new = change[name]
                    self.assertIn(old, code)
                    code = code.replace(old, new)
                (snapshot / name).write_text(code)
            result = subprocess.run([str(compiler), "PROOF.bend"], cwd=snapshot,
                                    env=dict(os.environ, BEND_NO_TELEMETRY="1"),
                                    capture_output=True, timeout=20)
            self.assertEqual(result.returncode == 0, i == 0, result.stdout[-500:])
            if i == 0:
                self.assertIn(b"ALL PROOFS CHECK", result.stdout)
                verdict_env = dict(os.environ, BEND_NO_TELEMETRY="1",
                                   PATH=str(Path.home() / ".elan/bin") + os.pathsep + os.environ["PATH"])
                verdict_env.pop("BENDTT", None)
                verdict = subprocess.run([str(compiler), "PROOF.bend", "--verdict"], cwd=snapshot,
                                         env=verdict_env,
                                         capture_output=True, timeout=20)
                self.assertEqual(verdict.returncode, 0, verdict.stderr)
                self.assertIn(b"ALL PROOFS CHECK", verdict.stdout)

    def test_threads_signals_and_allocator(self):
        module = bend.checked_module()
        before = {s: signal.getsignal(s) for s in [signal.SIGSEGV, signal.SIGBUS, signal.SIGPIPE]}
        expected = memo.cover_python(5324, 30)
        module.cover(5324, 30)
        warm_pages = module._stats()[1]
        for _ in range(2000): self.assertEqual(module.cover(5324, 30), expected)
        self.assertEqual(module._stats()[1], warm_pages)
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            self.assertTrue(all(x == expected for x in pool.map(lambda _: module.cover(5324, 30), range(80))))
        self.assertEqual(before, {s: signal.getsignal(s) for s in before})
        pid = os.fork()
        if pid == 0:
            okay = module.cover(5324, 30) == expected and module._stats()[0] == os.getpid()
            os._exit(0 if okay else 1)
        self.assertEqual(os.waitpid(pid, 0)[1], 0)
        self.assertEqual(module._stats()[0], os.getpid())

    def test_immutable_pin_and_stale(self):
        generation = bend.build()
        expected = bend.source_hashes()
        self.assertEqual(bend._checked(expected), generation)
        bad = dict(expected, **{"selection.bend": "changed"})
        self.assertIsNone(bend._checked(bad))
        # Changing current after resolution cannot alter an already loaded module.
        module = bend.checked_module()
        with patch.object(bend, "CURRENT", ROOT / ".local/bend/no-such-current"), \
             patch.object(bend, "build", return_value=generation):
            self.assertIs(bend.checked_module(), module)
        with patch.object(bend, "digest", return_value="corrupted"):
            self.assertIsNone(bend._checked(expected))
        with self.assertRaises(bend.SelectionError): bend.instrument("unexpected runtime")

    def test_retained_compiler_rebuild(self):
        with patch.dict(os.environ, {"BEND_HOME": str(ROOT / ".local/bend/no-installed-compiler"),
                                          "BENDTT": "/bin/false"}):
            generation = Path(bend.build(force=True))
        pinned = json.loads((ROOT / "BEND_TOOLCHAIN.json").read_text())
        for name, expected in pinned["files"].items():
            self.assertEqual(sha256((generation / "toolchain" / name).read_bytes()).hexdigest(), expected)
        self.assertEqual(json.loads((generation / "manifest.json").read_text())["version"], pinned["version"])
        self.assertEqual(bend.checked_module().cover_status(7, 3),
                         (0, [(0, 4), (4, 6), (6, 7)]))

    def test_requirement_guard(self):
        from check_selection import preserve_requirements
        old = {name: (ROOT / name).read_text() for name in
               ["CONTRACT.bend", "LAWS.bend", "selection.bend", "PREFERENCE_CONTRACT.bend", "selection_cli.bend"]}
        preserve_requirements(old, old)
        added = dict(old, **{"LAWS.bend": old["LAWS.bend"] + "\nlaw new_requirement:\n  Unit\n"})
        preserve_requirements(old, added)
        expanded = dict(old, **{"CONTRACT.bend": old["CONTRACT.bend"] + "\ndef NewRule() -> Type:\n  Unit\n"})
        preserve_requirements(old, expanded)
        for filename, needle, replacement in [
                ("CONTRACT.bend", "Le(d, 31n)", "Unit"),
                ("LAWS.bend", "K.Contract(xs, total, budget)", "Unit"),
                ("LAWS.bend", "import ./CONTRACT.bend as K", "import ./certificate.bend as K"),
                ("selection.bend", "depth: Nat", "depth: U32"),
                ("PREFERENCE_CONTRACT.bend", "Nat.is_eq", "Nat.is_le"),
                ("selection_cli.bend", "import ./preference.bend as V", "import ./selection.bend as V")]:
            changed = dict(old, **{filename: old[filename].replace(needle, replacement)})
            with self.assertRaises(RuntimeError): preserve_requirements(old, changed)

    def test_automatic_source_proof_and_failed_publish(self):
        snapshot = ROOT / ".local/bend/autobuild-controls" / uuid.uuid4().hex
        snapshot.mkdir(parents=True)
        for name in bend.SOURCES: (snapshot / name).write_bytes((ROOT / name).read_bytes())
        artifacts = snapshot / ".local/bend"
        current = artifacts / "current-native"
        with patch.object(bend, "ROOT", str(snapshot)), patch.object(bend, "ARTIFACTS", str(artifacts)), \
             patch.object(bend, "CURRENT", str(current)):
            self.assertEqual(bend.cover(7, 1), [(0, 4), (4, 6), (6, 7)])
            original_generation = current.resolve()
            file = snapshot / "certificate.bend"
            source = file.read_text()
            stamp = file.stat()
            file.write_text(source.replace("    case True{}:\n      Some{xs}", "    case True{}:\n      None{}"))
            os.utime(file, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
            with self.assertRaises(bend.SelectionError): bend.cover(7, 1)
            self.assertEqual(current.resolve(), original_generation)
            file.write_text(source + "\n# @unsafe is forbidden even in a new build input.\n")
            with self.assertRaisesRegex(bend.SelectionError, "unsafe"): bend.cover(7, 1)
            self.assertEqual(current.resolve(), original_generation)
            file.write_text(source + "\n  import ../escape.bend as Escape\n")
            with self.assertRaisesRegex(bend.SelectionError, "unfrozen"): bend.cover(7, 1)
            self.assertEqual(current.resolve(), original_generation)
            file.write_text(source)
            self.assertEqual(bend.cover(7, 1), [(0, 4), (4, 6), (6, 7)])

    def test_memory_refusal_and_signal_delivery(self):
        generation = bend.build()
        binary = str(Path(generation) / ("_optmem_selection" + bend.EXTENSION_SUFFIX))
        prefix = '''from importlib.machinery import ExtensionFileLoader,ModuleSpec
import sys
l=ExtensionFileLoader('_optmem_selection',sys.argv[1])
m=l.create_module(ModuleSpec('_optmem_selection',l,origin=sys.argv[1]));l.exec_module(m)
'''
        cases = [prefix + '''import resource
resource.setrlimit(resource.RLIMIT_AS,(128<<20,128<<20))
try:m.cover(5324,30)
except OSError:pass
else:raise AssertionError('reservation did not refuse')
assert m._stats()==(0,0)
''', prefix + '''import signal
def stop(*args):raise KeyboardInterrupt
signal.signal(signal.SIGALRM,stop)
signal.setitimer(signal.ITIMER_REAL,.001)
try:m.cover(65535,65534)
except KeyboardInterrupt:pass
else:raise AssertionError('pending signal not delivered')
signal.setitimer(signal.ITIMER_REAL,0)
assert m.cover(1,1)==[(0,1)]
''', prefix + '''import signal
seen=[]
def nested(*args):
 try:m.cover(1,1)
 except RuntimeError as error:
  assert 'recursive' in str(error)
  seen.append(True)
 else:raise AssertionError('nested selector call was accepted')
 raise KeyboardInterrupt
signal.signal(signal.SIGALRM,nested)
signal.setitimer(signal.ITIMER_REAL,.001)
try:m.cover(2147483648,65535)
except KeyboardInterrupt:pass
else:raise AssertionError('interrupt was lost')
signal.setitimer(signal.ITIMER_REAL,0)
assert seen
assert m.cover(1,1)==[(0,1)]
''']
        for script in cases:
            result = subprocess.run([sys.executable, "-c", script, binary], capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)


def benchmark():
    bend.cover(5324, 30)
    for total, budget in [(5324, 30), (5318, 208), (1_000_000, 208), (bend.MAX_TOTAL, 208)]:
        native, python = [], []
        for _ in range(60):
            start = time.perf_counter_ns(); bend.cover(total, budget)
            native.append((time.perf_counter_ns()-start)/1e6)
            start = time.perf_counter_ns(); memo.cover_python(total, budget)
            python.append((time.perf_counter_ns()-start)/1e6)
        print("full adapter %d/%d: native %.3fms, Python %.3fms" %
              (total, budget, statistics.median(native), statistics.median(python)))
    for budget in [30, 208]:
        store = fixture(5324, budget)
        samples = {"python": [], "default": []}
        output = None
        for i in range(40):
            for backend in (["python", "default"] if i % 2 else ["default", "python"]):
                start = time.perf_counter_ns(); result = cli(store, "python" if backend == "python" else None)
                samples[backend].append((time.perf_counter_ns()-start)/1e6)
                if result.returncode: raise RuntimeError(result.stderr)
                if output is None: output = result.stdout
                assert result.stdout == output
        print("whole cold memo wake 5324/%d (%d output bytes): Python %.3fms, default %.3fms" %
              (budget, len(output), statistics.median(samples["python"]), statistics.median(samples["default"])))


if __name__ == "__main__":
    if sys.argv[1:] == ["--benchmark"]: benchmark()
    else: unittest.main()
