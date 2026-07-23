# Save-File Template

Block shapes for `/context-save` Step 2. Copy each block into
`$STATE_DIR/auto-context-save-{session-id}.md` and fill every field.

**Parse contract:** the section names below are literals that `/context-resume`,
`session-post-compaction-restore.sh`, and `gate-resume-read.py` depend on. `## Read On Resume`
is the load-bearing one. Rename a section only by changing every consumer in the same commit.

**Capture vs point:** capture verbatim only what dies with the context window (the live loop,
decisions, outputs). Point by path at what lives on disk (specs, canonical docs, entity KB).

## Frame block (one per touched repo — pointers, not copies)

```markdown
# Context Save: [DATE TIME]

## Repo Frame: {repo-name}

**Path:** `/absolute/path/to/repo` | **Branch:** `branch-name`
**Entity:** `$KB_DIR/projects/{name}` (or "no entity mapping")

**North Star:** [1-3 sentences: what this repo is FOR, the durable goal. Quote the single load-bearing claim from THESIS.md-class docs if one exists.]
**Station:** [Where this work sits in the longer arc: what's shipped, in motion, queued. 2-4 sentences.]
**Read for frame:** [paths only, one line each on why]
- `THESIS.md` — [why it matters to this work]
- `docs/ARCHITECTURE.md` — [why]
- `$KB_DIR/projects/{name}/summary.md` — entity state
```

## Core blocks (always include)

```markdown
## Session Goal
[Primary objective THIS SESSION: specific, distinct from the repo's north star. "Adding X to Y" not "working on Y".]

## Status
- Branch: [name], [count] uncommitted files
- [x] Completed items
- [ ] In progress / pending

## Decisions
| Decision | Reasoning |
|----------|-----------|
| [choice] | [why; include the *because* so edge cases can be judged later] |

## Key Files Modified
| Path | What changed |
|------|-------------|
| [path] | [change] |

## Spec Files
| Path | Progress | Current Step (quoted) |
|------|----------|----------------------|
| [spec path] | [X/Y] | [verbatim from >> Current Step, already updated on disk] |

## Next Actions
1. [First priority: concrete, executable]
2. [...]

## Critical Context
[Non-obvious things that would be bad to forget: constraints, gotchas, why approach Y was ruled out, conventions specific to this work.]
```

## Bridge blocks (always include)

````markdown
## Read On Resume

The post-compaction model should open these files first, in this order:

1. `path/to/file.py:L120-180` — [one-line why: where the bug is / where the change goes]
2. `path/to/spec.md` — [why: source of truth for the current frontier]
3. (3-7 entries total; ordered by what unblocks the next move first)

**Suggested skills:** the 1-3 skills to invoke first, each with a one-line why (e.g. `/pickup` to load entity context).

## In-Flight

**Current hypothesis / approach:** [what we believe is true and are acting on]
**Last attempt:** [what we just tried]
**Result:** [what happened: error, partial success, dead end]
**Next move:** [what to try next, and why this rather than alternatives]
**Ruled out:** [approaches already tested and rejected, recorded so they are not re-tried]

## Last Run Outputs

Verbatim, truncated to the load-bearing 20-50 lines (error frame, failing assertion, actual numbers):

```
[command]
[output]
```
````

## Session-Specific State (optional, freeform)

```markdown
## Session-Specific State
[Whatever live state this particular work makes load-bearing and the blocks above don't hold:
experiment configs mid-run, dispatched-agent/codex session ids with resume commands, draft
voice notes, hyperparameter comparisons. Capture what would be lost; skip padding.]
```
