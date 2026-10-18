#!/usr/bin/env python3
"""The ripgrep prefilter must never hide a line the Python matchers would report.

Every case compares the narrowed scan with the full line-by-line scan on the same bytes;
the two must agree finding for finding. A deliberately blind prefilter is the positive
control that this comparison can fail. Optional argument: a corpus file (for example a
`git log -p` of ~/lore) to compare as well; it is never written anywhere.
"""
import importlib.util
import io
import os
import pathlib
import re
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[2]
SCANNER = ROOT / "hooks/lib/privacy-scan.py"
spec = importlib.util.spec_from_file_location("privacy_scan", SCANNER)
ps = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ps)
ps.MAX_FINDINGS = 10**9  # compare every finding, not the first twenty


def full(data, matchers):
    out = io.StringIO()
    real, sys.stdout = sys.stdout, out
    try:
        ps.scan(enumerate(io.BytesIO(data), 1), matchers)
    finally:
        sys.stdout = real
    return out.getvalue()


def narrow(data, matchers, patterns):
    argv = ps.ripgrep(patterns)
    assert argv, "ripgrep is required for this test (missing, or it refused the prefilter patterns); the scanner itself falls back to a full scan"
    real_stdin, real_stdout = sys.stdin, sys.stdout
    sys.stdin = io.TextIOWrapper(io.BytesIO(data))
    sys.stdout = out = io.StringIO()
    try:
        ps.scan(ps.narrowed(argv, ps.chunks([])), matchers)
    finally:
        sys.stdin, sys.stdout = real_stdin, real_stdout
    return out.getvalue()


def matchers_for(classes, tokens):
    found = [("secret", re.compile(ps.ere(ps.SECRETS), re.I))]
    if classes == "all":
        found += [(n, re.compile(ps.ere(p), re.I)) for n, p in ps.STRUCTURAL]
        found += ps.inventory(tokens)
    return found


# 1. The fold set is complete: every non-ASCII code point Python's IGNORECASE equates with an
#    ASCII letter or digit is in FOLD_ONLY_IN_PYTHON.
ascii_class = re.compile("[a-zA-Z0-9]", re.I)
folds = {chr(c) for c in range(0x80, 0x110000)
         if not 0xD800 <= c < 0xE000 and ascii_class.fullmatch(chr(c))}
assert folds <= set(ps.FOLD_ONLY_IN_PYTHON), sorted(map(hex, map(ord, folds)))

# Shapes built at run time so this file carries no secret-shaped literal.
FOLD_MARK = "(?-i:["
A = "A" * 40
K = "aB3" * 16  # key-shaped: a long stretch with digits
samples = [
    "sk-" + "ant-api03-" + A, "x=sk-" + "proj-" + K, "rk_" + "live_" + A, "gh" + "p_" + A,
    "github" + "_pat_" + A + A, "gl" + "pat-" + A, "AK" + "IA" + "A" * 16, "AI" + "za" + "B" * 35,
    "ya" + "29." + A, "1/" + "/0" + A, "xo" + "xb-" + "1234567890ab", "np" + "m_" + "a" * 36,
    "hf" + "_" + A, "dckr" + "_pat_" + A, "tskey" + "-auth-" + A, "eyJ" + "a" * 12 + ".bbbbbbbbbbbb.cccccc",
    "-----BEGIN " + "RSA PRIVATE KEY-----", "https://" + "joe:hunter2x@" + "db.example.com",
    "Authorization: " + "Bearer " + A, "hooks.slack.com" + "/services/T0/B0/abc",
    "ſk-" + "ant-api03-" + A,          # long s: Python folds it to s
    "AKİA" + "A" * 16,               # dotted capital I: Python folds it to i
    "K" + "ey",                        # Kelvin sign next to nothing secret
    "caf\xe9 ﻿sk-" + "proj-" + K,    # non-ASCII and a BOM before a match
]
noise = ["plain prose line", "x-cz-sk-" + "material-buyers-brief-and-more.md", "sk-" + "A" * 30, "https://user:password@" + "example.com/x", "", "\x00binary\x00",
         "Gr\xfc\xdfe aus \xdcberall", "10.9." + "1.2 and host.mesh.example and +" + "44 30 1234567"]
lines = []
for i in range(400):
    lines.append(noise[i % len(noise)])
    if i % 7 == 0:
        lines.append(samples[i % len(samples)])
text = ("\n".join(lines + samples) + "\n").encode()
# Invalid UTF-8 directly before and inside a match: both sides must see U+FFFD alike.
text += b"\xff" + ("sk-" + "ant-api03-" + A).encode() + b"\n" + b"gh" + b"p_\xc3" + A.encode() + b"\n"
text += b"no trailing newline ghp_" + A.encode()

with tempfile.TemporaryDirectory() as tmp:
    tokens = pathlib.Path(tmp, "tokens.txt")
    tokens.write_text("lit nonesuch-private-name\ndemo widgets.example\nre acme[- ]?corp\n")
    data_with_tokens = text + b"\nAcme Corp and NONESUCH-private-name and widgets.example\n"
    checked = 0
    for classes in ("secrets",):
        matchers = matchers_for(classes, str(tokens))
        patterns = ps.prefilter(classes)
        expected = full(data_with_tokens, matchers)
        assert expected.count("\n") >= 30, expected  # the samples really are findings
        got = narrow(data_with_tokens, matchers, patterns)
        assert got == expected, (classes, set(expected.splitlines()) ^ set(got.splitlines()))
        checked += expected.count("\n")
        # Positive control: a prefilter that cannot see the long-s line loses a finding.
        blind = [p for p in patterns if FOLD_MARK not in p]
        assert narrow(data_with_tokens, matchers, blind) != expected, "control did not fire"

    # 2. Inventory regexes diverge between the engines (NFD "Acmé" against `\\bacme\\b`), so a
    #    scan of every class is never narrowed.
    assert ps.prefilter("all") is None

    # 3. End to end through the CLI, with and without ripgrep on PATH: same report, same status.
    def cli(env_path):
        env = dict(os.environ, PATH=env_path, PRIVACY_TOKENS_FILE=str(tokens))
        tokens.write_text("lit nonesuch-private-name\n")
        return subprocess.run([sys.executable, "-S", str(SCANNER), "--classes", "secrets", "--evidence"],
                              input=data_with_tokens, capture_output=True, env=env, timeout=60)
    with_rg, without_rg = cli(os.environ["PATH"]), cli(tmp)
    assert with_rg.returncode == without_rg.returncode == 10, (with_rg, without_rg)
    assert with_rg.stdout == without_rg.stdout
    clean = subprocess.run([sys.executable, "-S", str(SCANNER), "--classes", "secrets"],
                           input=b"nothing here\n", capture_output=True, timeout=30)
    assert clean.returncode == 0 and not clean.stdout, clean

    # 4. A content file over the bound is a failed scan (3), not a short clean one.
    big = pathlib.Path(tmp, "big")
    big.write_bytes(b"x" * (ps.MAX_FILE_BYTES + 1))
    over = subprocess.run([sys.executable, "-S", str(SCANNER), "--classes", "secrets", "--file", str(big)],
                          input=b"", capture_output=True, timeout=30)
    assert over.returncode == 3, over

# The OpenAI shape wants digits in a hyphen-free stretch of 20: slugs and letter runs pass.
sk = re.compile(ps.ere(ps.SECRETS), re.I)
assert sk.search("sk-" + "proj-" + K) and sk.search("sk-" + K[:48])
assert not sk.search("-cz-sk-" + "material-buyers-brief.md") and not sk.search("sk-" + "A" * 30)
assert not sk.search("sk-" + "2026-09-material-buyers-brief")  # digits, but no 20-long stretch

if len(sys.argv) > 1:
    corpus = pathlib.Path(sys.argv[1]).read_bytes()
    matchers = matchers_for("secrets", None)
    expected = full(corpus, matchers)
    assert narrow(corpus, matchers, ps.prefilter("secrets")) == expected
    print("corpus: %d findings agree" % expected.count("\n"))
print("privacy-scan prefilter: %d findings agree, fold set and controls hold" % checked)
