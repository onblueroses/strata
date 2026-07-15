#!/usr/bin/env bash
# SessionEnd memory access-log wrapper. Mechanical only; fail-open so a telemetry
# parse problem never blocks session shutdown. Twenty seconds is enough for normal
# O(new-tail) ingestion; the timeout keeps shutdown bounded during first-run
# migration, telemetry rotation, or a filesystem stall. Runs the engine as a module
# with the install root on PYTHONPATH so the absolute `memory.*` imports resolve.
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}" timeout 20 python3 -m memory.reconcile --access-log 2>/dev/null || true
exit 0
