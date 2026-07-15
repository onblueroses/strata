---
description: |
  End session. Writes daily note JSON, commits work, updates entity summaries, syncs.
  Auto-trigger: MANDATORY when session is ending, user says goodbye/done/wrap up/thanks/
  that's all/signing off/goodnight, or before closing. Invoke even for short sessions.
---

# End Session

Goal: Close the session by capturing daily note state, committing work, reconciling entities, syncing, and writing field-agent results when dispatched.

Success means:
  - Steps 1-7 run in order, with Priority Mode applying only where specified.
  - Daily note `$KB_DIR/daily/YYYY-MM-DD-{slug}-{sessionId}.json` uses the Step 3 JSON schema and carries accurate summary, outputs, entities, tags, takeaway, and commit hashes.
  - `/commit` handles work from this session, entity summaries reflect changed state, sync behavior follows Step 6, and field-agent sessions write `.task-result.md` (when status is complete | partial | failed) or `.task-blocked.md` (when status is blocked).

Stop when: The daily note is written or verified, applicable commits and pushes finish, entities and sync are handled, and the required final confirmation line is returned.

Execute steps 1-7 in order. Apply each step whose condition matches. Low context or trivial session? Use Priority Mode (end).

## 1. Find and name daily note

Find in `$KB_DIR/daily/`: match today's date + session ID from SessionStart hook (or `$STATE_DIR/auto-context-save.md` after compaction, or most recent `*-unnamed-*.json`). Use the daily-note path shape `$KB_DIR/daily/YYYY-MM-DD-{slug}-{sessionId}.json`. If hooks disabled: create stub using step 3 schema.

**Name** (if `unnamed` present): choose 2-3 words, `{noun}-{verb}` format (e.g. vault-move, api-deploy). Rename file and update `session_name` field inside.

## 2. Commit and push work

Run `git status --short` and `git status -sb` in all repos you touched this session (parallel).

For each repo with uncommitted changes from your work:
1. Invoke `/commit` to group and commit them atomically. Save hashes for step 3.
2. Run `git push` immediately after committing. Report failure once and continue.

Also check for repos already ahead of origin (`[ahead X]` in `git status -sb`) and push those too, including repos with only earlier session commits. This catches commits made during the session that remain unpushed.

Mention pre-existing changes and leave them uncommitted. Skip repos with a clean worktree that are synced with origin.

## 3. Write daily note

Write or verify the daily note before ending; **MUST** complete this step because the daily note preserves session state across closures.

**Guard:** Read existing. If `summary` non-null and accurate, skip to step 4. If incomplete, merge (detailed summary wins, union arrays, keep specific takeaway).

Schema:
```json
{
  "date": "YYYY-MM-DD", "session_id": "...", "session_name": "...",
  "project_dir": "...", "started": "...", "ended": "HH:mm",
  "summary": "2-5 sentences", "decisions": ["choice + why"],
  "outputs": ["path (what changed)"], "entities_touched": ["$KB_DIR/projects/x"],
  "tags": ["2-3"], "takeaway": "one sentence"
}
```

**Fields:**

- `summary`: 400-600 chars. Use an action-complications-resolution arc with specifics (numbers, paths). No "In this session" opening - lead with what happened.
- `decisions`: Record choices where alternatives existed. Formats: "Chose X over Y because Z" / "Left X unchanged because Y" / "Deferred X because Z". Exclude methods ("used subagents for speed", "ran tests in parallel") - those are process details outside the decision list.
- `outputs`: List paths + parentheticals. 10+: summarize by area. End with `"Git: repo-name abc1234"`. `[]` ok for research.
- `entities_touched`: Map modified paths to entities via the Entities table in MEMORY.md (in context) - match the `Local` column to files changed. Cross-check: Deployed to VPS? +`$KB_DIR/areas/infrastructure`. Changed `.claude/`? +`$KB_DIR/areas/claude-code-setup`.
- `tags`: Free-form (3-7 tags). Suggested vocab: deploy, security, frontend, skill, infrastructure, content, knowledge-system, git, design, research, automation.`
- `takeaway`: **Test:** cover the summary with your hand and read the takeaway alone - does it teach something useful on its own? When it reads as a compressed restatement, rewrite it. Routine sessions: state the main outcome.

**Verify:** Confirm takeaway independent? Entities complete? Outputs have descriptions? Commit hashes present?

## 4. Reconcile entities

Reconcile entity summaries when Step 3 touched entity-scoped files. Apply the three gates below in order; the first gate that matches short-circuits the rest.

<details>
<summary>Reconcile entities</summary>

**Apply gates in this order. First match wins:**

**Gate 1 — Empty-entities fast skip.** Check `entities_touched` from Step 3. If it is empty (zero entity-scoped files modified this session), skip Step 4 entirely — autoend-state gate, lock gate, and 4.1-4.6 included. Jump to Step 5. Preserve existing `last_run` because the session contributed zero entity state. This is the cheap path for pure Q&A or knowledge-base sessions.

**Gate 2 — Auto-end skip.** Read `$STATE_DIR/autoend-state.json` (create parent dir if needed). If missing, treat as `{ "last_run": null, "sessions_since": 0 }`. Increment `sessions_since` by 1 immediately. Then apply the skip if all three conditions hold:
- `last_run` is not null
- fewer than 4 hours since `last_run` (strict less-than; exactly 4 hours fails the skip)
- `sessions_since` < 5

If skipping: write `{ "last_run": "<existing value>", "sessions_since": <incremented value> }` back to `autoend-state.json`. Jump to Step 5.

**Gate 3 — Lock gate.** Check `$STATE_DIR/autoend.lock`. If it exists and was modified within the last 5 minutes, a concurrent session is reconciling — skip, write incremented `sessions_since`, jump to Step 5. Otherwise: create the lock file (write current ISO timestamp as contents). Proceed with 4.1-4.6 below. Delete the lock file after 4.6 completes (even if steps error).

**Reconcile path (gates 1-3 passed).** Proceed with steps 4.1-4.6. After 4.6, write `{ "last_run": "<ISO timestamp>", "sessions_since": 0 }` to `autoend-state.json`.

**Schema:** `{ "last_run": "ISO-8601 or null", "sessions_since": integer }`

Read all `entities_touched` summaries in parallel. Leave summaries unchanged when the session left documented state unchanged.

**4.1 Update summary.md:** Fix stale status/progress, arch/tech, tables, paths. Edit actual inaccuracies only.

**4.2 Update items.json:** Read when session produced structured facts (values, gotchas, ports, versions) absent from summary. New entries: next ID in sequence. Schema: `[{"id","type","subject","fact","date","source"}]`.

**4.3 Set last_verified:** `last_verified: YYYY-MM-DD` after `## Status`. Warn if previous >7 days.

**4.4 Recent Sessions:** Add `| YYYY-MM-DD | session-name (session_id) | one-line |`. Then enforce the 10-row cap actively: count rows AFTER your insert; if >10, delete oldest rows (bottom of table) until exactly 10 remain. This applies even if the prior table was already over the cap (it can drift via direct edits). Ensure blank line before `## Links`.

**4.5 Cross-entity consistency (2+ entities only):** Check shared facts (auth status, PM2, ports, versions, domains, crons) between site entities + `infrastructure`. Fix stale side.

**4.6 Create if missing:** Make directory + `summary.md` (`# Name`, `## Status`, `## Details`, `## Recent Sessions`, `## Links`) + `items.json` as `[]`.

</details>

## 5. Tacit knowledge

Append to `$KB_DIR/tacit.md` (cap 20, prune oldest) when a new preference/constraint was observed.

## 6. Sync

Sync `$KB_DIR` with the exact command below.

```bash
cd $KB_DIR && git add -A && { git diff --cached --quiet && echo "Nothing to sync" || { git commit -m "Auto-sync: SESSION_NAME (YYYY-MM-DD HH:mm)" && git push; }; }
```
Replace SESSION_NAME, use current time. When push fails, report once and continue (Stop hook backs up).

**Confirm:** Report session name, entities updated (what changed), sync status, warnings. Keep it brief. Final line: `Session closed cleanly. No issues. You can close this terminal.` OR `Session closed with issues: [list]. Address these before closing.`

---

## Field Agent Mode (dmux dispatch)

Detect field agent mode before step 1 by checking whether `.task-brief.md` exists in the current working directory. If yes, activate field agent mode for this dispatched field agent session.

**Read the brief:** Parse the YAML frontmatter to extract `id`, `entity`, `scratchpad`, and `siblings`.

**Execute normal /end steps (1-5)** as usual. Leave step 6 (sync) for the parent session because multiple field agents finishing simultaneously would cause git conflicts in `$KB_DIR/`. The parent session syncs after `/collect`. Then execute the additional step below.

### 7. Write task result

Write `.task-result.md` in the current working directory after all normal /end steps complete:

```markdown
---
id: {id from .task-brief.md}
status: {complete|partial|failed}    # blocked sessions write .task-blocked.md instead — see Status determination below
completed: {ISO timestamp}
files_changed:
  - {from git diff --name-only against branch_from}
tests_passed: {true|false|unknown}
merge_order_hint: {merge-first|no-dependency|merge-after:{slug}}
---

## Summary
{Reuse the summary from the daily note (step 3) - same 2-5 sentences}

## Decisions
{Reuse decisions array from daily note, one per line with bullet}

## Surprises
{Things discovered that the parent orchestrator didn't anticipate.
If nothing surprising: "None - task executed as briefed."}

## Integration Notes
{What the parent needs to know for merge:
- Env vars that need to be set
- Config changes required
- Files that other tasks may need to update after merge
- Suggested merge order rationale
If straightforward: "Clean merge expected, no special handling needed."}
```

**Status determination:**
- `complete`: all acceptance criteria from the brief are met
- `partial`: some criteria met, work is usable but incomplete
- `blocked`: write only `.task-blocked.md`; blocker prevents meaningful progress
- `failed`: attempt made and meaningful progress remained out of reach

**merge_order_hint:**
- `merge-first`: this task changes interfaces/types that siblings depend on
- `no-dependency`: independent, can merge in any order
- `merge-after:{slug}`: depends on another task's changes being merged first

**Scratchpad reminder:** When the brief had `scratchpad: true` and sibling-useful discoveries exist, ensure `.dmux/scratchpad/{your-slug}.md` contains them before ending.

---

## Priority Mode

Execute only: 1 (find+name), 2 (commit), 3 (write note), 6 (sync) when context is low, session <15min, or rush applies. Defer 4-5 - caught by the next staleness check or Stop hook fallback. In field agent mode, still write `.task-result.md` (step 7) even in priority mode - the parent needs it.
