#!/usr/bin/env python3
"""Scan text on stdin for private identifiers and secrets: the one scanner both gates share.

Inventory from PRIVACY_TOKENS_FILE (default ~/.claude/config/private-tokens.txt): lines
`lit <token>`, `demo <token>`, `re <regex>`; `#` comments and blanks ignored.

    --classes secrets   only the secret patterns; needs no inventory
    --classes all       secrets, structural classes, and the inventory tokens

exit 0 clean; exit 10 with findings on stdout, `line <n> <class> <excerpt>` and every match
replaced by `***`, at most 20; exit 3 the inventory is unusable, because a scan that could
not run is not a clean scan. Plain text only: no base64 or hex decoding.
"""

import argparse
import io
import os
import re
import shutil
import subprocess
import sys
import threading

MAX_FINDINGS = 20
MAX_FILE_BYTES = 1048576
CHUNK = 1 << 22
EXCERPT = 160
DEFAULT_TOKENS = os.path.expanduser("~/.claude/config/private-tokens.txt")

# The inventory and the secret patterns are `grep -E` source. Python reads `[[:alnum:]]` as a
# nested set matching `:` and `a`-`m`, which silently widens every pattern carrying one.
POSIX = dict(
    pair.split("=", 1)
    for pair in (
        "alnum=0-9A-Za-z|alpha=A-Za-z|blank= \\t|cntrl=\\x00-\\x1f\\x7f|digit=0-9|"
        "graph=\\x21-\\x7e|lower=a-z|print=\\x20-\\x7e|punct=!-/:-@\\[-`{-~|"
        "space= \\t\\n\\r\\f\\v|upper=A-Z|word=0-9A-Za-z_|xdigit=0-9A-Fa-f"
    ).split("|")
)


def ere(pattern):
    return re.sub(r"\[:([a-z]+):\]", lambda m: POSIX.get(m[1], m[0]), pattern)


# ripgrep has no lookahead, so its prefilter drops these two: only ever wider.
DIGIT_AHEAD = r"(?=[A-Za-z0-9_]*[0-9])"
PLACEHOLDER = (
    r"(?!(password|passwd|pass|secret|token|changeme|example|x{3,}"
    r"|\$\{?[A-Z_]+\}?|<[^>]+>)@)"
)

# Ported from SECRET_RE in the retired hooks/pre-push-scan.py, which ran under `grep -inE`.
# The Twilio SID is bounded on both sides on purpose: unbounded, the case-insensitive `ac`
# inside any 34-character hex digest matched, so sha256 files and lockfiles were findings.
SECRETS = "|".join(
    [
        r"(^|[^[:alnum:]])sk-ant-(api|admin|oat|sid)[0-9A-Za-z_-]{16,}",
        # A key holds a long random stretch with digits in it; `-cz-sk- + example-brief`
        # and other hyphenated slugs do not (the operator, 2026-10-01).
        r"(^|[^[:alnum:]])sk-[A-Za-z0-9_-]*?" + DIGIT_AHEAD + r"[A-Za-z0-9_]{20,}",
        r"(^|[^[:alnum:]])(sk|rk)_(live|test)_[A-Za-z0-9]{16,}",
        r"gh[porsu]_[A-Za-z0-9]{36,}",
        r"github_pat_[A-Za-z0-9_]{40,}",
        r"glpat-[A-Za-z0-9_-]{20,}",
        # Long-term key ids only. `ASIA` temporary ids ride inside presigned S3 URLs (every
        # finding in ~/lore on 2026-09-01) and grant nothing without the signed request.
        r"AKIA[0-9A-Z]{16}",
        r"AIza[0-9A-Za-z_-]{35}",
        r"ya29\.[0-9A-Za-z_-]{20,}",
        r"(^|[^0-9A-Za-z_])1//0[A-Za-z0-9_-]{20,}",
        r"xox[baprs]-[0-9A-Za-z-]{10,}",
        r"npm_[A-Za-z0-9]{36}",
        r"dop_v1_[a-f0-9]{64}",
        r"hf_[A-Za-z0-9]{30,}",
        r"dckr_pat_[A-Za-z0-9_-]{20,}",
        r"(FlyV1[[:space:]]|fm2_)[A-Za-z0-9+/=_-]{20,}",
        r"tskey-(auth|api|client|reusable)-[A-Za-z0-9_-]{10,}",
        r"SG\.[A-Za-z0-9_-]{22}\.[A-Za-z0-9_-]{43}",
        r"(^|[^0-9A-Za-z])AC[0-9a-f]{32}([^0-9A-Za-z]|$)",
        r"(^|[^0-9])[0-9]{8,10}:AA[A-Za-z0-9_-]{32,}",
        r"rpa_[A-Za-z0-9]{20,}",
        r"(^|[^[:alnum:]])eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}",
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        # Three shapes where the URL IS the credential, so the userinfo alternative below --
        # which needs a `user:pass@` -- never sees them. Ported from the retired SECRET_URL_RE.
        r"hooks\.slack\.com/services/T[A-Z0-9]+/B[A-Z0-9]+/[A-Za-z0-9]+",
        r"discord(app)?\.com/api/webhooks/[0-9]+/[A-Za-z0-9_-]+",
        r"https://[0-9a-f]{16,}@[a-z0-9.-]*sentry\.io/[0-9]+",
        # A userinfo password that is plainly a placeholder is documentation, not a credential.
        # Without the exclusion every `https://user:password@host` in a README is a finding,
        # which is the false-positive class that retired this pattern the first time.
        r"[a-z][a-z0-9+.-]*://[^/@:[:space:]]+:" + PLACEHOLDER + r"[^/@[:space:]]+@[^[:space:]/]",
        r"[Aa]uthorization:[[:space:]]*(Bearer|Basic)[[:space:]]+[A-Za-z0-9+/._=-]{20,}",
    ]
)

# Structural classes (the shape of an overlay-network address, its DNS suffix, a phone number)
# are `re` lines in the private token file: a shape leaks no value, but it names the network
# and the country, so this public copy ships none here. The list stays for a private fork.
STRUCTURAL = []


class BadInventory(Exception):
    pass


def inventory(path):
    """Compile the token file to (class, regex) pairs; raise on anything unusable."""
    literals, demos, regexes = [], [], []
    try:
        with open(path, encoding="utf-8", errors="strict") as handle:
            lines = handle.readlines()
    except (OSError, ValueError) as error:
        raise BadInventory(str(error))
    for number, raw in enumerate(lines, 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)
        value = parts[1].strip() if len(parts) > 1 else ""
        if parts[0] not in ("lit", "demo", "re") or not value:
            raise BadInventory("line %d is not `lit|demo|re <value>`" % number)
        if parts[0] == "lit":
            literals.append(value)
        elif parts[0] == "demo":
            demos.append(value)
        else:
            try:
                compiled = re.compile(ere(value), re.I)
            except re.error as error:
                raise BadInventory(
                    "line %d is not a usable regex: %s" % (number, error)
                )
            # `foo|` is a valid regex that matches every line: it would turn the gate into a
            # wall reporting arbitrary characters as private identifiers.
            if compiled.search(""):
                raise BadInventory("line %d matches every line (a stray '|')" % number)
            regexes.append(("re", compiled))
    if not (literals or demos or regexes):
        raise BadInventory("holds no tokens")
    fixed = [
        (name, re.compile("|".join(re.escape(t) for t in tokens), re.I))
        for name, tokens in (("lit", literals), ("demo", demos))
        if tokens
    ]
    # Each `re` entry compiles alone: joined by `|`, an alternation renumbers capture groups,
    # so a backreference in one entry silently names a group belonging to another.
    return fixed + regexes


def mask(text, spans):
    merged = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    out, cursor = [], 0
    for start, end in merged:
        out += [text[cursor:start], "***"]
        cursor = end
    return "".join(out + [text[cursor:]])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--classes", choices=("secrets", "all"), default="all")
    parser.add_argument("--evidence", action="store_true", help="emit the selected scan class for a gate")
    parser.add_argument("--file", action="append", default=[], help="complete bounded content file")
    parser.add_argument(
        "--tokens", default=os.environ.get("PRIVACY_TOKENS_FILE") or DEFAULT_TOKENS
    )
    args = parser.parse_args()

    matchers = [("secret", re.compile(ere(SECRETS), re.I))]
    if args.classes == "all":
        matchers += [(n, re.compile(ere(p), re.I)) for n, p in STRUCTURAL]
        try:
            matchers += inventory(args.tokens)
        except BadInventory as error:
            print("inventory %s: %s" % (args.tokens, error), file=sys.stderr)
            return 3

    def content():
        yield from sys.stdin.buffer
        for path in args.file:
            with open(path, "rb") as handle:
                data = handle.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES:
                raise OSError("content file exceeds the complete-scan limit of 1 MiB: " + path)
            yield from io.BytesIO(data + b"\n")

    if args.evidence:
        print("privacy-scan-v1:" + args.classes, flush=True)
    try:
        rg = ripgrep(prefilter(args.classes))
        if rg is None:
            return scan(enumerate(content(), 1), matchers)
        return scan(narrowed(rg, chunks(args.file)), matchers)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print("content not completely scanned: " + str(error), file=sys.stderr)
        return 3


# Python's IGNORECASE equates these four with ASCII letters; ripgrep's simple case folding
# keeps only the last two. Every other code point folds alike, so a line holding one of these
# is always a candidate (gates/tests/test-privacy-scan-prefilter.py recomputes the set).
FOLD_ONLY_IN_PYTHON = "\u0130\u0131\u017f\u212a"


def prefilter(classes):
    """ripgrep patterns matching a superset of the lines the secret matcher matches, or None.

    Only the built-in secret patterns are narrowed: they use explicit ASCII classes, where the
    two engines agree. Inventory `re` entries do not (`\\b` beside a combining mark, `\\s` on
    \\x1c, `[a&&b]`), so a scan of every class keeps the full Python pass (review, 2026-09-30).
    """
    if classes != "secrets":
        return None
    # Case-sensitive: under --ignore-case the class would grow to every s and k.
    return [ere(SECRETS.replace(PLACEHOLDER, "").replace(DIGIT_AHEAD, "")),
            "(?-i:[" + FOLD_ONLY_IN_PYTHON + "])"]


def ripgrep(patterns):
    """argv for a usable ripgrep, or None: then every line goes through Python."""
    binary = shutil.which("rg")
    if patterns is None or binary is None:
        return None
    # --no-config: RIPGREP_CONFIG_PATH could add --max-columns and blank out long lines.
    # --encoding none: the default strips a UTF-8 BOM, which Python's decode keeps.
    argv = [binary, "--no-config", "--ignore-case", "--text", "--encoding", "none",
            "--line-number", "--no-filename", "--no-heading", "--color", "never"]
    for pattern in patterns:
        argv += ["-e", pattern]
    try:
        probe = subprocess.run(argv, input=b"", capture_output=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    # 1 is "no match": the patterns compiled. 2 is a pattern ripgrep cannot read.
    return argv if probe.returncode == 1 else None


def chunks(files):
    """The stdin-then-files stream in newline-aligned blocks, decoded exactly as scan() does."""
    def raw():
        tail = b""
        while True:
            block = sys.stdin.buffer.read(CHUNK)
            if not block:
                break
            yield block
            tail = block
        # The line-wise reader ended a newline-less stdin line before the first file line.
        if files and tail and not tail.endswith(b"\n"):
            yield b"\n"
        for path in files:
            with open(path, "rb") as handle:
                data = handle.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES:
                raise OSError("content file exceeds the complete-scan limit of 1 MiB: " + path)
            yield data + b"\n"

    carry = b""
    for block in raw():
        block = carry + block
        cut = block.rfind(b"\n") + 1
        carry = block[cut:]
        # A newline never sits inside a UTF-8 sequence, so decoding whole lines replaces the
        # same bytes as decoding each line: ripgrep searches the text Python would see.
        if cut:
            yield block[:cut].decode("utf-8", "replace").encode("utf-8")
    if carry:
        yield carry.decode("utf-8", "replace").encode("utf-8")


def narrowed(argv, blocks):
    """(line number, line) for each line ripgrep selects, in order."""
    proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                            stderr=subprocess.DEVNULL)
    failure = []

    def feed():
        try:
            for block in blocks:
                proc.stdin.write(block)
        except BaseException as error:  # handed to the reader; never a silent short scan
            failure.append(error)
            proc.kill()
        finally:
            try:
                proc.stdin.close()
            except OSError as error:
                failure.append(error)

    writer = threading.Thread(target=feed, daemon=True)
    writer.start()
    for line in proc.stdout:
        number, _, text = line.partition(b":")
        yield int(number), text
    writer.join()
    status = proc.wait()
    if failure:
        raise failure[0] if isinstance(failure[0], OSError) else OSError(repr(failure[0]))
    if status not in (0, 1):
        raise OSError("ripgrep exited %d" % status)


def scan(content, matchers):
    findings = []
    for number, raw in content:
        # Drain rather than close once capped: an early close SIGPIPEs the producer, and the
        # calling gate reads a failed producer as a scan that never covered its input.
        if len(findings) >= MAX_FINDINGS:
            continue
        text = raw.decode("utf-8", "replace").rstrip("\n")
        spans, classes = [], []
        for name, pattern in matchers:
            hits = [m.span() for m in pattern.finditer(text)]
            if hits:
                spans += hits
                classes.append(name)
        if not spans:
            continue
        # Windowed on the first match, not the head of the line: a truncated head showed a
        # long JSON line with no `***` in it at all, which named nothing and hid the match.
        masked = mask(text, spans)
        cut = max(0, masked.find("***") - EXCERPT // 3)
        excerpt = ("..." if cut else "") + masked[cut : cut + EXCERPT]
        for name in classes[: MAX_FINDINGS - len(findings)]:
            findings.append("line %d %s %s" % (number, name, excerpt))
    if findings:
        print("\n".join(findings))
    return 10 if findings else 0


if __name__ == "__main__":
    sys.exit(main())
