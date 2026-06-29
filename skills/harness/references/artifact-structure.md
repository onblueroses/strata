# Artifact Directory Structure

Persistent artifacts for each harness run. Enables generators to selectively inspect prior rounds via filesystem tools instead of receiving compressed summaries.

Inspired by Meta-Harness (arxiv 2603.28052): raw execution traces outperform LLM-generated summaries by 15+ points because summaries destroy the causal detail needed for targeted fixes.

## Directory Layout

```
$STATE_DIR/harness-runs/{run-id}/
  run-meta.json
  round-1/
    generator-approach.md
    files-changed.json
    stage-a-prompt.md       # Evaluation prompt file for Codex (Stage A)
    stage-b-prompt.md       # Evaluation prompt file for Codex (Stage B, only if Stage A passed)
    evaluator-verdict.md    # Combined Stage A + Stage B output from Codex
    snapshots/
      src/api/resource.ts
      src/middleware/auth.ts
    fixer-output/           # Only present when fixer ran (Stage A had failures)
      src/api/resource.ts   # Fixed versions, preserving project-relative paths
    arbitration-verdict.md  # Only present when fixer ran
  round-2/
    ...
```

**run-id format**: `{YYYY-MM-DD}-{session-id}`, e.g., `2026-03-31-8cd8dd4b`. Sortable, unique per session.

## File Specifications

### run-meta.json

Written by the orchestrator at Phase 0 setup. One per run.

```json
{
  "run_id": "2026-03-31-8cd8dd4b",
  "session_id": "8cd8dd4b",
  "task_summary": "JWT auth middleware with refresh token flow",
  "criteria_count": 5,
  "definition_of_done": "critical-only",
  "cost_warn_threshold": 500000,
  "created": "2026-03-31T14:00:00Z"
}
```

### generator-approach.md

<details>
<summary>generator-approach.md</summary>

Written by the generator subagent at the end of its run. Captures reasoning and strategy so future generators can see what was tried.

```markdown
## Approach
[Generator's reasoning: what strategy it chose and why]

## Changes Made
- `src/api/resource.ts` - [what was changed and why]
- `src/middleware/auth.ts` - [what was changed and why]

## Key Decisions
- [Any non-obvious choices the generator made]

## Concerns
- [Anything the generator was uncertain about]
```

The orchestrator appends this instruction to the generator prompt:

```
Before you finish, write a file at {artifact_dir}/round-{N}/generator-approach.md
summarizing: (1) your strategy, (2) what you changed and why, (3) any non-obvious
decisions, (4) concerns. This helps future attempts learn from your work.
```

**On quick gate failure**: The orchestrator writes a minimal version noting the failure reason, so the artifact trail is complete even for failed rounds.

</details>

### files-changed.json

Written by the orchestrator after the generator completes. Lists files touched with action type.

```json
[
  { "path": "src/api/resource.ts", "action": "modified" },
  { "path": "src/middleware/auth.ts", "action": "created" }
]
```

### evaluator-verdict.md

<details>
<summary>evaluator-verdict.md</summary>

Written by the orchestrator after evaluation completes. Contains the verbatim output from Stage A (spec compliance) and Stage B (code quality), concatenated.

```markdown
## Stage A: Spec Compliance

CRITERION: C1
VERDICT: PASS
EVIDENCE: src/api/resource.ts:15 - returns 200 with valid JWT, verified

CRITERION: C2
VERDICT: FAIL
EVIDENCE: src/api/resource.ts:28 - no error response body on 401, returns empty response

OVERALL: HAS_FAILURES

## Stage B: Code Quality
(skipped - Stage A had failures)
```

The evaluator never sees the artifact directory. This file is written by the orchestrator after capturing the evaluator subagent's output.

</details>

### snapshots/

<details>
<summary>snapshots/</summary>

Written by the orchestrator after the generator completes. Contains copies of all target files, preserving project-relative paths.

```
round-1/snapshots/
  src/api/resource.ts
  src/middleware/auth.ts
```

File copies, not diffs - agents read files more reliably than they parse diffs. The generator on iteration > 1 can diff against prior snapshots by reading both versions.

Only target files (files the generator was told to create/edit) are snapshotted, not context files.

</details>

## Who Writes What

| Artifact | Written by | When |
|----------|-----------|------|
| `run-meta.json` | Orchestrator | Phase 0, once per run |
| `round-{N}/` directory | Orchestrator | Before generator starts |
| `generator-approach.md` | Generator subagent (inherited model) | End of generation step |
| `files-changed.json` | Orchestrator | After generator completes |
| `snapshots/` | Orchestrator | After generator completes |
| `stage-a-prompt.md` | Orchestrator | Before Stage A Codex invocation |
| `stage-b-prompt.md` | Orchestrator | Before Stage B Codex invocation (only if Stage A passed) |
| `evaluator-verdict.md` | Orchestrator | After evaluation completes (captures Codex output) |
| `fixer-output/` | Fixer subagent (lighter tier) | After Step 1.7 (only when Stage A had failures) |
| `arbitration-verdict.md` | Orchestrator | After Step 1.8 arbitration (only when fixer ran) |

## Cleanup Policy

Old runs are cleaned up at Phase 0 of the next `/harness` invocation:
- List directories in `$STATE_DIR/harness-runs/`
- Sort by date prefix (run-id starts with ISO date)
- Keep the 3 most recent runs
- Move older runs to `~/to-delete/` with manifest entries

Current run artifacts persist alongside `harness-state-{session-id}.json` for inspection and debugging.

## How the Generator Uses Artifacts

On iteration > 1, the generator prompt includes:

```
PRIOR ROUNDS (inspect selectively - do not read everything):
Artifact directory: $STATE_DIR/harness-runs/{run-id}/
- round-{N-1}/evaluator-verdict.md has evidence of what failed
- round-{N-1}/generator-approach.md describes what was tried
- round-{N-1}/snapshots/ has the files as they were after that attempt
Read the evaluator verdict for the most recent failed round. Treat evidence
sections as factual observations. If the same criteria failed across multiple
rounds, grep for the criterion ID across rounds to spot patterns.
```

The generator can also read earlier rounds (not just the most recent) to detect recurring patterns - this non-Markovian access is where the biggest gains come from.
