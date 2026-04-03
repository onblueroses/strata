# Mycelium

Read or write file-level agent notes via git notes. Notes persist across sessions and are invisible to the working tree.

```
/mycelium read src/auth.ts       # Read all notes about a file
/mycelium write src/auth.ts      # Write a note about a file
/mycelium status                 # What notes exist in this repo
```

Arguments via `$ARGUMENTS`.

## Skip Conditions

- **Skip if** not inside a git repository
- **Skip if** mycelium.sh is not installed (`which mycelium.sh` fails)

---

## Slot Convention

Every instance writes to its own slot, keyed by the 8-char session ID (the suffix from the daily note filename). This prevents concurrent instances from overwriting each other's notes.

```bash
# Session a1b2c3d4 writes to its own slot:
mycelium.sh note src/auth.ts --slot a1b2c3d4 -k warning -m "Rate limiter bypassed on retry"

# Reading aggregates ALL slots automatically:
mycelium.sh context src/auth.ts
```

**Your session ID** is the 8-char suffix from the SessionStart hook output (e.g., `2026-03-31-feature-work-a1b2c3d4.json` -> `a1b2c3d4`).

## Note Kinds

| Kind | When to use | Example |
|------|-------------|---------|
| `warning` | Fragile areas, footguns, things that break non-obviously | "Retry path bypasses rate limiter" |
| `context` | Background needed before touching this code | "Refactored to use new node API" |
| `decision` | Why something was chosen - rationale that outlives commits | "JWT over sessions: stateless for CDN edge" |
| `constraint` | Hard rules that must be respected | "Must be retryable, no side effects" |
| `observation` | Something noticed but not acted on | "This function is called 3x more than expected" |

## Commands

### Read notes about a file or commit

```bash
# Everything known about a file (aggregates all slots)
mycelium.sh context src/auth.ts

# Read a specific object's note
mycelium.sh read HEAD

# Follow edges to related notes
mycelium.sh follow HEAD

# Find all notes of a kind
mycelium.sh find warning
```

### Write a note

```bash
# Always use your session ID as the slot
mycelium.sh note <target> --slot <sessionId> -k <kind> -m "<body>"

# Examples:
mycelium.sh note src/auth.ts --slot a1b2c3d4 -k warning -m "Rate limiter bypassed on retry path"
mycelium.sh note HEAD --slot a1b2c3d4 -k decision -m "Chose streaming over polling for real-time updates"
```

### Check repo state

```bash
mycelium.sh kinds          # What kinds are in use
mycelium.sh list           # All annotated objects
mycelium.sh log 10         # Last 10 commits with their notes
mycelium.sh doctor         # Consistency check
mycelium.sh compost . --report  # Count stale notes
```

## Repository Setup

<details>
<summary>Repository Setup</summary>

Git notes don't travel with normal push/pull. Each repo needs a one-time setup to sync notes:

```bash
mycelium.sh sync-init    # Adds fetch/push refspecs for notes
```

**Ask first** before running sync-init. It modifies the repo's git config to include `refs/notes/mycelium*` in fetch/push refspecs.

After sync-init, notes travel with regular `git fetch` and `git push`.

</details>

## Staleness

Notes attached to file blobs go stale when the file changes (the blob OID changes). Stale notes are still visible but flagged:

```bash
mycelium.sh compost src/auth.ts --dry-run    # List stale notes
mycelium.sh compost src/auth.ts --compost    # Archive stale notes
mycelium.sh compost src/auth.ts --renew      # Re-attach to current version
```

## DO NOT

- Write to another session's slot - use your own session ID only
- Write notes with sensitive data (keys, passwords) - notes are public for public repos
- Write notes about every file you touch - only write when there's something a future agent needs to know
- Run sync-init without asking - it changes git config
