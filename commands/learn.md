---
description: |
  Append a reusable insight to Claude Code's native project memory.
  Manual: when you notice a reusable pattern, workaround, or insight worth preserving.
---

# Learn - Mid-Session Pattern Capture

Capture a pattern, gotcha, or insight right now before it's forgotten.

## Steps

1. Ask the user what they learned using AskUserQuestion:
   - Question: "What did you just learn or notice?"
   - Options:
     - "Gotcha / workaround" - Something that broke and how to fix it
     - "Tool/tech pattern" - A technique or command that works well
     - "Architecture decision" - A choice with reasoning worth preserving

2. Resolve the native project directory from the current session transcript. Search for the exact path `$HOME/.claude/projects/*/$CLAUDE_SESSION_ID.jsonl`. Continue only when that exact session maps to one project directory; never guess the directory from an encoded working-directory name.

3. Set the target to that project's `memory/MEMORY.md`. Create the `memory/` directory and file when the project directory is known and the memory file does not yet exist.

4. Read the target and search for the stable token that identifies the subject: a project slug, file path, config key, command, issue id, or other literal anchor.

5. Append one concise record. Prefix it with `F` for a durable fact, `S` for current state, `E` for an event, or `P` for a pointer to richer content. Keep commands, paths, and identifiers exact.

6. When the new record corrects an earlier one, append the correction and name the superseded stable token. Preserve the earlier record as history.

7. Confirm the appended line and the resolved native-memory path.

## Rules
- Match the surrounding native-memory style when it already follows a stricter convention.
- Append only reusable cross-session knowledge.
- Keep rich explanations in project files and store a `P` record that points to them.
