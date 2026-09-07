---
name: outreach-atlas
description: "Build the data layer of cold outreach: a ruled brief, a curated atlas.md where every person earns their line with a why-them clause, emails quoted verbatim from fetched pages, wave slices and send ledgers for /cold-email. Auto-trigger when creating, auditing, or slicing an outreach map, prospect list, or who's-who of a field, or when hunting and verifying email addresses; even with no mailing planned."
---

# Outreach Atlas

## When to use

Also covers: contact atlases, campaign people stores, landscape maps, key-people lists of a market or scene. Emails are hunted in escalating passes; replies feed a learnings file.

**Goal**: a curated markdown atlas of one field's people — who they are, why they matter, how to reach them — with wave slices for `/cold-email` and a `learnings.md` that answers the brief's questions from replies.
**Success means**: every atlas entry carries a why-them clause; on a mail-bound campaign every entry also carries a hunt state — a ✓/? address or an explicit no-email note naming the passes tried; every address is quoted verbatim from a fetched page with its source URL; the counts line separates mapped from reachable✓; no do-not-mail name appears in any wave.
**Stop when**: the requested stage is done. Drafting and sending belong to `/cold-email` plus the operator's per-batch approval.

## The one structural rule

Fleets write `raw/`; judgment writes the atlas. No script, fleet job, or regex ever edits a curated file. Earlier iterations's merge bugs were automated surgery on prose; later iterations's overhead was the JSON machinery built to make that surgery safe. Remove the automated writes and neither is needed: the primary reads fleet output critically and hand-picks what earns a line. Curation is the merge.

## Layout

```
<vault-root>/research/YYYY-MM-DD-<slug>/
├── BRIEF.md      true goal (never stated in mails), learning goal, lanes,
│                 explicit search terms, do-not-mail list, send gates
├── atlas.md      THE map: counts line, then curated entries by lane
├── waves/        wave-N.md — the cut plus its send ledger
├── learnings.md  what replies taught, cited to entries
└── raw/          fleet briefs + outputs (raw/fleet-<name>/) and source dumps;
                  append-only, quote-don't-edit
```

Create the vault entity hub and operator-supplied memory pointers per the vault conventions; log fleet completions and count changes as operator-supplied memory events.

## Entry format

```markdown
- **Jordan Lee** — Head of Model Risk, Example Mutual Owns sign-off on simulation-backed
  underwriting. jordan.lee@example.org ✓the recorded period ([src](https://example.org/team))
  · [SOA talk on agent models](https://…)
```

- The why-them clause is the admission test: if you cannot write one, the name stays in `raw/`.
- Select by burden, not seniority: who owns the problem the campaign is about, not who ranks highest (a prior comparison the recorded period; burden selection also reached one selection basis outperformed another).
- `✓date (src)` means you fetched the page and it shows this address *for this person* — attribution included, because a page can show the string while contradicting the employer (a prior comparison flagged several such). `?` means found but unverified. These are the only two address marks; earlier runs' ad-hoc status markers silently hid many reachable people.
- A person hunted dry keeps their line, stamped `no-email (A+B, the recorded period)`: an explicit null naming the passes tried, so the next round escalates instead of re-treading. Distinct from no stamp at all, which means not yet hunted.
- Counts line, first line of atlas.md, updated at each curation pass: `mapped N · reachable✓ M · do-not-mail K`. reachable✓ counts unique people with a ✓ address who are not on do-not-mail; it is the only number quoted outward — earlier runs' a headline count overstated the reachable set, and the correction cost more trust than the honest number would have.

## Flow

**Brief** — fill BRIEF.md and get the operator's ruling before any fleet spend; a fleet against an unruled brief maps the wrong field precisely. State the actual search queries: an early discovery round missed an entire lane because its queries said "synthetic respondents" and never "strategic simulation". Prior-contact names go on the do-not-mail list now, before mapping; a do-not-mail entry carries name, known aliases and addresses, org, and date + reason, so a person cannot re-enter under a variant spelling. A map-only brief (nobody gets mailed) skips waves and gates and keeps everything else.

**Map** — discovery fleet by lane (`references/fleet-recipes.md`), then curate `raw/` into atlas.md. Grep the atlas for the name before adding it; dedup is a curator's grep, not a normalizer.

**Reach** — the atlas earns its keep here: a person you cannot reach is a name, not a contact, so the hunt gets the same rigor as the map. Hunt in enumerated batches, escalating — pass A the person's own pages, pass B commit patches, CFP listings, thesis PDFs, CVs, Wayback; a large share of misses falls to escalation (measured bases in `references/fleet-recipes.md`). Verbatim from a fetched page only; aggregators (RocketReach, ContactOut, Hunter, Apollo, Lusha) stay banned as a source. **Pattern-guessing is no longer banned outright** — the operator may allow it for corporate lanes when the brief says so — but a constructed address is a second class of thing, and the two never mix in one wave (see *Two classes of address* below). Batch hunts by publishing surface — people found via the same kind of page (faculty directory, conference roster, GitHub org) hunt together; this raised a prior comparison's hit rate from a lower hit rate to a higher hit rate. The hunt is complete when every atlas entry carries ✓, ?, or its no-email stamp — a bare entry is unhunted, never "unreachable".

**Cut** — a wave is ~30–50 people (basis: hook throughput, completed hooks from the current run; small waves put replies weeks earlier). Before cutting, enrich the candidates: 1–2 concrete artifacts with URLs per person — the substrate for a falsifiable opener; fleet the fact-finding, never the hook-writing. Spot-recheck the wave's source pages (enumerated luna job); a page that no longer shows the address downgrades ✓ to ?. Check every name against do-not-mail. the operator approves each batch before anything sends.

**Learn** — each reply lands in the wave ledger (date + one-line extract); an opt-out puts the name on do-not-mail instantly, and a do-not-mail person is never mailed again — under any sender identity — without the operator's explicit ruling. Synthesize into learnings.md: answer the brief's questions, cite entries, re-aim the next wave's cut and hooks. Judgment work; runs in the primary, never in a fleet.

## Two kinds of surface, hunted separately

The most transferable measurement of the recorded period comparative campaign: **a page that
names people well almost never prints their address, and a page that prints addresses rarely
explains why the person matters.** Measured across matched fleets in one campaign:

| Surface kind | Examples | People | With address |
|---|---|---:|---:|
| **Engagement pages** | vendor case studies, exercise write-ups, award citations, programme pages | many | **few** |
| **Address-rich pages** | papers with a corporate co-author, signed regulatory comment letters, committee rosters, conference proceedings, proxy and court filings, annual reports with a named contact | many | **most** |

So run them as **two aimed rounds, not one**: engagement pages to find who matters and why,
address-rich pages to make them reachable. A single round aimed at "find people with addresses"
gets whichever the surface happens to yield and silently under-delivers the other half.

The corollary is a warning about reading reply rates: **reachability is a publishing custom, not
buyer interest.** In that campaign insurance reached very high reachability because its industry bodies
and working parties publish addresses by convention, while other lanes sat low for people
who wanted the product just as much. A lane comparison that does not control for this measures
disclosure practice and calls it demand.

## Two classes of address

- **Evidenced** — quoted from a page you fetched, for this person. The only class that goes to a
  colleague writing personally, where one bounce costs a real slot.
- **Constructed** — an evidenced org format applied to a name. Acceptable for a bulk wave, never
  for a hand-written one, and never released as a block.

The lever: one evidenced format makes every colleague at that organisation reachable. The risk is
the same lever pointed the wrong way — a wrong pattern bounces a dozen addresses at one domain on
one day, which is how a sending domain is burned. Discipline that follows:

- **Never accept a format without the real address that evidenced it.** One campaign built 16
  addresses at a domain from a format claim with **zero** observed addresses behind it.
- **Count what rests on each format.** 187 constructed addresses in that campaign rested on a
  single observation; that is a bet, and it should be a visible one. `mail-domains.md` (below)
  prints that count per domain, so the bet is visible without being tallied by hand.
- **Seed-test before release**: one address per domain, watch for the bounce, then release.
  SMTP probes can reduce uncertainty first; they do not replace attribution or sending approval.

## Checking an address

The laptop has successfully made SMTP probes; the VPS has blocked outbound port 25. Network
reachability can change. Use `<vault-root>/tools/crm/probe.py` for an authorized, bounded set:

    python3 <vault-root>/tools/crm/probe.py --domain example.org
    python3 <vault-root>/tools/crm/probe.py --unprobed --limit 300
    python3 <vault-root>/tools/crm/probe.py addresses.txt

The verifier uses RCPT TO without DATA: it sends no message body. Servers can still log, limit
or block probes; do not describe them as reputation-free. The wrapper saves a raw trail under
`<vault-root>/research/address-probes/`, then updates the registers, cards and suppression output.
Check every step's completion. If reconciliation fails, keep the trail and rerun the chain;
a saved result alone does not mean the CRM was updated.

| result | evidence | action |
|---|---|---|
| `VALID` | the server accepted this recipient after rejecting a random nonexistent recipient | record SMTP acceptance separately; it does not establish the person's identity, page attribution or eventual delivery |
| `INVALID` | explicit evidence that the mailbox does not exist | register the address and clear its current email field, preserving its owner and history |
| `CATCHALL` | the server accepted a random recipient | mailbox existence is unconfirmed; keep constructed addresses labelled as guesses |
| `TEMPFAIL` | temporary or policy rejection | retain the reason; retry only when appropriate |
| `NOMX` / `ERROR` | DNS, connection or transaction failure, or an inconclusive response | no mailbox verdict; investigate or retry |

A 550 alone does not prove a dead mailbox: authentication, TLS, spam policy, bounce verification
and command-order failures can reject a probe or message without saying whether the address
exists. Keep delivery restrictions suppressed until reviewed; do not automatically restore a
previously removed address when correcting its classification. Historical `VALID` results that
lack a recorded negative control are weaker evidence than a controlled probe.

A ✓ in the atlas still means **quoted from a fetched page for this person**. SMTP acceptance
never upgrades a constructed address to ✓. At catch-all domains, prioritize source pages;
current catch-all counts belong in the generated register, not this skill.

## Address and domain registers

Under `<vault-root>/agent-registry/`:

- **`dead-addresses.md`** records mailbox failures and their owners. CRM address intake checks it
  for both new and existing cards. A missing or malformed register must stop the write.
- **`mail-domains.md`** summarizes candidate name patterns and their evidence. A matching CRM
  address may itself be a guess: agreement measures exposure, not independent corroboration.
  Use only explicitly sourced observations or controlled SMTP acceptance as supporting evidence,
  and preserve the difference between the two. Check the evidence's role and department before
  extending it to another group at that employer; a staff mailbox does not establish a fellow's
  mailbox. The table does not establish department-specific distribution on its own.

The the recorded period MATS check found 82 nonexistent addresses after a staff `first@` pattern had been
applied to fellows. Many guesses agreeing with one another did not validate the pattern.

Use the guarded CRM tooling for address changes. A runtime without access to it must record a
pending correction with the person, address and evidence for the primary to apply, and say it
is pending. A prompt instruction is not an executable connection to the laptop.

## Who never enters a list

Beyond the do-not-mail list, four classes are excluded by construction, because each one wasted a
slot in the recorded period campaign before the filter existed:

- **Public sector** — government, agencies, regulators, hospitals, transit and other public
  authorities, universities and military schools, central banks, supranational bodies. In a
  counterparty lane this matters twice: **the authority is the live player being simulated, not
  the buyer** — a competition regulator in an antitrust list is the inverse of a lead.
- **Sellers and advisors** — consultancies and law firms sell the service; they do not buy it.
- **Trade associations and employer federations** — they lobby for buyers, they are not buyers.
- **Broken organisation fields** — a bare corporate-form word (`Syndicate`, `Ltd`, `Markets`) or a
  country name is a parse failure, not an employer, and a person whose employer is unknown cannot
  be judged.

Match exclusions on the **employer only**. An early version also read the role text and flagged a
commercial underwriter for *sitting on* the Joint War Committee — the committee is not his
employer. Over-exclusion is cheap when the pool exceeds the quota; a wrong inclusion is not.

For personal outreach, cap **two people per employer**. Nine people at one organisation is a
mailing list, not a personal approach.

## Selection integrity

Two failure modes, both caught by the operator rather than by the pipeline, both worth a standing check:

**The constraint artifact.** A list of exactly 100 that came from a pool of exactly 101 is not a
selection; it is everything that survived a constraint, presented as a choice. It looked curated
and was not: half its entries scored "thin", four lanes had one or two people, and a *Former Vice
President* and a *Finance Manager* were in it. **State the eligible pool size next to the picked
count** — `202 eligible → 100 picked` is a selection, `101 → 100` is a confession — and say which
one it is before anyone acts on the list.

**Title inference.** When jobs are aimed at rosters and "named heads of X" — pages that list
titles but describe nobody doing anything — agents infer relevance from the job title, because
that is the only signal on the page. That is how a Senior Paralegal and a CMO entered an
activist-defence lane. Rounds aimed this way produced 1283 people of whom **260 survived audit**.
The fix is in the brief, not the model: aim at pages that describe *something that happened*, and
state the admission test as a gate with a worked accept and a worked reject.

Audit the result rather than trusting it. Score on evidence — has a source, names a real
engagement, holds a deciding role — and penalise the weak-role, stale (`former`, `retired`) and
missing-org flags. Sample the weakest dozen by hand before handing the list to anyone.

## Dedup by address, not by name

Address is the identity that actually collides in a send queue, so it is the merge key; name plus
organisation is the fallback for people not yet reachable. One registry across every corpus in the
campaign, read by each new round as an exclusion list, so a round spends its budget on people we
do not already hold. That caught 271 duplicates in one campaign, including a slice that had split
its own output into three files.

## Curation

Curated beats complete. The atlas is the shortlist; the long tail lives in `raw/`, quotable and greppable. A lane past ~100 entries (rule of thumb, not a measurement) means the admission test is too loose — tighten the burden criterion, split the lane into its own file, or park the tail. Basis for the posture: a prior comparison mapped 795 people; among its 291 mailable, 164 owned the problem — the atlas is the owners, not the map.

## Fleet work

Read `references/fleet-recipes.md` before designing any fleet: enumerate on luna, execute on luna; jobs return markdown lists under a `===RESULTS===` marker; the partial-output rule is mandatory in every brief. Nuanced IN/OUT judgment does not fleet on the bulk tier — an earlier round overturned many bulk verdicts; judge on sol or in the primary.

## Hand-off to /cold-email

The wave file is the interface: per person one line — name, address with ✓date, org (so the same-lab check sees shared affiliations), lane, hook seed, artifacts — plus the send ledger table (`| name | sent | replied | note |`). Replies come back into that ledger. The campaign's true goal and any company plan live in BRIEF.md and stay out of mails, the wave files handed to `/cold-email`, and public artifacts.
