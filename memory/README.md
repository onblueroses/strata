# Memory

OptMem holds compact state, events, durable facts, and pointers in an append-only log. Rich personal documents live in a notes tree; OptMem points to them rather than copying them into the log. The note contract and primary/delegate boundary are in [Knowledge Management](../reference/knowledge-management.md).

The shared Obsidian vault holds team knowledge and its rule book. The issue tracker owns open work and assignment. A bridge reads the vault as its source of truth, and machine writes are verified against the server copy. Start with the [vault design](brain/README.md) and the [vault rule book](brain/vault-AGENTS.md).

## Agent messages are kept forever

Every message one agent sends another is kept, on the laptop and the server, for every runtime and resident ([ruling of 2026-11-02](../decisions/2026-11-02-agent-messages-kept-forever.md)). The messages stay in their own stores: the peer-messaging databases, session transcripts, the letters folder, worker and bridge state, and the tracker's event log and comments. A channel map in the notes tree names each channel, where its messages live and how it is backed up. A regular export writes each channel's messages of the day as readable text into the notes tree, one file per channel and day; a written day is never edited. The messages are backed up off the machine. No store is pruned, rotated away or reset without an archive, and a new channel gets its durable log before its first message.
