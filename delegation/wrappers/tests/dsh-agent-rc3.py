#!/usr/bin/env python3
"""Exercise the driver with isolated homes and local session logs."""

import json
import os
from pathlib import Path
import subprocess
import tempfile


WRAPPER = Path(__file__).resolve().parents[1] / "dsh-agent"
STATE = Path.home() / ".local/state/dsh-driver-tests"
STATE.mkdir(parents=True, exist_ok=True)
ROOT = Path(tempfile.mkdtemp(prefix="rc3-", dir=STATE))
FIXTURE = r'''#!/usr/bin/env python3
import json, os, pathlib, re, signal, subprocess, sys, time
overlay = pathlib.Path(sys.argv[sys.argv.index('--patch', 4) + 1]).read_text()
root = pathlib.Path(re.search(r'root: (.+)', overlay)[1])
model = re.search(r'model: (.+)', overlay)[1]
case = os.environ['DRIVER_TEST_CASE']
print(json.dumps({k: os.environ.get(k) for k in [
    'DSH_HOME', 'DSH_TOOLS_MODE', 'DSH_PERMISSION_MODE',
    'DSH_TELEMETRY_DISABLED', 'DSH_UNTRUSTED', 'DEEPSEEK_API_KEY']}), flush=True)
def log(name, depth, chosen=model, provider='deepseek-official'):
    rows = [{'type':'session','delegationDepth':depth},
            {'type':'request/header','data':{'header':{'config':{'provider':provider,'model':chosen}}}},
            {'type':'assistant/message','data':{'turn':1,'step':1,'usage':{'inputTokens':10,'outputTokens':5}}}]
    if case == 'headerless': rows = rows[:1]
    raw = '\n'.join(json.dumps(row) for row in rows) + '\n'
    dest = root / name / 'session.v4.jsonl.zstd'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(subprocess.run(['zstd','-qc'],input=raw.encode(),capture_output=True,check=True).stdout)
    if case == 'corrupt': dest.write_bytes(b'invalid zstd')
if case not in ['missing', 'timeout-missing']:
    log('root', 1 if case == 'child-only' else 0,
        'wrong-model' if case == 'mismatch' else model,
        'wrong-provider' if case == 'provider' else 'deepseek-official')
if case == 'child': log('child', 1, 'deepseek-v4-pro')
if case == 'duplicate': log('second-root', 0)
if case.startswith('timeout'):
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    time.sleep(10)
if case == 'failure': sys.exit(1)
'''


def run(case, expected, *args, pattern=""):
    home = ROOT / case
    binary = home / ".local/share/dsh-driver-0.2.1-rc.3/node_modules/.bin/dsh"
    binary.parent.mkdir(parents=True)
    binary.write_text(FIXTURE)
    binary.chmod(0o700)
    overlay = home / ".config/delegate/dsh/dsh-agent.yml"
    overlay.parent.mkdir(parents=True)
    overlay.write_text("[]\n")
    (home / ".config/delegate/.env").write_text("DEEPSEEK_API_KEY=fixture-file-key\n")
    env = dict(os.environ, HOME=str(home), DRIVER_TEST_CASE=case,
               DEEPSEEK_API_KEY="fixture-caller-key", DSH_UNTRUSTED="discard-me",
               DSH_TOOLS_MODE="invalid")
    result = subprocess.run([str(WRAPPER), *args, "test"], env=env,
                            capture_output=True, text=True, timeout=25)
    (home / "stdout").write_text(result.stdout)
    (home / "stderr").write_text(result.stderr)
    assert result.returncode == expected, (case, result.returncode, result.stderr)
    assert pattern in result.stderr, (case, result.stderr)
    if expected == 0:
        launch = json.loads(result.stdout)
        assert launch["DSH_HOME"] == str(home / ".local/share/dsh-driver/home")
        assert launch["DSH_TELEMETRY_DISABLED"] == "1"
        assert launch["DSH_UNTRUSTED"] is None
        assert launch["DEEPSEEK_API_KEY"] == "fixture-caller-key"
        assert launch["DSH_TOOLS_MODE"] == ("ptc" if "--code" in args else None)
        assert launch["DSH_PERMISSION_MODE"] == ("read-only" if "--read-only" in args else "workspace-write")
    print(f"PASS {case}: exit {expected}")


run("success", 0, pattern="session.v4.jsonl.zstd")
run("ptc", 0, "--code", "--read-only")
run("pro", 0, "--pro")
run("missing", 65, pattern="expected one root session log, found 0")
run("headerless", 65, pattern="no model request/header")
run("child-only", 65, pattern="expected one root session log, found 0")
run("duplicate", 65, pattern="expected one root session log, found 2")
run("corrupt", 65, pattern="decoder returned")
run("mismatch", 6, pattern="MODEL MISMATCH")
run("provider", 6, pattern="provider:wrong-provider")
run("child", 0)
run("failure", 1)
run("timeout-valid", 124, "--timeout", "1", pattern="run killed")
run("timeout-missing", 124, "--timeout", "1", pattern="run killed")
run("zero-timeout", 64, "--timeout", "0", pattern="positive seconds")
print(f"Logs: {ROOT}")
