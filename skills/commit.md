# Commit

Groups uncommitted changes into logical atomic commits. One `/review` pass, automatic grouping, dependency-ordered commits.

## Usage

```
/commit                # Group and commit all uncommitted changes
/commit --push         # Same, then push after all commits
/commit --dry-run      # Show proposed groups without committing
```

Arguments via `$ARGUMENTS`.

---

## Instructions

### 0. Check /verify prerequisite

Look for `.claude/.verify-passed-{sessionId}`. If the file doesn't exist but `.claude/.session-edits-{sessionId}` has entries, stop and tell the user to run `/verify` first. Committing unverified changes defeats the purpose.

### 1. Gather changes

```bash
git status --short
git diff HEAD --stat
git diff HEAD
```

If working tree is clean: say "Nothing to commit" and stop.

**Save the full diff and file list** - you need them for steps 2-4.

### 2. Run /review once

Invoke `/review --all`. This covers the entire diff in one pass. If review finds CRITICAL issues, stop and report them. HIGH/MEDIUM issues: note them but proceed (user already saw the review output).

### 3. Group changes by intent

Analyze the diff and group files that belong to the same logical change. This is the core algorithm.

**Grouping heuristics (in priority order):**

1. **Shared purpose.** Files that implement the same feature, fix, or refactor go together. A `.ts` file + its `.test.ts` + related `.css` = one group.
2. **Import dependencies.** If file B imports something new from file A (added this session), they're in the same group - unless A is a shared utility touched by multiple groups.
3. **Directory cohesion.** Files in the same directory changing for the same reason = one group. But don't group by directory alone - a config change and a feature change in the same dir are separate.
4. **Commit message test.** If you can't describe two files' changes in one sentence without "and", they're separate groups.

**Merge when in doubt.** Two borderline groups = one commit. Over-splitting produces commits that don't compile or don't make sense alone. A commit should be a valid, buildable state.

**Single-change shortcut.** If all files share one intent (common case), skip grouping and make one commit. Don't force-split a unified change.

**What NOT to do:**
- Don't group by file type (all .md together, all .ts together). Group by intent.
- Don't create single-file commits for minor related changes. A renamed import + the file it was renamed in = one commit.
- Don't split test files from their implementation.

### 4. Order by dependency

If commit B uses something introduced in commit A, A must come first. Check:
- New exports consumed by other groups
- Schema/type changes that other groups depend on
- Config changes that affect other groups' behavior

If no dependencies exist between groups, order by scope: infrastructure/config first, then libraries/utilities, then features, then tests-only, then docs-only.

### 5. Commit each group

For each group in order:

```bash
git add <file1> <file2> ...    # Stage only this group's files
```

Write a commit message:
- Subject line: short, imperative, describes the change (not the files)
- No body unless the change needs explanation beyond the subject
- End with `Co-Authored-By` using the model name from the system prompt

```bash
git commit -m "$(cat <<'EOF'
Subject line here

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
EOF
)"
```

**Save each commit hash** - report them at the end.

Between commits, verify the working tree is in a consistent state. If staging a subset would leave the repo in a broken state (e.g., file A references file B but B isn't staged yet), merge those groups.

### 6. Push (if --push)

```bash
git push
```

If push fails (e.g., no upstream, auth), report the error. Don't retry or force-push.

### 7. Report

```
COMMIT SUMMARY
==============
[N] commits created

1. abc1234 - Subject line (3 files)
2. def5678 - Subject line (2 files)
3. ghi9012 - Subject line (1 file)

[Pushed to origin/branch-name]  # only if --push succeeded
```

If `--dry-run`, show the proposed groups with their files and draft messages, but don't stage or commit anything.

---

## Quality self-check

Before committing, verify:
1. Each commit can stand alone (no broken intermediate states)?
2. No file appears in multiple groups?
3. Test files grouped with their implementation, not separated?
4. Commit messages describe intent, not just "update files"?
5. Dependencies ordered correctly (no forward references)?

## DO NOT

- **DO NOT ask for approval on grouping.** This is fully automatic. User can `git reset HEAD~N` if unhappy.
- **DO NOT run /review per commit.** One pass covers everything.
- **DO NOT create empty commits or commits with only whitespace changes.**
- **DO NOT force-push.** Ever.
- **DO NOT split a feature across commits** unless parts are truly independent.
- **DO NOT use generic messages** like "misc changes", "updates", "various fixes". Each commit message should be specific.
