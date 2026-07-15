# Memory card schema

Each card is a UTF-8 Markdown file named `<logical-id>.md`. Logical IDs should
contain letters, digits, dots, underscores, or hyphens. `MEMORY.md` is reserved
for the generated entity table and is not a card.

```markdown
---
name: Human-readable title
description: One-line retrieval hint
type: memory
importance: 5
---
Longer body text used by retrieval and shown as a bounded snippet.
```

`name`, `description`, `type`, and `importance` are optional. Missing `type`
defaults to `memory`; missing importance receives a type-based digest prior.
Types `user`, `safety`, and `critical` participate in the digest's never-trim
ladder. Card bodies may contain ordinary Markdown. The loader isolates unreadable
or malformed files so one card cannot zero the corpus.

The generated `MEMORY.md` entity table starts with a heading matching
`## Entities` and a Markdown table. Recommended columns are `Entity`, `Path`,
`Status`, and `last_verified`.
