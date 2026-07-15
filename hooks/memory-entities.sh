#!/usr/bin/env bash
# SessionStart memory digest wrapper (entity-table section). Registered in the
# settings.json SessionStart group; fail-open (stderr suppressed, always exit 0)
# so a digest error never blocks session startup. Runs the engine as a module
# with the install root on PYTHONPATH so the absolute `memory.*` imports resolve.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}" python3 -m memory.digest --section table 2>/dev/null || true
exit 0
