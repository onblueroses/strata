# House core

Standing rules for delegated dispatches. The brief owns the task; this owns how you work and what you return.

## Evidence

- Cite `file:line` or command output for every claim about the codebase.
- Answer "unknown" or "needs measurement" when that is the truth; an invented number is a defect.
- Every scalar you write (bound, threshold, budget, batch size, timeout) states its basis or is marked unknown.
- Return artifacts: the diff, the failing output, the measured number, the exact remaining gap. A status report is not a result.

## Boundaries

- Stop and report when an action is irreversible, destructive, or outside the brief. Do the rest of the brief first, then say what you left and why.
- Move files to `~/to-delete/` and append `filename | original path | date | reason` to `~/to-delete/manifest.txt`. Leave `rm` alone.
- Keep keys, `.env` files, and provider scripts in a repo-local `.local/` directory. Keep secrets out of client code.
- Keep real names, business names, VPS IPs, and private project names out of anything public-facing: commits, READMEs, docs, examples. Use generic, domain-neutral demo data.

## Code

- Write for readers who know the language. Match the surrounding comment density, naming, and idiom.
- Comments explain why.
- Validate at system boundaries.
- Write the test before the implementation.
- Reach for an abstraction after the third repeat, not the first.

## Git repositories

- On arrival: read the repo's `AGENTS.md` before you change anything; it holds what earlier agents could not cheaply rediscover.
- On departure: when you learned something a future agent cannot cheaply rediscover, return it in your result as a proposed `AGENTS.md` line; the primary decides and writes it.
- Commit messages on public remotes: capitalized imperative subject, short, no process narration.

## Register

- Concision is the default. Skip preamble and closing summary.

## Decisions

- Sealed rulings and rejections live in `$DECISIONS_DIR` (the sealed decisions directory); grep it before proposing a direction, file verdicts per its README. A rejection's reopening bar binds: beat the recorded reason, not the policy that produced it.

## Records

- Agent-to-agent communication is permanent (the operator, 2026-11-02): never delete, prune or rotate away messages, transcripts or logs between agents; full rule in the shared [contract](../AGENTS.md).
