# Vault operating manual

Read this rule book before writing to the shared Obsidian vault. The vault is the team's durable knowledge; the issue tracker holds work and ownership. Chat is an intake surface. A decision or contact history must not exist only in chat.

## Writing rules

- Answer from a vault note and cite it. If the vault has no answer, say so.
- Extract the minimum operational fact from a private message; do not copy private conversation into shared notes. Ask before sharing ambiguous personal context.
- Write a follow-up to the issue tracker when it becomes clear. Give each open task one issue and one owner. Keep durable knowledge in its one canonical vault note; other notes link to it.
- Read back machine writes from the server copy. A successful local write does not prove that another client can see it.
- Sign frontmatter with `author: <agent>/<member>` and `date:`. For dated log lines, append `(agent/member, date)` where provenance matters. Do not put signatures into ordinary member-facing prose.
- Never put credentials, tokens, passwords, or signed URLs into the vault. The vault keeps its history.
- Use Markdown records with frontmatter, not CSV. Obsidian Sync may not carry CSV to every device.
- Keep basenames unique, use lowercase ASCII kebab case for note names, and use `[[wikilinks]]` for known entities. Create a stub before linking to a new entity. Links are the vault's main value: a mention of something the vault knows, left unlinked, is a defect, and a name that is no longer a note (a merged card, a retired file) is written in backticks, never as a link.
- Keep append-only traces immutable. A correction is a new record with `supersedes:`.

## Root and tables

The root holds a front door (`Start here.md`), the rule book (`AGENTS.md`, `CLAUDE.md`), and one folder per section below. Keep the list of allowed root folders in one place and change it together with this rule book: files under unknown or retired root folders are moved into the inbox, with their old path recorded.

Every record folder has an Obsidian `.base` table. Filter with `file.inFolder(...)`, and for Markdown records also `file.ext == "md"`. A first column can use `link(file.path, if(title.isEmpty(), file.name, title))`. Frontmatter columns need `note.<field>`; a bare property name is ignored. Declare columns that the records carry, and group only by fields most records have. A text value shaped like `scheme:rest` (a label such as `for:<member>`) renders as a link, so keep such values out of table columns. Parent tables should not exclude child `.base` files when they need category rows. This table design was adopted on 2026-09-06 so members could browse the same evidence as agents without maintaining a second spreadsheet.

## Sections

- **Front door**: a rewritten overview, never an append log.
- **Team**: one page per member, canon, and versioned master documents. Current assignments are read from the issue tracker.
- **Contacts**: person and organization records, conversations and calls. Inclusion means directory membership only; it is not permission to contact anyone.
- **Research**: notes that lead with `question:`, `answer:`, and `## In short`; sources and method follow.
- **Calendar**: event records. The vault is the calendar.
- **Inbox**: unfiled captures and sync conflicts. Empty the inbox daily: file each capture to its canonical note and preserve the original with `filed_to:`, or leave it pending with a clear reason.
- **Agents**: generated lists, frozen evidence, decisions, templates and traces. A frozen corpus is not live canon.

## Contact records

Keep one card per person and one per organization. Search by name before creating one. The body is an append-only dated log; update by appending history, not rewriting it. An interaction updates the card and appends a dated log line; a list or report does not replace the card.

## Calendar

An event note has `type: event`, `title`, `day`, optional `start` and `end`, `all_day`, `tz`, `attendees`, `source`, `date`, and `author`. Date-only events have `all_day: true` and no invented hour.

## Decisions and ownership

Decision records have `ruling:` and `status:`. A replacement sets the old record to `superseded`, points `superseded_by:` to the new record, and links back with `supersedes:`. The issue tracker carries work, one owner label per open issue, and signed transitions. Delegation does not change the human owner of the outcome. Search for an existing issue before creating another.

Obtain a human decision before spending money, deploying to production, deleting, changing schema or architecture, overwriting another person's work, or granting new access. These actions can change cost, shared behavior, data, or trust boundaries; tool access alone is not approval. If the operator has already asked for a specific action, that request is the decision unless a separate spending, disclosure, communication, or irreversible-destruction gate applies.
