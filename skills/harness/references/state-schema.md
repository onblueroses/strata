# Harness State Schema

JSON schema for `$STATE_DIR/harness-state-{session-id}.json` (one file per session — `{session-id}` is the 8-char suffix of today's daily note filename). This file tracks loop progress and survives compaction. Session-specific filenames let multiple sessions run /harness concurrently without clobbering each other's state.

## Schema

```json
{
  "session_id": "a1b2c3d4",
  "status": "running | complete | escalated | error | aborted",
  "termination_reason": "done | spinning | oscillating | structural | diminishing_returns | user_abort | error",
  "task_summary": "One-line description of the task being harnessed",
  "run_id": "2026-03-31-a1b2c3d4",
  "artifact_dir": "$STATE_DIR/harness-runs/2026-03-31-a1b2c3d4",
  "definition_of_done": "critical-only",
  "cost_warn_threshold": 500000,
  "cost_warning_emitted": false,
  "convergence_state": {
    "failing_set_history": [["C2", "C3"], ["C2"]],
    "fix_count_history": [null, 1],
    "spinning_strikes": 0,
    "oscillating_strikes": 0,
    "structural_strikes": 0,
    "diminishing_strikes": 0,
    "cumulative_tokens": 124000
  },
  "iteration": 2,
  "criteria": [
    {
      "id": "C1",
      "description": "API returns 200 with valid JWT",
      "pass_condition": "GET /api/resource with valid token returns 200",
      "fail_condition": "Returns non-200 or rejects valid token"
    }
  ],
  "target_files": ["src/api/resource.ts", "src/middleware/auth.ts"],
  "context_files": ["src/types/auth.d.ts"],
  "mode": "linear | competitive",
  "candidates_per_round": 1,
  "slot_configs": [
    {"index": 0, "model": "opus", "strategy": "correctness-first"},
    {"index": 1, "model": "sonnet", "strategy": "simplicity-first"}
  ],
  "from_spec": null,
  "rework_fail_counts": {},
  "iterations": [
    {
      "iteration": 1,
      "retry_mode": "fresh",
      "framing_used": "specification-lawyer",
      "winning_candidate": null,
      "candidates_evaluated": 1,
      "generator_files_changed": ["src/api/resource.ts"],
      "stage_a": {
        "verdicts": { "C1": "PASS", "C2": "FAIL" },
        "evidence": {
          "C1": "src/api/resource.ts:15 - returns 200 with valid JWT, verified",
          "C2": "src/api/resource.ts:28 - no error response body on 401"
        },
        "status": "DONE"
      },
      "stage_b": null,
      "evaluator_feedback": [
        {
          "criterion_id": "C2",
          "description": "API returns structured error body on 401",
          "evidence": "src/api/resource.ts:28 - no error response body on 401"
        }
      ],
      "overall": "HAS_FAILURES",
      "timestamp": "2026-03-25T14:30:00Z"
    }
  ],
  "current_framing": "security-audit",
  "framings_used": ["specification-lawyer"],
  "insights": "Generator consistently missed error response bodies on 401. specification-lawyer caught the contract gap that security-audit would have framed as a data leak.",
  "failure_patterns": ["missing-error-response-body", "incomplete-status-code-handling"],
  "last_updated": "2026-03-25T14:35:00Z",
  "created": "2026-03-25T14:00:00Z"
}
```

## Field Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `session_id` | string | yes | 8-char session ID from daily note filename |
| `status` | enum | yes | Current loop state. `running` while iterating; `complete` on DONE; `escalated` when a convergence detector reached its second strike and the user paused; `aborted` if the user chose abort during escalation; `error` on unrecoverable failure |
| `termination_reason` | enum | no | Set when `status` leaves `running`. `done` (DONE), `spinning` / `oscillating` / `structural` / `diminishing_returns` (convergence-detector escalation), `user_abort` (user chose abort), `error` (unrecoverable) |
| `task_summary` | string | yes | One-line task description for resume context |
| `run_id` | string | yes | `{YYYY-MM-DD}-{session-id}` identifier for this run's artifact directory |
| `artifact_dir` | string | yes | Path to `$STATE_DIR/harness-runs/{run-id}/` - where all round artifacts live |
| `definition_of_done` | enum | yes | What counts as success: `critical-only` (Stage A pass + no Stage B CRITICAL; default), `no-warnings` (Stage A pass + zero Stage B findings), `stage-a-only` (Stage A pass only; Stage B skipped) |
| `cost_warn_threshold` | number | yes | Cumulative-token threshold above which the soft cost warning prints once. Default 500000. Never aborts the loop |
| `cost_warning_emitted` | boolean | yes | Whether the soft cost warning has already been printed this run (warning fires at most once) |
| `convergence_state` | object | yes | Convergence-detector state. `failing_set_history` is an array of arrays - one failing-set per iteration. `fix_count_history` is an array of numbers (or null for iteration 1) - count of items removed from the previous failing set. The four `*_strikes` fields each track how many times a detector has fired (0, 1, or 2 = escalated). `cumulative_tokens` accumulates generator + Stage A + Stage B token usage across the run |
| `iteration` | number | yes | Current iteration count (0 = setup complete, not started). No upper bound; convergence detectors govern termination |
| `criteria` | array | yes | Acceptance criteria with PASS/FAIL conditions |
| `target_files` | array | yes | Files the generator creates/modifies |
| `context_files` | array | no | Read-only files for generator context |
| `mode` | enum | yes | `"linear"` (default) or `"competitive"`. Competitive spawns N generators per iteration |
| `candidates_per_round` | number | yes | 1 for linear mode, N for competitive mode (2-5) |
| `slot_configs` | array | no | Per-slot model and strategy overrides. Set when `--models` flag is passed. Index maps to candidate slot (0-based). Absent or empty means all slots use `"opus"` with round-robin strategy hints. |
| `strictness` | enum | yes | Evaluator strictness level: `"strict"`, `"standard"` (default), or `"lenient"`. Controls the text block injected into Stage B via `{{strictness}}`. See `references/strictness-blocks.md`. |
| `from_spec` | string/null | no | Spec filename if criteria derived from spec |
| `rework_fail_counts` | object | yes | Map of criterion ID -> consecutive rework failure count. Tracks per-criterion persistence across rework iterations. If any criterion reaches count 2, next iteration uses fresh mode. Criteria that pass are removed from the map. Initialized as `{}`. |
| `iterations` | array | yes | Results from each completed iteration. Each entry includes `retry_mode` (`"fresh"` or `"rework"` - records the mode *this iteration used*, not what comes next; first iteration is always `"fresh"`), `stage_a` (`{verdicts, evidence, status}`), `stage_b` (`{findings, status}` or `null` if Stage A failed or `done_bar == "stage-a-only"`), `evaluator_feedback` (array of `{criterion_id, description, evidence}` for Stage A failures + `{finding, severity, evidence}` for Stage B criticals, or `null` if ALL_PASS), `overall`, `framing_used`, `winning_candidate` (number/null, competitive mode only), `candidates_evaluated` (number, 1 in linear mode; also 1 for rework iterations in competitive mode), `failing_set` (array of criterion IDs and Stage B finding keys that failed this iteration, used by convergence detectors), and `fix_count` (number/null - items removed from the previous iteration's failing set; null on iteration 1) |
| `current_framing` | string | yes | Next evaluator framing to use |
| `framings_used` | array | yes | Framings already used (for rotation) |
| `insights` | string | no | 2-3 sentence summary of what this run revealed (written at wrap-up) |
| `failure_patterns` | array | no | Recurring failure categories across iterations (e.g., "missing-input-validation") |
| `last_updated` | ISO 8601 | yes | Timestamp of last state mutation |
| `created` | ISO 8601 | yes | Timestamp of harness initialization |

### Per-Iteration Fixer Fields

These fields appear inside each iteration entry in the `iterations` array:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `fixer_ran` | boolean | yes | Whether the fixer step executed this iteration |
| `fixer_files` | array | no | List of file paths written to `fixer-output/` (only present when `fixer_ran: true`) |
| `arbitration_verdicts` | object | no | Map of `{filepath: {action: "accept"|"reject", reason: "one line"}}` (only present when fixer ran) |

## Status Transitions

```
(init)   -> running      Phase 0 complete, loop starting
running  -> running      Each iteration updates within running
running  -> complete     DONE: Stage A ALL_PASS + Stage B meets done_bar
                         (termination_reason: "done")
running  -> escalated    Convergence detector reached its second strike;
                         loop paused for user decision via AskUserQuestion
                         (termination_reason: "spinning" | "oscillating" |
                          "structural" | "diminishing_returns")
running  -> aborted      User chose abort during escalation, or concurrent
                         collision detected, or initial Phase 0 cancelled
                         (termination_reason: "user_abort")
running  -> error        Unrecoverable failure (2 consecutive subagent
                         crashes, etc.)
                         (termination_reason: "error")
escalated -> running     User chose continue during escalation; the firing
                         detector's strike counter resets to 0, others
                         remain. Loop resumes
escalated -> aborted     User chose abort during escalation
escalated -> running     User chose "refine criteria and restart"; Phase 0
                         re-runs with new criteria, artifact directory is
                         preserved for diffing
```

There is no `budget_exhausted` state. The loop has no hard iteration cap; it terminates only via `complete`, `escalated`, `aborted`, or `error`.
