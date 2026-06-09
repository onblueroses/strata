#!/usr/bin/env bash
# context-doc-router.sh — UserPromptSubmit hook (thin wrapper).
# v2: routes reference docs by work-context (cwd + recent edits + lexical meaning),
# not prompt keywords. Implementation in context-doc-router.py (bake-off winner,
# .router-eval aggregate F1 0.792 vs ~0.10 for the old keyword router).
# Backstop: any failure exits 0 so the user's prompt is never broken.
exec python3 "$(dirname "$0")/context-doc-router.py"
