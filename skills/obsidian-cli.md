# Obsidian CLI

Manage Obsidian vaults from the command line.

## Note Operations

### Read notes
```bash
obsidian-cli read "path/to/note.md"          # Read full note
obsidian-cli read "path/to/note.md" --json   # JSON output with frontmatter parsed
obsidian-cli search "query text"             # Full-text search
obsidian-cli search "query" --tag project    # Search with tag filter
```

### Create and edit
```bash
obsidian-cli create "path/to/new-note.md" --content "# Title\n\nContent"
obsidian-cli edit "path/to/note.md" --append "New content at end"
obsidian-cli edit "path/to/note.md" --prepend "Content at start"
```

### Properties (frontmatter)
```bash
obsidian-cli props get "note.md"                    # Read all properties
obsidian-cli props set "note.md" status active      # Set a property
obsidian-cli props delete "note.md" old_field       # Remove a property
```

### Tasks
```bash
obsidian-cli tasks list                              # All tasks
obsidian-cli tasks list --status incomplete          # Uncompleted tasks
obsidian-cli tasks list --tag project --due today    # Filtered tasks
obsidian-cli tasks complete "note.md" 5              # Complete task on line 5
```

## Plugin Development

```bash
obsidian-cli dev reload "plugin-id"           # Reload plugin after changes
obsidian-cli dev run "console.log('test')"    # Execute JS in Obsidian context
obsidian-cli dev errors                       # Capture console errors
obsidian-cli dev screenshot                   # Take vault screenshot
obsidian-cli dev inspect ".workspace"         # Inspect DOM element
```

## Vault Management

```bash
obsidian-cli vault list                       # List all known vaults
obsidian-cli vault open "Vault Name"          # Open vault in Obsidian
obsidian-cli vault stats                      # Note count, tag stats, etc.
```

## Common Patterns

### Batch update frontmatter
```bash
# Add a property to all notes in a folder
for f in path/to/folder/*.md; do
  obsidian-cli props set "$f" reviewed false
done
```

### Export search results
```bash
obsidian-cli search "TODO" --format json | jq '.[] | .path'
```

## Anti-Examples

| Bad | Why | Better |
|-----|-----|--------|
| Editing vault files directly while Obsidian is open | Risk of conflicts, lost changes | Use CLI or close Obsidian first |
| Using sed/awk on markdown with frontmatter | Easy to corrupt YAML frontmatter | Use `obsidian-cli props` for frontmatter |
| Searching with grep instead of CLI | Misses Obsidian-specific features (tags, links) | Use `obsidian-cli search` |
