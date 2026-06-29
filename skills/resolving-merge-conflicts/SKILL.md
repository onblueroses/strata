---
name: resolving-merge-conflicts
description: "Resolve an in-progress git merge or rebase conflict by recovering each side's original intent, preserving both where compatible, and finishing the merge after the project's own checks pass. Reconstructs why each conflicting change was made (commit messages, PRs, issues) before touching a hunk, never invents new behaviour, and always resolves rather than aborting. Auto-trigger when a git merge, rebase, cherry-pick, or stash-pop reports conflicts (CONFLICT markers, 'Unmerged paths', 'fix conflicts and then run', 'needs merge'), when /collect hands off a worktree merge that conflicted, or when the user asks to resolve, finish, or continue a stuck merge or rebase."
---

# Resolving Merge Conflicts

Goal: Land an in-progress merge or rebase with every conflict resolved to the union of both intents, the project's own checks green, and the merge or rebase committed and continued to completion.

Success means:
  - Every conflicting hunk carries a resolution grounded in why each side changed it, not a guess at the markers
  - Both intents survive where they are compatible; where they collide, the merge's stated goal wins and the trade-off is noted
  - No behaviour exists in the result that neither side introduced
  - The project's own typecheck, tests, and formatter run and pass; anything the merge broke is fixed
  - The merge or rebase is committed and continued until every commit is applied

Stop when: the working tree is conflict-free, the project checks pass, and the merge or rebase has finished (no in-progress state remains).

## Hard rules

Three rules are load-bearing; hold them even under pressure to just make it compile:

- **Recover intent before you touch a hunk.** A conflict is two intents colliding, not two text blobs. Resolve from the why, never from the markers alone.
- **Do not invent new behaviour.** The result contains exactly what one side or the other introduced. Inventing a third behaviour to dodge the conflict is the most common way a merge silently breaks production.
- **Always resolve, never `--abort`.** Aborting throws away the resolution work and the information you gathered. Drive every conflict to a decision and finish the merge.

## Procedure

1. **See the current state.** Run `git status` and `git log --oneline --graph -15` to read where the merge or rebase stands and which commits are colliding. List the conflicting files (`git diff --name-only --diff-filter=U`) and open each one to read the conflict regions in context.

2. **Find the primary sources for each side.** For every conflict, understand deeply why each change was made and what the original intent was. Read the commit messages on both sides (`git log` on each parent, `git show <sha>`), check the PRs and the issues or tickets they reference, and read enough surrounding code to know what each side was trying to accomplish. A resolution built on guessed intent is a bug waiting to surface.

3. **Resolve each hunk.** Preserve both intents where they compose. Where they are incompatible, pick the side matching the merge's stated goal and note the trade-off in the commit message or a code comment so the loser is recoverable. Do not invent new behaviour to paper over the collision. Resolve every hunk; never `--abort`.

4. **Discover and run the project's automated checks.** Find what the project actually runs (package.json scripts, Makefile, justfile, pyproject, CI config) and run them in order: typecheck, then tests, then formatter. Fix anything the merge broke; a merge that resolves cleanly but fails tests is not resolved.

5. **Finish the merge or rebase.** Stage everything (`git add -A`) and commit. For a merge, `git commit` (the default merge message is fine; extend it with any noted trade-offs). For a rebase, `git rebase --continue` and repeat the whole procedure for each subsequent commit that conflicts, until every commit is applied and no in-progress state remains.

## Worktree merges (/collect handoff)

The `/collect` flow merges parallel worktree branches back to the base and emits `# If conflicts: resolve, then git add . && git commit` with no procedure behind "resolve". This skill is that procedure: when a `/collect` merge step conflicts, run the five steps above on it before moving to the next branch in the merge order. The branches are independent agent work, so step 2 (recover intent) leans on each branch's `.task-result.md` Surprises section and commit history rather than tickets.

After a clean resolution, if your workspace pre-authorizes force-push (warn first only when the target is `main` or `master`), a finished rebase can be pushed without a separate confirmation.

Ported from mattpocock/skills (skills/engineering/resolving-merge-conflicts), release mattpocock-skills@1.0.0.
