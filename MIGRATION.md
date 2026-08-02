# Migration

This release removes Strata's custom knowledge-base commands, entity templates, session journals, and their hooks. It also removes the Stop hook that enforced `/verify`. Claude Code's native memory remains available; `/verify` remains a voluntary self-check.

Specs, handoffs, post-compaction pointers, and the `$STRATA_HOME` / `$KB_DIR` / `$STATE_DIR` / `$SPECS_DIR` path contract remain.

## Existing installs

After pulling the release, re-run the initializer:

```bash
git -C "$STRATA_HOME" pull --ff-only
"$STRATA_HOME/bin/strata-init"
```

The rerun refreshes the copied `$HOME/.claude/settings.json` and `$HOME/.claude/CLAUDE.md`. Symlinked commands and hooks update with the pull, but those copied files do not.

The initializer backs up changed copies before replacing them. It does not delete existing workspace content.
