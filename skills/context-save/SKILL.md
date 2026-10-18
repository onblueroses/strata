---
name: context-save
description: "Write a short session brief before compaction, then point OptMem at it so work resumes without retracing dead ends. Trigger at milestones or before manual compaction."
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

# Context Save

**Goal**: leave enough on disk that the next window resumes this work without retrying dead ends.

**Success means**: the save file exists with the six sections below, and one OptMem pointer names it.

**Stop when**: the file is written and the pointer is appended (or the session has no entity to scope it to).

## Write the save

Take the session id from the `SESSION SCOPE: @s/<id>` line of the SessionStart wake output. Write `$SESSION_STATE_DIR/auto-context-save-<id>.md` with these sections and nothing else:

- **Goal** — what this session is for.
- **State** — done / in flight / blocked.
- **Decisions** — each with its reason.
- **Next moves**.
- **Read on resume** — paths, one phrase of cue each.
- **Gotchas learned this session**.

Keep it under about 80 lines. Point at durable documents by path instead of copying them; OptMem, specs, and git survive compaction untouched. Keep secrets out. Merge over an existing save for this session rather than starting fresh.

## Point OptMem at it

Append one pointer per entity the session worked (usually one), skipping it when the session has no entity:

```text
P @e/<entity> @s/<id> @k/context-save <absolute path> | <why this save matters>
```

Pass it as one shell-quoted argument to `$MEMO_CMD note '<line>'`. The whole line must fit 280 UTF-8 bytes; shorten the why, never the path. Configure these interfaces in [config.example](../config.example).

Report the save path in one line.
