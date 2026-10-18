#!/usr/bin/env python3
"""Partial-evaluate the proved Bend policy into its complete finite shell table."""
import argparse
import hashlib
import itertools
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
TABLE = HERE.parent / "lib/privacy-decision.sh"


def evaluate(binary, request, allowed):
    result = subprocess.run([binary, "--threads", "1"], capture_output=True,
                            env=dict(os.environ, PRIVACY_BEND_REQUEST=request), timeout=2)
    if result.returncode or result.stderr or result.stdout not in [s.encode() + b"\n" for s in allowed]:
        raise RuntimeError(f"invalid native result for {request}: {result}")
    return result.stdout.decode().strip()


def table(binary):
    fingerprint = hashlib.sha256(b"".join((HERE / f).read_bytes() for f in
                                ("Policy.bend", "LAWS.bend", "PROOF.bend", "Main.bend"))).hexdigest()
    text = ("#!/usr/bin/env bash\n# Generated from proved Bend policy; edit Policy.bend, then run build.sh.\n"
            f"# Source SHA256: {fingerprint}\n# Runtime uses Bash builtins only.\n\n")
    specs = [
        ("privacy_plan", 3, "CLASSES", "p", itertools.product(range(2), repeat=3), ("skip", "secrets", "all")),
        ("privacy_verdict", 3, "PRIVACY_VERDICT", "f", itertools.product(range(3), range(3), range(4)), ("allow", "finding", "failure")),
        ("privacy_target", 2, "PROVEN_PRIVATE", "q", itertools.product(range(2), repeat=2), ("0", "1")),
    ]
    count = 0
    for function, arity, variable, op, states, allowed in specs:
        groups = {}
        for state in states:
            request = ":".join(map(str, state))
            result = evaluate(binary, op + ":" + request, allowed)
            if op == "f":
                request = ("skip", "secrets", "all")[state[0]] + ":" + ("none", "secrets", "all")[state[1]] + ":" + str(state[2])
            groups.setdefault(result, []).append(request)
            count += 1
        key = ":".join(f"${{{i}:-}}" for i in range(1, arity + 1))
        text += f"{function}() {{\n    [ \"$#\" -eq {arity} ] || refuse decision-input \"BLOCKED (privacy decision): invalid {function} input.\"\n    case \"{key}\" in\n"
        for result, states in groups.items():
            text += f"        {'|'.join(states)}) {variable}={result} ;;\n"
        text += "        *) refuse decision-input \"BLOCKED (privacy decision): invalid policy evidence.\" ;;\n    esac\n}\n\n"
    # The scanner reports its actual selected classes on stdout before findings. A
    # missing/malformed marker is NoEvidence, so status 0 cannot clear a requested scan.
    text += '''privacy_finish() {
    [ "$#" -eq 2 ] || refuse decision-input "BLOCKED (privacy decision): invalid scan outcome."
    local scan coverage=none report="$2"
    SCAN_FINDINGS="$report"
    case "$report" in
        privacy-scan-v1:all) coverage=all; SCAN_FINDINGS="" ;;
        $'privacy-scan-v1:all\\n'*) coverage=all; SCAN_FINDINGS="${report#*$'\\n'}" ;;
        privacy-scan-v1:secrets) coverage=secrets; SCAN_FINDINGS="" ;;
        $'privacy-scan-v1:secrets\\n'*) coverage=secrets; SCAN_FINDINGS="${report#*$'\\n'}" ;;
    esac
    case "$1" in 0) scan=1 ;; 10) scan=2 ;; *) scan=3 ;; esac
    privacy_verdict "${CLASSES:-}" "$coverage" "$scan"
}
'''
    assert count == 48
    return text


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binary", required=True)
    parser.add_argument("--output", type=Path, default=TABLE)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    expected = table(args.binary)
    if args.check:
        if not args.output.exists() or args.output.read_text() != expected:
            raise SystemExit("generated privacy table is stale; run hooks/privacy-decision/build.sh")
    else:
        pending = args.output.with_name(args.output.name + f".new-{os.getpid()}")
        pending.write_text(expected)
        pending.replace(args.output)
    print("privacy-table: 48 native states checked; " + ("fresh" if args.check else "generated"))
