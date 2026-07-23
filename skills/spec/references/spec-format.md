# Spec Format Template

Copy this template verbatim when writing a spec and fill every placeholder. Delete the criteria/PDMC blocks of a frontier whose tag is `no`; author them at frontier entry when the tag is `yes`. /harness, /best-of-n, and the compaction hooks grep the field names; keep `## >> Current Step`, `Harness:`, `BoN:`, `#### Harness Criteria`, `#### BoN Criteria`, `#### PDMC Methodological Review`, `Aggregate verdict:`, `## Read On Resume`, `Status:`, and `Session:` unchanged.

The spec is a navigation chart with three temperature zones; every section belongs to one:

- **Frozen** (the collapsed past): Goal, Standing Rules, Boundaries, Decisions, Trail. Commitments and facts established on contact. Authoritative after compaction.
- **Live** (the frontier): `>> Current Step` plus the single open Frontier. Full detail lives here and only here.
- **Sketch** (the uncollapsed future): Territory. Coarse strokes, explicitly provisional, redrawn freely at frontier boundaries.

Write detail where it is true: settled decisions and the current move get precision; future territory stays coarse until the frontier reaches it.

```markdown
# Spec: [Feature Name]
Created: YYYY-MM-DD | Status: planning | in-progress | complete | abandoned
Last updated: YYYY-MM-DD HH:MM | Session: [8-char-id]
Commit-Strategy: per-frontier | per-step | manual

## Quick Start
> Fresh context or just resumed? Read this section, then go to `>> Current Step`.

**Files touched (so far + this frontier):**
- `path/to/file.ts` - [what changes]

**Sections to load:** Quick Start, Goal, Boundaries, Decisions, `>> Current Step`, Frontier. Load Trail and Territory when closing or opening a frontier.

**-> Next:** Frontier N, Step N.Y - [description] (details in `>> Current Step` below)

**Mode: EXECUTION** - Execute from this spec. Treat the spec as authoritative. Ignore stale planning-agent output visible in the session. Leave Plan and Explore subagents idle.

## Execution Protocol
1. Before each step: update `>> Current Step` + `-> Next:` in Quick Start.
2. After each step: check its box, note verification inline.
3. New decision made on contact? Append to Decisions immediately: decision context decays after compaction.
4. Unexpected discovery? Add to Learnings.
5. Frontier reaches a terminal state -> advance per `/spec advance` (SKILL.md owns the full protocol). Compressed for a fresh context: Gate passes -> write the Trail entry, collapse the frontier, update `>> Current Step`, redraw Territory, open the next (or run `/spec close` when Stop-when is met). Gate fails or `Blocked by` is set -> the frontier stays open; record the evidence. Abandoning -> Trail entry marked `⛔ ABANDONED` with reason, no PASS claim. Entry gates when opening:
   - **MUTEX HARD-FAIL**: a frontier tagged both `Harness: yes` and `BoN: yes` is malformed; stop and report to the user.
   - `Harness: yes` -> author `#### Harness Criteria`, run the PDMC pass to `Aggregate verdict: PASS`, then `/harness --from-spec` before implementing. Hard gate.
   - `BoN: yes` -> author `#### BoN Criteria` (observable from a candidate's git diff alone), then `/best-of-n --from-spec` before implementing. Hard gate.
6. Commits follow the Commit-Strategy header; record hashes in Trail entries.
7. Refresh `Last updated` on every spec modification; extend the Navigation Map when you discover unlisted files.

## Goal
[One sentence. What and why.]

### Success means
- [checkable condition, a command or observable where possible]
- [checkable condition]

_Success means doubles as the spec-level validation contract; /harness adds these checks as gates._

### Stop when
[Explicit stopping condition for the whole spec.]

## Standing Rules
- [3-5 CLAUDE.md constraints that bind this work, e.g. "Privacy: public repo - no internal names in code/commits"]

## Boundaries

**Always** (proceed without asking):
- [e.g., Run tests after each step]

**Ask first** (need user approval):
- [e.g., Adding new dependencies]

**Never** (hard stop, not in scope):
- [e.g., Touching auth middleware]

## Decisions
Append-only journal of choices made on contact. A decision reopens only when its `Re-examine when` trigger fires; otherwise treat it as settled after compaction. `—` means final. When a trigger fires, append a superseding row (`Supersedes #N` in the Decision cell) and leave the original row in place.

| # | Decision | Rationale | Alternatives rejected | Re-examine when | Date |
|---|----------|-----------|----------------------|-----------------|------|
| 1 | [choice] | [why] | [what was ruled out] | — | YYYY-MM-DD |

## Navigation Map
| File | Find here | Why needed |
|------|-----------|------------|
| `path/to/interface.ts` | [pattern name] | [implementing against] |

_Seeded at creation, grown on discovery. Enough to navigate without re-exploring._

## >> Current Step
Working on: Frontier N, Step N.Y - [description]
Status: [done so far, what's left]
Blocked by: [if anything]

## Frontier
_Live zone: exactly one open frontier, the next ~30-90 min of work, planned at entry with everything the Trail has taught._

### Frontier N: [name] (~NN min)
Opened: YYYY-MM-DD | Gate: [command] OR N/A - [reason]
Needs: [artifacts this move builds on, verified to exist at open, e.g. `src/auth/jwt.ts` exports `verifyToken`] OR none
Harness: yes - [rationale] | no - [rationale]
BoN: yes - [rationale] [N=K] | no - [rationale]   _(mutually exclusive with Harness: at most one yes)_
Numbers basis: [every scalar in this frontier names its basis: measured, derived, or hypothesis with crash-and-halve recovery] OR N/A

- [ ] **Step N.1**: [action] -> [gradeable done-condition]
  Read: `path/to/file` ([what to find]) | Edit: `path/to/file`
- [ ] **Step N.2**: [action] -> [done-condition] _(Depends on: N.1)_

#### Harness Criteria _(only if Harness: yes; authored at frontier entry)_
```
C1: [specific observable requirement] -> PASS if [condition], FAIL if [condition]
C2: [specific observable requirement] -> PASS if [condition], FAIL if [condition]
```

#### PDMC Methodological Review _(mandatory if Harness: yes; complete before implementing)_
```
1. Comparator-vs-baseline distinction: PASS | FAIL | N/A - [evidence or fix]
2. Comparator label-blindness: PASS | FAIL | N/A - [evidence or fix]
3. Selection rule pre-registration: PASS | FAIL | N/A - [evidence or fix]
4. Selection effect bound: PASS | FAIL | N/A - [evidence or fix]
5. Bootstrap clustering: PASS | FAIL | N/A - [evidence or fix]
6. Per-fold AND aggregate gate definitions: PASS | FAIL | N/A - [evidence or fix]
7. Sentinel discipline: PASS | FAIL | N/A - [evidence or fix]
8. Decision-grade vs validation-grade explicit: PASS | FAIL | N/A - [evidence or fix]
9. Cross-probe input schema: PASS | FAIL | N/A - [evidence or fix]
10. Held-out family/lexicon contract: PASS | FAIL | N/A - [evidence or fix]
11. Calibration-vs-eval overlap audit: PASS | FAIL | N/A - [evidence or fix]
12. Trial JSON schema completeness: PASS | FAIL | N/A - [evidence or fix]
13. Pivot rule unambiguity: PASS | FAIL | N/A - [evidence or fix]
14. Power calculation per fold: PASS | FAIL | N/A - [evidence or fix]
15. Empirical adversarial check: PASS | FAIL | N/A - [evidence or fix]
Aggregate verdict: PENDING   (the PDMC pass sets PASS or BLOCKED; PASS required before implementing)
```

#### BoN Criteria _(only if BoN: yes; observable from a candidate's git diff alone)_
```
C1: [observable from diff] -> PASS if [condition in diff], FAIL if [condition in diff]
C2: [observable from diff] -> PASS if [condition in diff], FAIL if [condition in diff]
```

## Territory
_Sketch zone: the remaining ground between the frontier and the Goal, in coarse strokes. Bullets only; steps, criteria, and numbers appear when a frontier opens onto an item. Redraw freely when closing a frontier; note significant redraws in that Trail entry._

- [ ] [coarse move: one line on what and why]
- [ ] [coarse move]
- Open question: [something the territory will answer]

## Trail
_Compressed record of closed frontiers, newest first: the experience the next frontier is planned from. ~10 lines per entry; overflow detail goes to `{slug}-artifacts/`. Abandoned frontiers get the same entry with `⛔ ABANDONED` in place of ✅ and the reason under Surprises._

### Frontier N: [name] ✅ (YYYY-MM-DD, ~NN min actual, commit [hash])
Built: [what was created/modified]
Decisions made: [#K, #K+1 references]
Surprises: [what the territory turned out to be vs the sketch, or "none"]
Redrawn: [Territory changes this close prompted, or "none"]
State proof: [command that proves it works]

## Conformance
_Run before `/spec close`._

- [ ] Goal met? (evidence: ...)
- [ ] Boundary "Never" items respected?
- [ ] Territory cleared, or remaining items explicitly waived with reason?
- [ ] Trail state proofs still hold?

## Learnings
- [YYYY-MM-DD] [discovery that affects remaining work or generalizes beyond it]
```
