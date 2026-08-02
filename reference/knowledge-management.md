<!-- keywords: Claude Code native memory, note discipline, stable tokens, append-only corrections, pointers -->
# Native Memory Notes

Claude Code ships project memory. Strata uses it and does not maintain a second memory backend.

## Quick Nav

| Need | Read |
|------|------|
| Check what exists | Verify the backend |
| Write a useful record | Record shape |
| Keep retrieval reliable | Stable anchors |
| Correct an old claim | Append corrections |

## Verify the backend

Inspect `$HOME/.claude/projects/*/memory/` to see the native project-memory files
that exist on the current installation. Resolve the active project through the
current session transcript; encoded directory names are an implementation detail,
so a guessed path is not evidence.

Read the target file before appending. The file on disk is the check for what the
platform retained and whether a proposed record already exists.

## Record shape

Keep one record on one line. Begin it with a type prefix:

```text
F <stable-token> <durable fact>
S <stable-token> <current state>
E <stable-token> <event and outcome>
P <stable-token> <path to richer content>
```

Use `F` for a fact expected to remain true, `S` for replaceable current state,
`E` for something that happened, and `P` for a filesystem pointer.

Write the claim so another session can test it against a file, command, commit,
issue, or observed result. If no such check exists, label the uncertainty in the
record instead of turning it into a fact.

## Stable anchors

Anchor records with literals that survive paraphrase: project slugs, file paths,
config keys, command names, issue ids, schema fields, or commit ids. Reuse the
same token when the same subject appears again.

Do not rely on semantic similarity for identity. A literal search for the stable
token should find the relevant history even when wording changes.

Keep explanations, logs, designs, and long evidence in ordinary project files.
Store a `P` record with the exact path and a short statement of why it matters.

## Append corrections

Correct a record by appending a line that repeats its stable token and states what
it supersedes. Leave the old line in place so the change remains visible.

Before relying on current state, read all matching lines and use the newest supported correction. Verify consequential claims against their pointed-to source.
