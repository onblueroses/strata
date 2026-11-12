# Shared Obsidian brain

This is a shared Obsidian vault with a root [rule book](vault-AGENTS.md). A laptop copy and a server copy merge through Obsidian Sync; a headless client keeps the server copy current, and agents reach the server copy through an MCP server without a delete tool. Machine writes are read back from the server copy, since a successful local write alone does not prove convergence. Files under unknown root folders are moved into the inbox after a quiet period.

The layout uses `.base` tables over Markdown records throughout. The ruling of 2026-09-06 followed a concrete need: members needed to browse the same evidence as agents without a parallel spreadsheet. Keep one home per fact: durable team knowledge in the vault, open work in the issue tracker, and compact personal state and pointers in [OptMem](../optmem/README.md). The assistant bridge treats the vault as its source of truth.

The units, the server patch and the maintenance jobs of the live vault are private.
