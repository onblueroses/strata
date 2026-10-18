#!/usr/bin/env python3
"""Check finite shell/native equivalence, proof/freshness controls and real gate behavior."""
import argparse
import itertools
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "claude/hooks/privacy-decision"
(ROOT / "claude/.local/privacy-bend").mkdir(parents=True, exist_ok=True)
RIG = Path(tempfile.mkdtemp(prefix="table-tests-", dir=ROOT / "claude/.local/privacy-bend"))
ENV = dict(os.environ, BEND_NO_TELEMETRY="1")
COUNT = 0


def run(args, **kwargs):
    return subprocess.run(args, cwd=ROOT, text=True, capture_output=True, timeout=30, **kwargs)


def check(name, success, detail=""):
    global COUNT
    assert success, name + ": " + detail
    COUNT += 1


def shell(helper, function, *args):
    script = '''set -uo pipefail
refuse() { printf '%s\\n' "$2" >&2; exit 2; }
. "$1"; shift
f="$1"; shift
"$f" "$@"
case "$f" in privacy_plan) echo "$CLASSES" ;; privacy_target) echo "$PROVEN_PRIVATE" ;; *) echo "$PRIVACY_VERDICT" ;; esac
'''
    return run(["bash", "-c", script, "finite-test", str(helper), function, *map(str, args)])


def finite_controls(binary):
    helper = ROOT / "claude/hooks/lib/privacy-decision.sh"
    for op, function, states in (("p", "privacy_plan", itertools.product(range(2), repeat=3)),
                                ("f", "privacy_verdict", itertools.product(range(3), range(3), range(4))),
                                ("q", "privacy_target", itertools.product(range(2), repeat=2))):
        for state in states:
            request = op + ":" + ":".join(map(str, state))
            native = run([str(binary), "--threads", "1"], env=dict(ENV, PRIVACY_BEND_REQUEST=request))
            args = state if op != "f" else (("skip", "secrets", "all")[state[0]],
                                           ("none", "secrets", "all")[state[1]], state[2])
            generated = shell(helper, function, *args)
            check(request, native.returncode == generated.returncode == 0 and
                  native.stdout == generated.stdout and not generated.stderr, generated.stderr)
    for function, args in (("privacy_plan", ()), ("privacy_plan", (0, 1, 2)),
                           ("privacy_plan", (0, 1, 0, 0)), ("privacy_verdict", ("unknown", "all", 1)),
                           ("privacy_verdict", ("all", "none", 4)), ("privacy_target", (1, "private")),
                           ("privacy_target", (1,)), ("privacy_finish", ())):
        result = shell(helper, function, *args)
        check("invalid " + function, result.returncode == 2 and "BLOCKED" in result.stderr, result.stderr)
    for code, report, expected in ((0, "privacy-scan-v1:all", "allow"),
                                   (10, "privacy-scan-v1:all\nline 1 lit ***", "finding"),
                                   (0, "privacy-scan-v1:secrets", "failure"),
                                   (0, "", "failure"), (3, "privacy-scan-v1:all", "failure"),
                                   (124, "privacy-scan-v1:all", "failure"),
                                   (137, "privacy-scan-v1:all", "failure")):
        script = f'CLASSES=all; . "{helper}"; privacy_finish "$1" "$2"; echo "$PRIVACY_VERDICT"'
        result = run(["bash", "-c", script, "finite-test", str(code), report])
        check("scan-status " + str(code) + "/" + report[:20], result.returncode == 0 and
              result.stdout.strip() == expected)
    for plan, coverage, outcome, expected in (("all", "secrets", 1, "failure"),
                                              ("secrets", "all", 1, "failure"),
                                              ("all", "none", 1, "failure"),
                                              ("secrets", "none", 1, "failure"),
                                              ("all", "all", 1, "allow"),
                                              ("secrets", "secrets", 1, "allow")):
        result = shell(helper, "privacy_verdict", plan, coverage, outcome)
        check("independent evidence " + plan + "/" + coverage,
              result.returncode == 0 and result.stdout.strip() == expected)


def proof_controls():
    original = (SOURCE / "Policy.bend").read_text()
    # Equivalent implementation change: move the unproven branch before the private branch.
    private = "    case False{} True{} Private{}:\n      Secrets{}\n"
    unknown = "    case False{} True{} Unproven{}:\n      All{}\n"
    changes = (
        ("equivalent", original.replace(private + unknown, unknown + private) if private + unknown in original
         else original.replace(unknown + private, private + unknown), True),
        ("unknown-skips", original.replace(unknown, unknown.replace("All{}", "Skip{}")), False),
        ("clean-unknown-denied", original.replace("case All{} AllEvidence{Clean{}}:\n      Allow{}", "case All{} AllEvidence{Clean{}}:\n      DenyFailure{}"), False),
        ("private-secret-allowed", original.replace("case Secrets{} SecretsEvidence{Findings{}}:\n      DenyFinding{}", "case Secrets{} SecretsEvidence{Findings{}}:\n      Allow{}"), False),
        ("uncertainty-forgotten", original.replace("    case _ _:\n      Unproven{}", "    case Unproven{} Private{}:\n      Private{}\n    case _ _:\n      Unproven{}"), False),
        ("all-private-denied", original.replace("case Private{} Private{}:\n      Private{}", "case Private{} Private{}:\n      Unproven{}"), False),
    )
    for name, code, expected in changes:
        check(name + " changes code", code != original)
        directory = RIG / name
        directory.mkdir()
        for file in ("Policy.bend", "LAWS.bend", "PROOF.bend"):
            shutil.copyfile(SOURCE / file, directory / file)
        (directory / "Policy.bend").write_text(code)
        result = run(["bend", str(directory / "PROOF.bend")], env=ENV)
        (directory / "checker.txt").write_text(result.stdout + result.stderr)
        check(name, (result.returncode == 0) == expected, result.stdout + result.stderr)
    # The review's exact mutation: list aggregation stays correct but the operation
    # exported to the generated table always says Private. It passed the old 11 laws.
    fold = """def fold(state: Visibility, target: Visibility) -> Visibility:
  match state target:
    case Private{} Private{}:
      Private{}
    case _ _:
      Unproven{}
"""
    mutant = original.replace(fold, """def fold(state: Visibility, target: Visibility) -> Visibility:
  Private{}

""" + fold.replace("def fold(", "def original_fold(", 1))
    mutant = mutant.replace("targets(t, fold(state, h))", "targets(t, original_fold(state, h))")
    check("decoupled exported fold changes source", mutant != original and "original_fold(state, h)" in mutant)
    directory = RIG / "decoupled-fold"
    directory.mkdir()
    (directory / "Policy.bend").write_text(mutant)
    for file in ("LAWS.bend", "PROOF.bend"):
        shutil.copyfile(SOURCE / file, directory / file)
    result = run(["bend", str(directory / "PROOF.bend")], env=ENV)
    (directory / "checker.txt").write_text(result.stdout + result.stderr)
    check("decoupled exported fold rejected", result.returncode != 0 and
          "fold_private_unproven" in result.stdout + result.stderr, result.stdout + result.stderr)


def wiring_control(binary):
    request = "f:2:1:1"  # All requested, secrets-only clean evidence: must refuse.
    result = run([str(binary), "--threads", "1"], env=dict(ENV, PRIVACY_BEND_REQUEST=request))
    check("native exported finish refuses undercoverage",
          result.returncode == 0 and result.stdout.strip() == "failure", result.stdout + result.stderr)
    directory = RIG / "miswired-main"
    directory.mkdir()
    for file in ("Main.bend", "Policy.bend"):
        shutil.copyfile(SOURCE / file, directory / file)
    main = (directory / "Main.bend").read_text()
    altered = main.replace("evidence : P.Evidence <- read_evidence(c, scan)\n        return show_verdict(P.checked_finish(plan, evidence))",
                           "return show_verdict(P.finish(plan, scan))")
    check("miswired Main changes source", altered != main)
    (directory / "Main.bend").write_text(altered)
    compiled = run(["bend", str(directory / "Main.bend"), "-o", str(directory / "decision")], env=ENV)
    check("miswired Main compiles", compiled.returncode == 0, compiled.stdout + compiled.stderr)
    bad = run([str(directory / "decision"), "--threads", "1"],
              env=dict(ENV, PRIVACY_BEND_REQUEST=request))
    check("independent finish control catches miswire", bad.returncode == 0 and
          bad.stdout.strip() != "failure", bad.stdout + bad.stderr)


def freshness_control(binary):
    directory = RIG / "freshness"
    (directory / "privacy-decision").mkdir(parents=True)
    (directory / "lib").mkdir()
    for file in ("generate.py", "Policy.bend", "LAWS.bend", "PROOF.bend", "Main.bend"):
        shutil.copyfile(SOURCE / file, directory / "privacy-decision" / file)
    table = directory / "lib/privacy-decision.sh"
    shutil.copyfile(ROOT / "claude/hooks/lib/privacy-decision.sh", table)
    command = ["python3", str(directory / "privacy-decision/generate.py"), "--binary", str(binary), "--check"]
    check("freshness positive", run(command).returncode == 0)
    table.write_text(table.read_text().replace("CLASSES=all", "CLASSES=skip"))
    result = run(command)
    check("stale table refused", result.returncode != 0 and "stale" in result.stderr)


def gate_controls(before):
    home = RIG / "home"
    bindir = RIG / "bin"
    for path in (".claude/config", ".claude/hooks/lib", ".claude/telemetry"):
        (home / path).mkdir(parents=True, exist_ok=True)
    bindir.mkdir()
    (home / ".claude/config/private-tokens.txt").write_text("lit Acme Widgets\n")
    for file in ("run-gates.sh", "lib/privacy-scan.py"):
        shutil.copyfile(ROOT / "claude/hooks" / file, home / ".claude/hooks" / file)
    (home / ".claude/telemetry/telemetry-emit.sh").write_text("exit 0\n")
    (bindir / "gh").write_text('#!/usr/bin/env bash\nfor a in "$@"; do case "$a" in *privately-held*) echo PRIVATE; exit 0 ;; esac; done\nexit 1\n')
    (bindir / "gh").chmod(0o755)
    env = dict(ENV, HOME=str(home), PATH=str(bindir) + ":" + os.environ["PATH"], PRIVACY_DECISION_ENGINE="shell")

    def gate(command, script=ROOT / "claude/hooks/gate-gh-public-actions.sh"):
        event = json.dumps({"session_id": "privacy-table-test", "cwd": str(RIG), "tool_input": {"command": command}})
        return run(["bash", str(script)], env=env, input=event)

    secret = "ghp_" + "A" * 36
    for command, status in (("gh issue create --repo unknown/repo --body generic", 0),
                            ("gh issue create --repo unknown/repo --body 'Acme Widgets'", 2),
                            ("gh issue create --repo privately-held/repo --body 'Acme Widgets'", 0),
                            (f"gh issue create --repo privately-held/repo --body '{secret}'", 2),
                            ("PRIVACY_ACK=1 gh issue create --body 'Acme Widgets'", 0)):
        result = gate(command)
        check("gate policy", result.returncode == status, result.stderr)
    gh = bindir / "gh"
    original = gh.read_text()
    gh.write_text("#!/usr/bin/env bash\necho PRIVATE\nexit 1\n")
    for command, status in (("gh issue create --repo unknown/repo --body 'Acme Widgets'", 2),
                            ("gh issue create --body 'Acme Widgets'", 2),
                            ("gh issue create --repo unknown/repo --body generic", 0)):
        result = gate(command)
        check("failed lookup is unproven", result.returncode == status, result.stderr)
    gh.write_text(original)
    # The actual Codex dispatcher invokes both real gates under their production budgets.
    body = RIG / "dispatch body.md"
    body.write_text("Acme Widgets\n")
    for command, status in (("gh --repo unknown/repo issue create --body generic", 0),
                            ("gh --repo unknown/repo issue create --body 'Acme Widgets'", 2),
                            (f"gh issue create --body-file '{body}'", 2),
                            ("gh issue create --body bad\x00payload", 2),
                            ("git push --dry-run origin main", 0),
                            ("git push --dry-run origin main && git push origin main", 2)):
        event = json.dumps({"cwd": str(RIG), "tool_input": {"command": command}})
        result = run(["python3", str(ROOT / "codex/hooks/pre_tool_use.py")], input=event,
                     env=dict(env, CODEX_PRIVACY_GATE=str(ROOT / "claude/hooks")))
        check("real Codex dispatch", result.returncode == status, result.stderr)
    missing = RIG / "missing-helper"
    missing.mkdir()
    (missing / "lib").mkdir()
    shutil.copyfile(ROOT / "claude/hooks/lib/privacy-event.py", missing / "lib/privacy-event.py")
    for file, command in (("gate-gh-public-actions.sh", "gh issue create --body generic"), ("gate-pre-push.sh", "git push")):
        shutil.copyfile(ROOT / "claude/hooks" / file, missing / file)
        result = gate(command, missing / file)
        check("missing-helper " + file, result.returncode == 2 and "could not be loaded" in result.stderr, result.stderr)
    (missing / "lib/privacy-decision.sh").write_text("")
    for command in ("gh issue create --body generic", "PRIVACY_ACK=1 gh issue create --body generic"):
        result = gate(command, missing / "gate-gh-public-actions.sh")
        check("incomplete helper refuses", result.returncode == 2 and "incomplete" in result.stderr, result.stderr)
    (missing / "lib/privacy-decision.sh").write_text("privacy_plan() { :; }; privacy_target() { :; }; privacy_finish() { :; }\n")
    result = gate("PRIVACY_ACK=1 gh issue create --body generic", missing / "gate-gh-public-actions.sh")
    check("partial helper refuses", result.returncode == 2 and "incomplete" in result.stderr, result.stderr)
    shutil.copyfile(ROOT / "claude/hooks/lib/privacy-decision.sh", missing / "lib/privacy-decision.sh")
    for name, payload, status in (("missing-header", b"", 0),
                                 ("partial", b"privacy-event-v2\x002\x00", 0),
                                 ("wrong-count", b"privacy-event-v2\x000\x00gh issue create\x00.\x00s\x00extra\x00", 0),
                                 ("producer-failed", b"privacy-event-v2\x000\x00gh issue create\x00.\x00s\x00", 3),
                                 ("invalid-metadata", b"privacy-event-v2\x001\x00gh issue create\x00.\x00s\x00gh\x004\x00", 0),
                                 ("status-not-token", b"privacy-event-v2\x000\x00gh issue create\x00.\x00s\x000\x00", 0)):
        (missing / "lib/privacy-event.py").write_text(f"import sys\nsys.stdout.buffer.write({payload!r})\nsys.exit({status})\n")
        for file, command in (("gate-gh-public-actions.sh", "gh issue create --body generic"),
                              ("gate-pre-push.sh", "git push")):
            result = gate(command, missing / file)
            check("event " + name + " " + file, result.returncode == 2 and "privacy decision" in result.stderr, result.stderr)
    measurements = {}
    candidates = [("generated", ROOT / "claude/hooks/gate-gh-public-actions.sh")]
    if before:
        candidates.insert(0, ("before", Path(before).resolve() / "gate-gh-public-actions.sh"))
    samples = {label: [] for label, _ in candidates}
    # Interleave versions to reduce machine-load drift between before/after batches.
    for _ in range(20):
        for label, script in candidates:
            start = time.perf_counter()
            result = gate("gh issue create --repo unknown/repo --body generic", script)
            check("timing positive " + label, result.returncode == 0, result.stderr)
            samples[label].append((time.perf_counter() - start) * 1000)
    for label, values in samples.items():
        measurements[label] = {"median_ms": statistics.median(values), "max_ms": max(values)}
    (RIG / "performance.json").write_text(json.dumps(measurements, indent=2) + "\n")
    print("whole-gate measurements:", json.dumps(measurements))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", help="saved pre-change gates directory for timing comparison")
    args = parser.parse_args()
    result = run(["bash", str(SOURCE / "build.sh"), "--check"], env=ENV)
    check("native proof and generation freshness", result.returncode == 0, result.stdout + result.stderr)
    binary = Path(result.stdout.strip().split("privacy table build: ")[-1]) / "decision"
    finite_controls(binary)
    proof_controls()
    wiring_control(binary)
    freshness_control(binary)
    gate_controls(args.before)
    print(f"privacy-table-integration: {COUNT} checks passed; artifacts: {RIG}")
