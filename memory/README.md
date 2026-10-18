# Memory

OptMem holds compact state, events, durable facts, and pointers in an append-only log. Rich personal documents live in a notes tree; OptMem points to them rather than copying them into the log. The note contract and primary/delegate boundary are in [Knowledge Management](../reference/knowledge-management.md).

The shared Obsidian vault holds team knowledge and its rule book. The issue tracker owns open work and assignment. A bridge reads the vault as its source of truth, and machine writes are verified against the server copy. Start with the [vault design](brain/README.md) and the [vault rule book](brain/vault-AGENTS.md).
