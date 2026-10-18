#!/usr/bin/env python3
"""Real-index controls for automatic privacy checks and atomic proof/table builds."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[3]
P = "claude/hooks/privacy-decision/"
ARTIFACTS = ROOT / "claude/.local/privacy-bend"
ARTIFACTS.mkdir(parents=True, exist_ok=True)
RIG = Path(tempfile.mkdtemp(prefix="staged-controls-", dir=ARTIFACTS))
ENV = dict(os.environ, BEND_NO_TELEMETRY="1")
ENV.pop("PRIVACY_REQUIREMENTS_ACK", None)
COUNT = 0


def run(*args, root=RIG, **kwargs):
    return subprocess.run(args, cwd=root, env=kwargs.pop("env", ENV), text=True,
                          capture_output=True, timeout=60, **kwargs)


def check(name, success, detail=""):
    global COUNT
    assert success, name + ": " + detail
    COUNT += 1


def git(*args):
    result = run("git", *args)
    assert result.returncode == 0, result.stderr
    return result.stdout


paths = ["claude/hooks/gate-gh-public-actions.sh", "claude/hooks/gate-pre-push.sh", "claude/hooks/run-gates.sh",
         "claude/hooks/lib/privacy-decision.sh", "claude/hooks/lib/privacy-event.py", "claude/hooks/lib/privacy-scan.py",
         "claude/gates/tests/test-privacy-gates.sh", "claude/gates/tests/test-privacy-event.py", "codex/hooks/pre_tool_use.py"]
paths += [str(p.relative_to(ROOT)) for p in (ROOT / P).iterdir() if p.suffix in (".bend", ".py", ".sh")]
for path in paths:
    target = RIG / path
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(ROOT / path, target)
git("init", "-q")
git("config", "user.name", "Privacy Fixture")
git("config", "user.email", "example.test")
git("add", "claude", "codex")
git("-c", "core.hooksPath=/dev/null", "commit", "-qm", "Initialize generic privacy fixture")
checker = RIG / P / "check-staged.py"


def verify(name, expected, reason=""):
    result = run("python3", str(checker), "--repo", str(RIG))
    (RIG / (name + ".txt")).write_text(result.stdout + result.stderr)
    check(name, (result.returncode == 0) == expected and reason in result.stdout + result.stderr,
          result.stdout + result.stderr)


def reset(*paths):
    for path in paths:
        git("restore", "--source=HEAD", "--staged", "--worktree", path)


(RIG / "README.md").write_text("Generic unrelated change\n")
git("add", "README.md")
verify("unrelated-bypasses", True)
host = "claude/hooks/lib/privacy-event.py"
(RIG / host).write_text((RIG / host).read_text() + "\n# valid staged host extension\n")
git("add", host)
verify("valid-staged-host", True, "privacy-gates:")
reset(host)

table = "claude/hooks/lib/privacy-decision.sh"
original_table = (RIG / table).read_bytes()
(RIG / table).write_bytes(original_table + b"# deliberately stale staged table\n")
git("add", table)
(RIG / table).write_bytes(original_table)  # A clean worktree must not hide the stale index.
verify("partial-staging-stale", False, "stale")
reset(table)

laws = P + "LAWS.bend"
original_laws = (RIG / laws).read_text()
for name, altered in (("weakened-law", original_laws.replace("for scan: P.Scan", "for scan: P.Scan\n  for unused: Bool", 1)),
                      ("removed-law", original_laws.replace("law acknowledged:", "# law acknowledged:")),
                      ("redirected-law-import", original_laws.replace("as P", "as Other")),
                      ("weakened-requirement-predicate", original_laws.replace(
                          "case P.Unproven{} <> _:\n      False{}", "case P.Unproven{} <> _:\n      True{}"))):
    (RIG / laws).write_text(altered)
    git("add", laws)
    verify(name, False, "owner authorization required")
    reset(laws)
policy = P + "Policy.bend"
original_policy = (RIG / policy).read_text()
(RIG / policy).write_text(original_policy + "\n@unsafe\n")
git("add", policy)
verify("unsafe-policy", False, "unsafe/open proof marker")
reset(policy)
extra = P + "Extra.bend"
(RIG / extra).write_text("import Base\ndef open() -> Nat:\n  ?TODO\n")
git("add", extra)
verify("future-module-hole", False, "unsafe/open proof marker")
git("reset", "-q", "HEAD", "--", extra)  # Retain the produced control file; it is not a build input below.
for name, path in (("shadowed-law-binding", laws), ("shadowed-export-binding", P + "Main.bend")):
    target = RIG / path
    target.write_text(target.read_text() + "\nimport ./Policy.bend as P\n")
    git("add", path)
    verify(name, False, "duplicate Bend import binding")
    reset(path)

# A lawful refactor plus a new independently proved claim is accepted automatically.
private = "    case False{} True{} Private{}:\n      Secrets{}\n"
unknown = "    case False{} True{} Unproven{}:\n      All{}\n"
(RIG / policy).write_text(original_policy.replace(private + unknown, unknown + private))
(RIG / laws).write_text(original_laws.replace("law acknowledged:", 'law acknowledged: # a "quoted" explanatory comment')
                       + "\n# @unsafe ?TODO are examples, not code.\n"
                       "law added_private_scan:\n  {P.plan(False{}, True{}, P.Private{}) == P.Secrets{} : P.Plan}\n")
proof = RIG / P / "PROOF.bend"
proof.write_text(proof.read_text() + "\ndef Laws.added_private_scan():\n  {==}\n")
# Build from a package without the retained untracked hole control.
archive = RIG / ".local/control-inputs"
archive.mkdir(parents=True)
(RIG / extra).rename(archive / "Extra.bend")
result = run("bash", P + "build.sh")
check("lawful-generation", result.returncode == 0, result.stdout + result.stderr)
git("add", policy, laws, P + "PROOF.bend", table)
verify("lawful-refactor-added-law", True, "privacy-staged:")

# Modify live policy after the proof starts: the immutable snapshot remains the compiler
# input, but publishing must refuse because the live source no longer matches it.
before = (RIG / table).read_bytes()
bindir = RIG / ".local/race-bin"
bindir.mkdir()
real_bend = shutil.which("bend")
(bindir / "bend").write_text("#!/usr/bin/env python3\nimport os, subprocess, sys\n"
    "r = subprocess.run([os.environ['REAL_BEND'], *sys.argv[1:]])\n"
    "if sys.argv[1].endswith('/PROOF.bend') and r.returncode == 0:\n"
    " from pathlib import Path\n"
    " p = Path(os.environ['LIVE_POLICY'])\n"
    " p.write_text(p.read_text().replace('case False{} True{} Unproven{}:\\n      All{}', 'case False{} True{} Unproven{}:\\n      Skip{}'))\n"
    "sys.exit(r.returncode)\n")
(bindir / "bend").chmod(0o755)
result = run("bash", P + "build.sh", env=dict(ENV, REAL_BEND=real_bend,
             LIVE_POLICY=str(RIG / policy), PATH=str(bindir) + ":" + os.environ["PATH"]))
(RIG / "build-source-race.txt").write_text(result.stdout + result.stderr)
check("source-race-refuses-publication", result.returncode != 0 and (RIG / table).read_bytes() == before,
      result.stdout + result.stderr)
print(f"privacy-staged-controls: {COUNT} checks passed; artifacts: {RIG}")
