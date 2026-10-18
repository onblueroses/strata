#!/usr/bin/env python3
"""Exercise event framing and literal/dynamic quote context without executing input."""
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[2]
READER = ROOT / "hooks/lib/privacy-event.py"


def decode(command, **extra):
    event = dict(tool_input=dict(command=command), **extra)
    r = subprocess.run(["python3", str(READER)], input=json.dumps(event), text=True,
                       capture_output=True, timeout=2)
    fields = r.stdout.split("\0")[:-1]
    return r, fields


cases = [
    ("gh issue create --body-file 'body file.md'", "body file.md", "0"),
    ('''gh api graphql -f query='query($id: ID!) { node(id: $id) { id } }' ''',
     "query=query($id: ID!) { node(id: $id) { id } }", "0"),
    ('gh issue create --body "$BODY"', "$BODY", "1"),
    (r'gh issue create --body "\$BODY"', r"\$BODY", "0"),
    ("gh issue create --body '$(touch sentinel); `touch sentinel`'", "$(touch sentinel); `touch sentinel`", "0"),
    ('gh issue create --body="$(cat file)"', "--body=$(cat file)", "1"),
    ("git push a&&git push b", "&&", "2"),
    ("echo '&&'", "&&", "0"),
    ("git push a&&'git push b'", "&&", "2"),
    ("python3 - <<'PY'\nprint(\"unbalanced shell quote: ' gh git\")\nPY\ngit push a", "push", "0"),
    # A quote that spans lines closes on a later line; judging each line alone read that
    # closing quote as an opening one and left the heredoc body unmasked (2026-09-30).
    ("git commit -m \"subject\n\nbody\" && cat >> f <<'EOF'\nCodex's note\nEOF\ngit push a", "push", "0"),
]
for command, token, flag in cases:
    result, fields = decode(command)
    assert result.returncode == 0 and fields[0] == "privacy-event-v2", result.stderr
    count = int(fields[1])
    assert len(fields) == 5 + 2 * count
    pairs = dict(zip(fields[5::2], fields[6::2]))
    assert pairs[token] == flag, (command, fields)
for command, extra in (("gh x\0y", {}), (False, {}), ("gh read", {"cwd": "x\0y"}),
                       ("gh read", {"session_id": 4}), ("gh 'unclosed", {})):
    result, fields = decode(command, **extra)
    assert result.returncode != 0 and not fields
print("privacy-event: 16 quote/framing controls passed")
