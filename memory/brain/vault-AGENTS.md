# Vault operating manual

Read this rule book before writing to the shared Obsidian vault. The vault is the team's durable knowledge; the issue tracker holds work and ownership. Chat is an intake surface. A decision or contact history must not exist only in chat.

## Writing rules

- Answer from a vault note and cite it. If the vault has no answer, say so.
- Extract the minimum operational fact from a private message; do not copy private conversation into shared notes. Ask before sharing ambiguous personal context.
- Write a follow-up to the issue tracker when it becomes clear. Give each open task one issue and one owner. Keep durable knowledge in its one canonical vault note; other notes link to it.
- Read back machine writes from the server copy. A successful local write does not prove that another client can see it.
- Sign frontmatter with `author: <agent>/<member>` and `date:`. For dated log lines, append `(agent/member, date)` where provenance matters. Do not put signatures into ordinary member-facing prose.
- Never put credentials, tokens, passwords, or signed URLs into the vault. The snapshot captures history.
- Use Markdown records with frontmatter, not CSV. Obsidian Sync may not carry CSV to every device.
- Keep basenames unique, use lowercase ASCII kebab case for note names, and use `[[wikilinks]]` for known entities. Create a stub before linking to a new entity.
- Keep append-only traces immutable. A correction is a new record with `supersedes:`.
- **Keep the team's name inside the team.** Until the operator rules otherwise, do not put it in mail, a demo, a calendar invite, a shared document, or a public artifact. The 2026-09-06 ruling preserves a private team identity while members communicate through their own approved sender identities. Check drafts before they leave the team.

## Root and tables

The human path is numbered: `Start here.md`, `0 Company/`, `1 CRM/`, `2 Market/`, `3 Research/`, `4 Calendar/`, `5 Inbox/`; `9 Agents/` holds agent library and machine records. `AGENTS.md` and `CLAUDE.md` may also be at the root. A root mirror may be added through the sweep configuration. Keep the root list here and the sweep's root configuration together: a mirror once got flattened into captures because the prose list changed before the sweep list. After a quiet period, narrowly classified out-of-scope content moves from anywhere outside `9 Agents/` and mirrors to a holding tree outside the vault, with a manifest. Unknown or retired root paths then move to `5 Inbox/captures/`, with their old path in `swept_from:` and an append-only trace. A young classified file blocks the whole classified batch and does not fall through to captures.

Every record folder has an Obsidian `.base` table. Filter with `file.inFolder(...)`, and for Markdown records also `file.ext == "md"`. A first column can use `link(file.path, if(title.isEmpty(), file.name, title))`. Frontmatter columns need `note.<field>`; a bare property name is ignored. Declare columns that the records carry, and group only by fields most records have. Parent tables should not exclude child `.base` files when they need category rows. This table design was adopted on 2026-09-06 so members could browse the same evidence as agents without maintaining a second spreadsheet.

## Sections

- `Start here.md` is a rewritten front door, never an append log.
- `0 Company/` holds the company page, one team page per member, canon, and versioned master documents. Current assignments are read from the issue tracker.
- `1 CRM/` holds person and organization records, conversations, calls, reports, and templates. Inclusion means directory membership only; it is not permission to contact anyone.
- `2 Market/` holds category, competitor, buyer, and possible domain records, with one prose overview and one canonical source for stated numbers.
- `3 Research/` holds papers, domain notes, architecture, and reading lists. Member-facing research notes lead with `question:`, `answer:`, and `## In short`; sources and method follow.
- `4 Calendar/` holds event, conference, and current-status records. The vault is the calendar; a conference shortlist item is not an event until attendance is decided.
- `5 Inbox/captures/` holds unfiled captures and sync conflicts. Empty the inbox daily: file each capture to its canonical note and preserve the original with `filed_to:`, or leave it pending with a clear reason.
- `9 Agents/library/` is a shelf for generated lists and frozen evidence. `9 Agents/machine/` holds decisions, templates, traces, registries, and archives. A frozen corpus is not live canon.

## CRM record contract

Keep one card per person and one per organization. Search by name and address before creating one. Person frontmatter can carry `type`, `name`, `company`, `role`, `email`, `channel`, `campaign`, `lane`, `owner`, `status`, `sent`, `last_touch`, `next_action`, `next_touch`, and `source`. `company` is a wikilink. The body is an append-only dated log. A status only climbs; update by appending history, not rewriting it. `last_touch` means contact actually happened. A scouted card has no `last_touch`.

A `hook:` is one checkable, sourced clause. Empty is acceptable; invention is a defect. A send, reply, booked call, decline, or requested follow-up updates the person card and appends a dated log line. A list or report does not replace the card. Whenever `next_action` changes, also set `next_touch` to an ISO date. Due follow-ups can be bundled for a member rather than sent as individual interruptions.

Each substantive external interaction gets one frontmatter conversation record, linked to the person, organization, and any call note. A later exchange gets a new card. Automated replies are not conversations; record `conversation_card: not-applicable` with a dated reason. A call note links its calendar event, and the event links back. A transcript belongs in the call note, not in captures. Address corrections use a guarded path that checks a suppression register, preserves history, and treats a replacement as unprobed; a replacement does not grant sending permission.

## Calendar and whereabouts

An event note has `schema`, `type: event`, `title`, `day`, optional `start` and `end`, `all_day`, `tz`, `attendees`, `source`, `date`, and `author`. Date-only events have `all_day: true` and no invented hour. `attendees` use member or CRM wikilinks, or `team`. Past events remain available through a table view. Calendar views provide one lane per member; an event with `team` appears in each lane.

`4 Calendar/now/now-<member>.md` holds current status. A deterministic schedule job owns `doing`, `doing_at`, and `doing_source`; a member's message supplies `where`, `where_as_of`, and `reported_by`. A self-report outranks an event-derived place. Never infer location from a timezone or an event without a place. Read the record afresh before answering a whereabouts question, and include the report date so stale information looks stale. This separation was ruled on 2026-08-28 after event-derived presence proved too weak to stand in for what a member said.

## Decisions and ownership

Decision records have `ruling:` and `status:`. A replacement sets the old record to `superseded`, points `superseded_by:` to the new record, and links back with `supersedes:`. The issue tracker carries work, one owner label per open issue, and signed transitions. Delegation does not change the human owner of the outcome. Search for an existing issue before creating another.

Obtain a human decision before spending money, deploying to production, deleting, changing schema or architecture, overwriting another person's work, or granting new access. These actions can change cost, shared behavior, data, or trust boundaries; tool access alone is not approval. If the operator has already asked for a specific action, that request is the decision unless a separate spending, disclosure, communication, or irreversible-destruction gate applies.
