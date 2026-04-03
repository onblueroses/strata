# End Session

Execute steps 1-7 in order. Skip where nothing applies. Low context or trivial session? Use Priority Mode (end).

## 1. Find and name daily note

Find in `$STRATA_KB/daily/`: match today's date + session ID from SessionStart hook (or `.claude/auto-context-save.md` after compaction, or most recent `*-unnamed-*.json`). If hooks disabled: create stub using step 3 schema.

**Name** (if `unnamed` present): 2-3 words, `{noun}-{verb}` format (e.g. vault-move, api-deploy). Rename file and update `session_name` field inside.

## 2. Commit work

Run `git status --short` in all modified repos (parallel). For each repo with your changes, invoke `/commit` to group and commit them atomically. Save hashes for step 3. Mention but don't commit pre-existing changes. Skip if clean.

## 3. Write daily note

**Guard:** Read existing. If `summary` non-null and accurate, skip to step 4. If incomplete, merge (detailed summary wins, union arrays, keep specific takeaway).

Schema:
```json
{
  "date": "YYYY-MM-DD", "session_id": "...", "session_name": "...",
  "project_dir": "...", "started": "...", "ended": "HH:mm",
  "summary": "2-5 sentences", "decisions": ["choice + why"],
  "outputs": ["path (what changed)"], "entities_touched": ["$STRATA_KB/projects/x"],
  "tags": ["2-3"], "takeaway": "one sentence"
}
```

**Fields:**

- `summary`: 400-600 chars. Action-complications-resolution arc. Specifics (numbers, paths). No "In this session" opening - lead with what happened.
- `decisions`: Choices where alternatives existed. Formats: "Chose X over Y because Z" / "Left X unchanged because Y" / "Deferred X because Z". NOT methods ("used subagents for speed", "ran tests in parallel") - those are how, not what was decided.
- `outputs`: Paths + parentheticals. 10+: summarize by area. End with `"Git: repo-name abc1234"`. `[]` ok for research.
- `entities_touched`: Map modified paths to entities via the Entities table in MEMORY.md (always in context) - match the `Local` column to files changed. Cross-check: Deployed to VPS? +`$STRATA_KB/areas/infrastructure`. Changed `.claude/`? +`$STRATA_KB/areas/my-area`.
- `tags`: From vocab: `deploy`, `security`, `frontend`, `skill`, `infrastructure`, `content`, `knowledge-system`, `git`, `vps`, `design`, `research`, `automation`. Max 1 custom.
- `takeaway`: **Test:** cover the summary with your hand and read the takeaway alone - does it teach something useful on its own? If it's just a compressed restatement, rewrite it. Routine sessions: state the main outcome.

**Verify:** Takeaway independent? Entities complete? Outputs have descriptions? Commit hashes present?

## 4. Reconcile entities

<details>
<summary>Reconcile entities</summary>

**Dream-state gate:** Read `~/.claude/state/dream-state.json`. If missing, treat as `{ "last_run": null, "sessions_since": 0 }`.

Increment `sessions_since` by 1 immediately (before the skip check below).

**Skip reconciliation (steps 4.1-4.6) if ALL are true:**
- `last_run` is not null
- fewer than 4 hours since `last_run`
- `sessions_since` < 5

If skipping: write `{ "last_run": "<existing value>", "sessions_since": <incremented value> }` back to `dream-state.json`. Jump to Step 5.

If running: proceed with steps 4.1-4.6 below. After 4.6, write `{ "last_run": "<ISO timestamp>", "sessions_since": 0 }` to `dream-state.json`.

**Schema:** `{ "last_run": "ISO-8601 or null", "sessions_since": integer }`

Read all `entities_touched` summaries in parallel. **Skip if** session didn't change documented state.

**4.1 Update summary.md:** Fix stale status/progress, arch/tech, tables, paths. Edit only if actually wrong.

**4.2 Update items.json:** **Only read if** session produced structured facts (values, gotchas, ports, versions) not in summary. New entries: next ID in sequence. Schema: `[{"id","type","subject","fact","date","source"}]`.

**4.3 Set last_verified:** `last_verified: YYYY-MM-DD` after `## Status`. Warn if previous >7 days.

**4.4 Recent Sessions:** Add `| YYYY-MM-DD | session-name (session_id) | one-line |`. Cap 10 rows. Ensure blank line before `## Links`.

**4.5 Cross-entity consistency (2+ entities only):** Check shared facts (auth status, PM2, ports, versions, domains, crons) between touched entities + `infrastructure`. Fix stale side.

**4.6 Create if missing:** Make directory + `summary.md` (`# Name`, `## Status`, `## Details`, `## Recent Sessions`, `## Links`) + `items.json` as `[]`.

</details>

## 5. Mycelium departure notes

**Skip if** `mycelium.sh` is not installed or no files were edited this session.

Write departure notes for files edited during this session so future agents know what happened. Uses the session edits file that `track-edits.sh` already maintains.

1. Read `.claude/.session-edits-{sessionId}` to get the list of edited files.
2. For each edited file that lives inside a git repo:
   - Determine the appropriate kind: `warning` if the change introduced a known gotcha or fragile area, `context` for normal work.
   - Write a one-line note summarizing what changed and why (derive from commit message or session summary):
     ```bash
     cd [repo-root] && mycelium.sh note [file-path] --slot [sessionId] -k context -m "[summary]"
     ```
3. If many files were edited in the same repo (5+), write a single note on HEAD instead of per-file, listing the files in the body.
4. Only write notes when a future agent would genuinely benefit. Skip trivial edits (formatting, typos, config bumps).

## 6. Tacit knowledge

**Skip unless** new preference/constraint observed. Append to `$STRATA_KB/tacit.md` (cap 20, prune oldest).

## 7. Sync

```bash
cd $STRATA_KB && git add -A && { git diff --cached --quiet && echo "Nothing to sync" || { git commit -m "Auto-sync: SESSION_NAME (YYYY-MM-DD HH:mm)" && git push; }; }
```
Replace SESSION_NAME, use current time. If push fails, report but don't retry (Stop hook backs up).

**Confirm:** Session name, entities updated (what changed), sync status, warnings. Brief. Final line: `Session closed cleanly. No issues. You can close this terminal.` OR `Session closed with issues: [list]. Address these before closing.`

---

## Priority Mode

Context low / session <15min / rush? Execute only: 1 (find+name), 2 (commit), 3 (write note), 7 (sync). Defer 4-6 - caught by next `/reconcile`, staleness check, or Stop hook fallback.
