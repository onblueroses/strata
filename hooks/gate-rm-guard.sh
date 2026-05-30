#!/usr/bin/env bash
# gate-rm-guard.sh - PreToolUse(Bash) blocking hook
# Blocks rm on project/home files. Redirects to ~/to-delete/ workflow.
# Allows rm on safe targets: /tmp/, *.pyc, __pycache__, node_modules, build/dist artifacts.

TOOL_INPUT="${CLAUDE_TOOL_INPUT:-}"

# Only trigger on rm commands
if ! echo "$TOOL_INPUT" | python3 -c "
import sys, json, re
try:
    data = json.load(sys.stdin)
    cmd = data.get('command', '')
except:
    cmd = sys.stdin.read()
if re.search(r'\brm\s', cmd):
    sys.exit(0)
sys.exit(1)
" 2>/dev/null; then
    exit 0
fi

# Extract the command
COMMAND=$(echo "$TOOL_INPUT" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    print(data.get('command', ''))
except:
    pass
" 2>/dev/null)

# Allow safe targets: /tmp/, obvious build artifacts
SAFE_PATTERN='/tmp/|\.pyc$|__pycache__|/node_modules/|/\.cache/|/build/|/dist/|/target/|\.o$|\.class$'
if echo "$COMMAND" | grep -qE "$SAFE_PATTERN"; then
    exit 0
fi

# Allow rm of files explicitly just created this command (e.g. rm tempfile after use in same command chain)
# Heuristic: if the rm target is a shell variable or /dev/null, allow it
if echo "$COMMAND" | grep -qE 'rm\s+/dev/null|rm\s+\$[A-Z_]+\b'; then
    exit 0
fi

cat <<'EOF'
{"result": "block", "reason": "Direct deletion blocked. Use the to-delete workflow instead:\n  mv <file> ~/to-delete/<name>\n  echo '<name> | <original-path> | $(date +%Y-%m-%d) | <reason>' >> ~/to-delete/manifest.txt\nIf the file is a true temp/artifact (in /tmp, __pycache__, node_modules, build/dist), rm is fine."}
EOF
exit 2
