# Keep every message between agents

Decided: 2026-11-02

Rule: Keep every message one agent sends another, on the laptop and the VPS, past and future, for every
      runtime and resident: session transcripts, the peer-messaging stores, letters, the chat agent's
      chat, worker and bridge state, the tracker's event log and its comments. Never prune, rotate away,
      cap down or reset one of these stores without an archive. A new channel gets a durable log before
      its first message.

Reason: Agents coordinate through these messages, so they are the only record of why a run did what it
        did. Retention defaults, log rotation and session cleanup delete that record silently, and a
        later review cannot recover it. A store that deletes by default is therefore treated as a bug,
        not as housekeeping.

Reopen when: A measured storage or privacy cost exceeds the value of the record, and an archive that
             keeps every message readable replaces the deletion.

Effect: Retention settings are set to keep; logs are not rotated away; an export writes the messages
        of each channel as readable text and records the state of the backups.
