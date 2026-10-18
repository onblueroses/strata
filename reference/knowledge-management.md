<!-- keywords: OptMem, memo, append-only memory, proposal inbox, drain, note grammar, UTF-8 bytes, regex recall, recall truncation, live state, document pointer, session scope, PARA, cross-linking, frozen history -->
# Knowledge Management

OptMem is the operator's operational memory. It stores compact facts, state, events, and document pointers in one append-only log. The `<notes-tree>/lore/` vault is the document layer: rich content stays in files there, and OptMem points to those files when needed. The `<notes-tree>/life/` tree keeps project and area state (specs, handoffs, operational files).

| Layer | Location | Purpose |
|---|---|---|
| Linear | a configured workspace, via `brain-linear` | Live task + decision state (`linear-spine.md`); OptMem carries no task state post-cutover, only closed-ruling mirrors |
| OptMem | `<optmem-state>/memory` | Live records and the index to documents |
| Proposal inbox | `<optmem-state>/proposals` | Detached delegated-agent candidates awaiting a user-facing primary's judgment |
| Lore vault | `<notes-tree>/lore/` | Knowledge documents: notes, research, journal + diary, entity hubs, traces; constitution `<notes-tree>/lore/CLAUDE.md` |
| PARA state | `<notes-tree>/life/{projects,areas}/` | Project and area state: specs, handoffs, operational files |

Substitute the local absolute OptMem checkout for `<optmem-root>` before running:

```bash
python3 <optmem-root>/memo <command>
```

User-facing primary Claude, primary Codex, and primary DeepSeek sessions may call `memo note` and
`memo nap` under this contract. Delegated agents never settle the store: they return canonical
candidates to their primary, or use the Proposal Inbox when a detached dispatch contract names it.

## Quick Nav

| Task | Section |
|---|---|
| Choose and write a note type | Note Grammar |
| Submit or drain a delegated candidate | Proposal Inbox |
| Read current state | Live State and Corrections |
| Recall records without losing coverage | Regex Recall and Coverage |
| Sweep every entity | Cross-Entity Discovery |
| Store a rich document | Documents and Pointer Notes |
| Find who owns a writer's note contract | Writer Contracts |
| See what OptMem reports about itself | Telemetry |
| Understand the pre-cutover files | Frozen History |
| Add a person document | People Pattern |
| Link documents | Cross-linking |

## Note Grammar

Every note is one non-empty line:

```text
TYPE ENTITY SCOPE KEY PAYLOAD
```

The complete line is at most 280 UTF-8 bytes. This is the `ENTRY_CHARS` default enforced by `check()` in `<optmem-root>/memo`; measure encoded bytes, not characters.

| Field | Allowed form | Meaning |
|---|---|---|
| `TYPE` | `F`, `S`, `E`, or `P` | The record class |
| `ENTITY` | `@e/<slug>` | Canonical lowercase entity; use `@e/operator` only when no narrower entity applies |
| `SCOPE` | `@g` or `@s/<id>` | Global or one logical session |
| `KEY` | `@k/<key>` | One or more lowercase kebab-case segments separated by `/` |
| `PAYLOAD` | Plain one-line text | Literal names, paths, commands, and terms that support regex recall |

Tokens are separated by one ASCII space. The ASCII space after `@k/<key>` is the key boundary; represent it as `\x20` in recall regexes if a formatter might trim a trailing space. Session ids are exactly eight lowercase alphanumeric characters. Take the current token from the `SESSION SCOPE: @s/<id>` line at the selected primary's startup surface, used verbatim.

Choose the first matching type:

1. Opening a file is the value: `P`.
2. A changeable current value: `S`.
3. Something that happened: `E`.
4. A durable proposition expected to remain true: `F`.

Use these concrete forms:

```text
F @e/<entity> @g @k/<topic> <durable proposition>
S @e/<entity> <scope> @k/<field> <current value; optional evidence>
E @e/<entity> @s/<session-id> @k/<event-kind> <occurrence and outcome>
P @e/<entity> <scope> @k/<document-kind> /absolute/path | <why this file matters>
```

Split mixed atomic claims into separate notes. Put a rich body in a document and emit one `P` instead of compressing it into note prose.

One filled example per type:

```text
F @e/agent-setup @g @k/optmem-recall Recall is case-insensitive regex only; use stable @e/, @s/, and @k/ tokens, not paraphrase.
S @e/project-a @g @k/next-phase Phase 14 is next; verified against <notes-tree>/life/projects/project-a, 2026-07-27.
E @e/agent-setup @s/e1427637 @k/session-end Finished the canonical note grammar; next: migrate writer skills.
P @e/operator @s/e1427637 @k/diary <notes-tree>/lore/journal/diary/2026-07-27-memory-without-a-second-store.md | Reflective record of choosing one append-only memory.
```

Set `<notes-tree>` to an absolute local path. Create the file a `P` note names before appending the note.

Write the note straight to the CLI; no pre-flight measurement is needed:

```bash
python3 <optmem-root>/memo note "$note"
```

`check()` refuses an empty, multi-line, or overlong line before anything is written; an overlong refusal reports the measured byte count against the limit, so a failed append is self-diagnosing and leaves the store untouched.

## Proposal Inbox

`<optmem-state>/proposals` is the plain-text queue for unjudged candidates from detached
delegated runs. Native child agents normally return candidates inline to their primary, skipping
a second queue. The inbox is created on the first accepted append and remains append-only
between drain rotations. Each physical line has this exact format:

```text
YYYY-MM-DD<TAB>SOURCE<TAB>TYPE ENTITY SCOPE KEY PAYLOAD
```

`<TAB>` means one literal U+0009 tab character. `YYYY-MM-DD` is the writer's local ISO date.
`SOURCE` matches `[a-z0-9][a-z0-9._/-]*`, has non-empty slash-separated components, and names the
originating surface, such as `codex/standalone`, `codex/subagent`, or `claude/delegate`. Everything after the second tab is
one candidate in the Note Grammar above; it contains no tab or newline and remains at most 280
UTF-8 bytes.

A proposal whose key field begins `@k/core/` is `REJECT`ed on sight, regardless of content. The
namespace is injected into every session; only the operator or a user-facing primary acting on his
direction writes it. Malformed or overlong candidates must also be `REJECT`ed.

Primary Claude, primary Codex, and user-facing primary DeepSeek append accepted notes and may settle
memory; delegated agents write proposals only for later primary judgment, preserving the compression
and reconciliation boundary.
OptMem's append lock gives concurrent primaries unique ids; it does not resolve semantic conflicts.
Before acting on mutable `S` state, recall the exact entity, scope, and key and take the greatest id.

Writers read this section, build the canonical candidate first, and call:

```bash
<user-bin>/optmem-proposals append codex/standalone "$note"
```

The helper validates the source, grammar, and byte limit, then appends the dated envelope while
holding `<optmem-state>/proposals.lock` with `flock`. A failed append leaves the queue
unchanged; retain the candidate in the final `PROPOSED-NOTES:` block when the helper fails.

Draining belongs to the user-facing primary that accepts the detached run's result. Claude's
executable sequence lives in `commands/pickup.md` and `commands/end.md`; Codex-native and
DeepSeek-native delegates normally return candidates inline for immediate primary judgment. Any inbox
drainer must claim, inspect, judge, append, and archive under the same invariant and exact-recall
checks.

A claim is an immutable snapshot. Every claimed physical line gets exactly one
`KEEP<TAB>reason`, `REWRITE<TAB>reason`, or `REJECT<TAB>reason` decision in matching order; the
reason contains no tab or newline. A `KEEP` or `REWRITE` note is appended and verified by exact
recall before the archive call, because archiving discards the snapshot the retry would need. The
helper then writes the combined audit record under `<optmem-state>/proposal-archive/`
and removes the claimed snapshot.

An unarchived claim under `<optmem-state>/proposal-claims/` is a recovery state, not a
fault: judgment or a keeper write didn't complete; nothing was lost, and a later primary re-judges
the claim using exact recall before retrying. `optmem-proposals pending` lists them.

## Live State and Corrections

An `S` identity is `(entity, scope, key)`. Recall its exact prefix, parse the numeric `#N` that `memo` prepends, and select the record with the greatest `N`. That record alone is live state for the identity; rendered date, output position, prose confidence, and file modification time do not decide it.

Append a newer `S` under the same identity to correct or advance a current value. OptMem records are not edited or deleted. Different entities, scopes, or keys are different identities.

Durable `F` records and historical `E` records accumulate. Surface contradictory durable propositions instead of silently choosing one. For conflicting `P` records with the same `(entity, scope, key)`, the greatest numeric memo id is the current pointer.

## Regex Recall and Coverage

`memo recall` performs case-insensitive Python regex search over rendered lines:

```text
#N YYYY-MM-DD TYPE ENTITY SCOPE KEY PAYLOAD
```

There is deliberately no semantic search. Anchor structural tokens so a mention inside a payload cannot masquerade as the record's entity:

```bash
python3 <optmem-root>/memo recall \
  '^#[0-9]+ [0-9]{4}-[0-9]{2}-[0-9]{2} S @e/project-a @g @k/next-phase\x20'
```

Read the final status line before trusting records:

- `No match.`, `1 match.`, and `N matches.` prove complete coverage.
- `Newest N of M matches. Narrow the regex.` is a coverage failure — the records shown are only the newest slice. Discard it for record-reading purposes, narrow the regex into complete non-overlapping partitions, and merge only complete slices.

The shipped CLI's `PART_CHARS` default is 20,000 — the basis for the recall rendering cap. Narrow in this order when applicable: type, exact entity, scope, key or key prefix, then date. If the task asks only for total count or whether any match exists, the `M` in a truncated status line answers that limited question exactly; it doesn't make the returned records complete.

## Cross-Entity Discovery

The store has no entity registry; a broad whole-store recall can truncate. Build a sweep as a partition:

1. Enumerate direct entity directories under `<notes-tree>/life/areas/` and `<notes-tree>/life/projects/`; add grammar-reserved `operator`.
2. When store-only state slugs matter, recall `S` with first-letter partitions `[a-f]`, `[g-p]`, `[q-z]`; require a complete status line each, extract entity slugs, merge with the directory list. Split any truncating range further.
3. Recall each entity and type separately. Narrow by scope, key prefix, and date until every record-bearing slice proves completeness.

The current `/tidy` sweep uses the complete first-letter `S` partitions. It cannot discover an entity with only `F` or `P` notes and no entity directory; report that boundary rather than presenting the sweep as exhaustive over such store-only slugs.

## Documents and Pointer Notes

The `<notes-tree>/lore/` vault holds knowledge documents; `<notes-tree>/life/{projects,areas}/` keep project and area state. Direct project and area directory names supply canonical entity slugs, matching the vault's `entities/` hubs. For rich content, OptMem indexes; the filesystem holds the content.

Write the document first. Then append:

```text
P @e/<entity> <scope> @k/<document-kind> /absolute/path/to/file | <one-line recall reason>
```

Substitute an absolute local path for `<notes-tree>`; the resulting pointer must begin with `/`. Use a non-empty reason after the first literal ` | `, `@s/<id>` for a session document, and `@g` for a canonical document. A document concerning several entities gets one pointer per entity. When a current document moves, append a newer `P` with the same identity.

Diary entries live in `<notes-tree>/lore/journal/diary/`; their main pointer identity:

```text
P @e/operator @s/<session-id> @k/diary <notes-tree>/lore/journal/diary/<filename>.md | <what the entry holds>
```

Agenda and epistle variants use distinct keys, as defined by the diary skill.

## Writer Contracts

Each command and skill that writes owns its own note contract; read that file for what it appends.
This doc owns the grammar, coverage rules, and pointer rules every writer obeys.

One invariant crosses all of them: no writer creates or renames a daily file. Daily notes are
frozen history; a session's record of itself is an `E` note.

## Telemetry

OptMem reports on itself through four minimal event kinds, added 2026-07-30 and appended to the shared sink `<agent-config>/telemetry/events.jsonl`:

| Kind | Producer | Payload |
|---|---|---|
| `optmem_wake` | `hooks/optmem-wake.sh` (SessionStart, EXIT trap) | `status`, `reason`, `ms`, `wake_ms`, `unsettled`, `chars` |
| `optmem_append` | `memo` note and nap paths | `op`, `id` or `block`, `bytes`, and the four grammar tokens on a grammar match |
| `optmem_recall` | `memo recall` | `op`, `matches`, `returned`, `truncated`, `ms`, `query` (≤64 chars) |
| `optmem_drain` | `emit_drain_telemetry()` in `<user-bin>/optmem-proposals`, fired on `archive` | `op`, `claimed`, `keep`, `rewrite`, `reject`; one row per completed drain — corroborate an empty stream against the proposals archive (fail-open, see below) |

Emission is strictly fail-open and post-hoc. A row is written after the operation succeeds; every failure inside the emitter is swallowed, so command output, exit codes, and timing stay untouched. The `memo`-side emitter opens the sink and never creates it, so a machine without the telemetry layer stays untouched; it also takes the file lock without waiting, so no memory command can block on telemetry.

Memory CONTENT never enters a payload. Rows carry grammar tokens, memo ids, byte counts, and a ≤64-character prefix of the recall pattern; a line that doesn't match the note grammar contributes no tokens — its head is prose, and prose is memory content. Set `OPTMEM_TELEMETRY=0` to silence the `memo`-side emission for test suites and throughput measurement.

Wake refusals are now observable. A wake that refuses because 9+ blocks are unsettled writes `status: refused`, `reason: nap-required`, and the backlog size, so the nap debt shows up as data instead of a fail-closed silence. Stream vocabulary and the reader's caveats live in `<agent-config>/telemetry/README.md`.

## Frozen History

The following pre-cutover artifacts may remain on disk; they are documents from the retired system:

| Artifact | Current status |
|---|---|
| `summary.md` | Frozen history; never read it as authoritative entity state. |
| `items.json` | Frozen history; it is not the structured-detail store. |
| Daily note JSON files and their schema | Frozen archive; `/end` emits `E` notes and creates no daily note file. |
| `last_verified` | Frozen legacy field; `/end` doesn't maintain it — current evidence belongs in the relevant `S` payload when a writer's contract calls for it. |
| `## Recent Sessions` inside `summary.md` | Frozen history; entity events come from `E` recalls. |
| The daily-file session-naming rule | Retired; sessions do not rename archived JSON files. |

Read current state from OptMem; read a legacy file only when the task explicitly asks about historical document content.

## People Pattern

Store relationship documents for recurring clients, collaborators, and stakeholders under `<notes-tree>/lore/notes/people/`. These are vault documents, not entity-state records. Add `P` notes when a person document needs an OptMem index entry.

## Cross-linking

Inside the vault, use relative paths so related files move together, for example `../entities/project-a.md` from a file in `notes/`. Links that cross roots (a vault note referencing `<notes-tree>/life/` state, or the reverse) use absolute paths, as does every `P` note, per the pointer grammar.

## Progressive Disclosure in Human-Browsed Markdown

Long human-browsed markdown (life/ knowledge base, specs, reference docs) uses `<details>`/`<summary>`; keep `## Heading` above the block and make `<summary>` match the heading. Model-facing instruction files (SKILL.md bodies, `commands/*.md`, agent prompts) skip `<details>`: bodies load whole, so collapsing saves no tokens. Do not collapse short sections, Quick Nav tables, intros, daily notes, or short configs.
