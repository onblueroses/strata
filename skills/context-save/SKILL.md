---
name: context-save
version: 8.0.0
description: "Pre-compaction session-state save, pointer-first: capture the live loop that dies with the context window (In-Flight, decisions, next actions, last outputs) and point at everything that lives on disk (specs, canonical docs, entity KB). Manual: invoke /context-save at milestones or before manual compaction."
allowed-tools:
  - Read
  - Write
  - Edit
  - Bash
  - Glob
  - Grep
---

# Context Save

Save this session's live state as a brief for the next instance, so it resumes the work without asking a clarifying question and without re-trying dead ends.

**Outcome:**
- Goal: the post-compaction model inherits the live loop (current hypothesis, last result, next move, ruled-out paths) and a map of where everything else lives.
- Success means: every Core and Bridge block filled, `>> Current Step` updated on disk for owned specs, no `[placeholder]` left.
- Stop when: the Self-Check passes.

**Capture vs point.** Compaction destroys only what exists solely in the context window; disk survives untouched. Capture verbatim: the in-flight loop, session decisions with reasoning, last run outputs, anything not yet written anywhere else. Point by path: specs, canonical docs (THESIS.md, README.md, CLAUDE.md), entity summary.md/items.json, git state. The pipeline overview lives at `$STRATA_HOME/reference/context-continuity.md`.

**Division of labor.** The PreCompact hook (`hooks/context-pre-compaction-save.sh`) automatically writes `auto-context-save-{session-id}-hook.md`: an advisory mechanical snapshot (git state, owned specs' `>> Current Step`, daily-note summaries) plus the Frame map (canonical doc paths, entity paths). The harness natively reloads the cwd CLAUDE.md chain and writes its own compaction summary. This skill owns the semantic layer nothing else records: North Star + Station framing, In-Flight, Decisions, Read On Resume, Last Run Outputs. `## North Star` names the gated strategic anchors: the spec's frozen zone via line range, the entity summary, and a canonical design document. `## Read On Resume` is the ungated advisory map of tactical pointers. Point both blocks at conclusions, never logs.

**Guard — merge, don't overwrite.** The save lives at `$STATE_DIR/auto-context-save-{session-id}.md` (session ID = 8-char suffix of the daily-note filename). Read your session's existing save first; if it is richer than what you're about to write, merge: keep the fuller Goal/Critical Context, union Decisions/Key Files, refresh Status/In-Flight/Last Outputs to now.

**Scope vs `/handoff`.** /context-save survives THIS session's own compaction. To hand a *different* next task to a *fresh* session, use `/handoff` (writes `$STATE_DIR/handoffs/`).

**Keep sensitive data out:** saves are plaintext in the repo; no keys, tokens, passwords.

## Step 1: Gather state

1. **Touched repos.** For each: path, branch, entity mapping (`$KB_DIR/projects/{name}` or `$KB_DIR/areas/{name}`), and the canonical docs worth naming (THESIS/STRATEGY/ARCHITECTURE/README class, root + `docs/ notes/ .claude/`). Record paths, one line on why each matters; quote at most the single load-bearing claim.
2. **Owned specs only (sibling isolation).** The owner runs multiple parallel sessions; a sibling's spec contaminates the resume. For each spec at `$SPECS_DIR/` with header `Status: in-progress` or `planning`: include it only if its `Session:` field matches THIS session, is absent, or the spec was edited here (the same filter the hooks apply). Update each included spec's `>> Current Step` on disk NOW — the spec is the durable pointer; the save only quotes it.
3. **Live loop.** The current hypothesis/approach, last attempt, result, next move, ruled-out paths; the verbatim load-bearing 20-50 lines of the last test/command output; pending background work (agents, dmux panes, codex sessions with their resume ids).
4. **North Star anchors.** Carry forward at most 3 durable strategic paths unless the mission genuinely shifted; use a line range for files over approximately 10 KB.

## Step 2: Write the save

Copy the block shapes from `references/save-template.md` and fill every field. Section names are a parse contract with `/context-resume` and the restore/gate hooks — keep them exact; `## North Star` is the gated orientation contract and `## Read On Resume` is advisory.

Where the work has live state the template doesn't name (experiment configs mid-run, dispatched-agent status, draft-in-progress voice notes), add it under `## Session-Specific State` in whatever shape fits: capture what would be lost, skip what a genre template would pad.

**Priority Mode (budget near-exhausted).** Write in recoverability order and stop where the budget ends: (1) spec `>> Current Step` on disk, (2) North Star + In-Flight + Next Actions + Read On Resume, (3) remaining Core blocks, (4) Frame pointers. The hook independently guarantees the mechanical snapshot; the semantic layer exists nowhere else.

**Self-Check** (fix any miss before finishing): Session Goal specific and distinct from the repo's north star; North Star has at most 3 durable conclusion-bearing paths carried forward from the prior save unless the mission shifted, with line ranges for files over approximately 10 KB; Read On Resume lists 3-7 advisory tactical paths beyond the save itself; In-Flight has all five sub-fields (an empty "Ruled out" is suspicious); Last Run Outputs verbatim, not paraphrase; Decisions carry the *because*; owned specs' `>> Current Step` updated on disk and quoted; Frame pointers name paths, not copies; no `[placeholder]` left.

## Step 3: Output

```
CONTEXT SAVED to $STATE_DIR/auto-context-save-{session-id}.md
Repos: [touched repos]
Specs: [owned specs, >> Current Step updated on disk]
Git: [branch], [uncommitted count] uncommitted
Next: [top priority action]

Ready to compact.
```
