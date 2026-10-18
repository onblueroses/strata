# Hook and gate maintenance

Detailed implementation notes and failure history moved verbatim from the repository
AGENTS.md on 2026-09-07; dated measurements describe those runs, not fresh verification.
Paths below are relative to the claude/ directory unless explicitly absolute.

Read the relevant sections before changing privacy gates, their scanner, hook dispatch,
or their test harnesses. Global policy remains in [AGENTS.md](../../AGENTS.md).

## Hooks and gates

- `hooks/run-gates.sh` is sourced into every PreToolUse gate under `set -u` and must never abort:
  PreToolUse reads any status but 0 or 2 as "hook errored" and permits the command, which disarmed
  eleven gates at once on 2026-08-16. Opt out with `_GATE_FAIL_CLOSED=0` before sourcing, never after.
- Every gate prints its block reason to STDERR. PreToolUse relays stderr on exit 2 and parses stdout
  only against the decision schemas, so a reason on stdout is discarded silently.
- The two privacy gates were rewritten on 2026-09-01 (the operator: one job each, judgment over apparatus).
  `hooks/gate-gh-public-actions.sh`, `hooks/gate-pre-push.sh` and `hooks/lib/privacy-scan.py` replace
  a 6,000-line helper chain: the bashlex command parser, its launcher and vendored dependency, the two
  streaming scanners, `gates/lib/shell-segments.sh`, and the pasted shared blocks. All of it is in
  `~/to-delete/`. Nothing in `hooks/` parses shell any more; both gates read the command as TEXT.
- The gates therefore match `gh` and `git` in COMMAND POSITION — start of text, or the far side of a
  shell operator, past env assignments and `sudo|env|nice|time|exec|then|do|else|xargs|timeout N`.
  A match anywhere in the text instead refused every command that merely QUOTED a push or a gh write:
  a grep pattern, a jq fixture, this repo's own diagnostics (a ticket, and again on 2026-09-01 while
  measuring the rewrite). The `CMDPOS` regex is duplicated in both gates on the paste-don't-source
  ruling; if you change one, change the other.
- `gate-gh-public-actions.sh` scans the command text plus every file it names as content:
  `--body-file`, `-F k=@f`, `--input`, `--notes-file`, a `<` redirection (`--body-file - < f`
  reads stdin), gist positionals, and the assets of `release create|upload <tag> <files>` past
  the tag word. A read that FAILS is a refusal, not an empty file: `head` masking its own status
  let a broken reader pass as a clean scan. The resolved `$HOME` is normalised to `~` in the
  COMMAND TEXT only: the home path is a `lit` in the inventory AND the prefix of every local path here,
  so scanning the line raw refused 51 of 1385 real gh commands for naming a file. File CONTENTS are
  scanned raw, so the path still refuses inside a body; an inline body that spells it out passes.
- Relative file references resolve against a `cd <dir>` in the same command, not the reported cwd:
  PreToolUse fires BEFORE the command, so `cd x && gh api -F q=@f` otherwise resolves nothing and
  publishes unscanned. The same rule picks the repo in `gate-pre-push.sh`, where `-C` is read from the
  push invocation only — a diagnostic running `git -C <other> log` beside a quoted push scanned the
  wrong repo entirely.
- `gate-pre-push.sh` resolves a range PER REFSPEC (`<remote>/<dst>..<src>`, else `<src> --not
  --remotes=<remote>`). The old gate used `@{u}..HEAD` whatever remote was named, so `git push origin
  main` in a repo whose upstream is a different remote measured the wrong set and passed 19 real hits.
- The refspec list is EXPANDED first, because the flags decide what is actually sent: a leading `+`
  is stripped, `--all` and an exact `:` mean every local branch, `--mirror` every branch and tag,
  `--tags`/`--follow-tags` add every local tag to the default, and `--dry-run`/`-n` publish nothing
  and exit 0. Each of those shapes was scanned as "whatever HEAD points at" and sent unscanned
  commits (review, 2026-09-01). A source that resolves to an annotated tag also scans
  `git cat-file -p <tag>`: the tag MESSAGE lives in the tag object, which `git log -p` never walks.
- Secrets refuse on ANY target, private included (the old gate exited before the scan whenever
  visibility was `private`, so no private repo was ever scanned for credentials). Identifiers refuse
  unless EVERY target the command writes to is proven private, `private` from gh for a forge repo or
  a destination off the public forges (the VPS over Tailscale, a bare repo on disk); a failed lookup
  is not a claim. `ASIA` temporary AWS key ids are not a secret class: they ride in presigned S3 URLs
  in `~/lore` and grant nothing without the signed request.
- The gh targets are every `--repo X`, `-R X`, `-RX`, `--repo=X` in the line plus the
  `repos/<owner>/<repo>` prefix of a `gh api` endpoint; the cwd repo is the target only for a
  non-api, non-gist verb that names none. A gist and an api call with no `repos/` path are never
  proven private. Taking visibility from one target let an attached `-Rpublic/repo`, an api endpoint,
  a public gist and a private-then-public chain all publish from a private cwd (review, 2026-09-01).
- `gate-pre-push.sh` classifies the CONFIGURED PUSH urls, `git config --get-all remote.<r>.pushurl`
  falling back to `remote.<r>.url`, read UNEXPANDED. It classified the fetch url, so a remote whose
  fetch side is a private box and whose `pushurl` is a public forge published unscanned. A remote
  name that resolves to no url is unknown, and unknown is not private. The privacy test harness
  therefore keeps forge urls on the remotes and redirects real pushes with
  `url.<bare>.pushInsteadOf=<forge url>`; a fixture `pushurl` would be the field under test.
- `PRIVACY_ACK=1` is the documented override, honoured ONLY as a leading env assignment
  (`^[[:space:]]*PRIVACY_ACK=1[[:space:]]`) in both gates. As a substring it fired on prose: a body
  that merely discussed the override, or one containing `--help`, turned a public write into a
  permit. There is no `--help` exit either, for the same reason.
- Bounds are TIME bounds and the suite reads them from source. gh: ONE 1200 ms visibility budget
  shared across the targets a line names (past six it stops asking and scans everything) + 1500 ms
  scan inside the declared 3 s (measured: 4 ms no-gh, 14 ms read, 420..600 ms write). pre-push: 3 s per git
  call and a 12 s scan, each taken as min(its own bound, what is left of ONE 17 s whole-gate
  deadline) inside the declared 20 s (measured: 3 ms non-git, 12 ms `git status`, ~100 ms for
  3 commits, 4.7 s for the 14.6 MB `~/lore` range — the scanner runs at ~3 MB/s).
- The scanner narrows with ripgrep first (2026-09-30): the 195 MB `~/lore` range of 254 commits
  took ~50 s in pure Python, past the 12 s scan bound, so every push of it refused; narrowed it
  takes 2.3 s. Only `--classes secrets` (pushes to proven-private remotes) is narrowed; Python still
  judges every candidate line, so its verdicts and reports are unchanged. `--classes all` keeps the
  full Python pass: inventory `re` entries mean different things to the two engines (`\b` beside a
  combining mark, so NFD `Acmé` evades `\bacme\b`; `\s` on \x1c; `[a&&b]`), found by review.
  The prefilter must stay a SUPERSET of the matchers: ripgrep sees the stream after the same
  `decode("utf-8", "replace")` (invalid bytes become U+FFFD on both sides), runs with
  `--no-config --encoding none --text`, drops only the placeholder lookahead it cannot parse, and
  any line holding one of the four non-ASCII code points Python's IGNORECASE folds to ASCII
  (`İ ı ſ K`; ripgrep misses the first two) is always a candidate. That class is case-sensitive: under `-i` it grew to
  every `s` and `k` and the narrowing vanished. No `rg`, or a pattern it refuses, silently falls
  back to the full Python scan: slower, never wider.
  `gates/tests/test-privacy-scan-prefilter.py [corpus]` compares the two paths finding for finding
  with a blind-prefilter positive control; pass a `git log -p` corpus after changing a pattern.
- `raw/` is exempt for proven-private destinations (the operator, 2026-10-01): scraped pages carry other
  sites' embedded keys by the hundred (123 hits in one `~/lore` push, all Maps keys and lookalikes).
  git drops them itself, with the pathspec `':(exclude,glob)**/raw/**'` on the diff; the messages are
  read in a separate `git log` without a pathspec, which would also drop every commit touching only
  raw/. A first version had the scanner follow `+++ ` headers instead: messages could pose as
  headers, `diff.dstPrefix=raw/` put every path under raw/, and the 39k header lines cost Python
  3 s. Tests: `message-posing-as-raw-diff-refuses`, `exemption-ends-at-the-next-file`,
  `rawdata-is-not-raw`, `repo-diff-prefix-cannot-forge-raw`, `raw-only-commit-message-is-scanned`.
- The OpenAI `sk-` shape needs a hyphen-free stretch of 20 holding a digit (the operator, 2026-10-01):
  `-cz-sk`-`example-brief` was a finding. Its lookahead, like the placeholder one, is dropped
  for ripgrep, so the prefilter only widens.
- A hook `timeout` in settings.json is in SECONDS. Until 2026-09-30 the gates declared 20000,
  3000 and so on as if milliseconds, so a hung hook could stall a session for hours; they now
  read 20, 3, 5, 2 and 10. A killed PreToolUse hook permits, so each gate's own deadline must
  stay under its declared timeout.
- Under a second of that deadline left, the pre-push gate refuses "NOT scanned". Per-call bounds
  alone did not add up: five git calls plus a scan overran at 21.9 s and returned 124, which
  permits. `timeout`, `jq`, `git` and `python3` are preflighted, and 126/127 out of a bounded call
  is a refusal, never a git verdict — a `timeout` that could not run read as "not a repository"
  and passed a dirty push.
- `hooks/lib/privacy-scan.py` holds `SECRET_RE` ported verbatim from the retired `pre-push-scan.py`,
  plus four alternatives recovered from `SECRET_URL_RE` on 2026-09-01: the Slack-webhook,
  Discord-webhook and Sentry-DSN urls (where the url IS the credential), and the `user:pass@host`
  userinfo pattern, this time with the placeholder-password exclusion it needs (password, passwd,
  pass, secret, token, changeme, example, `x{3,}`, `${VAR}`, `<...>`). Without that exclusion every
  `https://user:password@host` in a README is a finding, which is what retired the pattern the
  first time. `GENERIC_SECRET_RE` is still NOT ported: labelled-secret matching is a false-positive
  engine until someone builds a much larger exclusion list for it. The
  inventory and those patterns are `grep -E` source, so the scanner translates POSIX classes —
  Python reads `[[:alnum:]]` as a nested set matching `:` and `a`-`m`, silently widening the pattern.
- The governing failure class is still a command whose status nobody reads: `grep` exits 2 on a bad
  pattern, `2>/dev/null` eats it, and the empty result reads as "found nothing". Any status but 0 or 1
  is a refusal. The scanner's own contract is 0 clean / 10 findings / 3 unusable inventory, and the
  gates refuse on anything else — including a git that timed out under `pipefail`.
- `gates/tools/replay-gate-blocks.py diff` sandboxes `$HOME`, which makes the gh gate's home-path
  normalisation a no-op and reported 51 moved verdicts where production moves 2. Measure that gate
  with the operator's own HOME; `replay` is faithful for `pre-push`.
- `gates/verify-vendor-contract.sh` reds on any edit to the `~/lore/decisions/` clause in CLAUDE.md
  (the Codex and Kimi AGENTS.md links pair on the same clause) until a manual `--emit-baseline` reseal.
- The deletion guards (rm-guard, delete-manifest, destructive-git, nested-clone, codex-exec) were
  retired on 2026-09-01 by the operator's ruling: easy to bypass, costly in false positives. The `~/to-delete`
  convention in CLAUDE.md is guidance, not a hook. `gates/state/` keeps their block corpora.
- Suite discipline: `KNOWN_RED` is a ticketed deferral guarded both ways, and defects per review
  round ran 7, 3, 11, 19, 51 with every round shipping green, so green is not coverage. A case must
  fail for the reason in its name; `gates/tests/test-privacy-gates.sh` ends with negative controls
  that remove a matcher and require the case to pass — the push control needs an OUTGOING commit
  carrying the literal, because at `main == origin/main` it passed with nothing to scan at all.
  It also asserts the scanner directly (masking, the 20-finding cap, a 200 KB clean drain), since
  every one of those could be broken without moving a gate status. `red-suite.sh` asserts 137 on
  SIGKILL to record a limit, and `--only <regex>` that selects no section now exits 1: a mistyped
  filter reported a green suite off the store check alone.

- A suite that runs real git commands in scratch repositories must clear Git's repository-local environment
  first (`git rev-parse --local-env-vars`; githooks(5)). The pre-commit hook passes `GIT_DIR` and
  `GIT_INDEX_FILE` of the live repository, and on 2026-10-01 the fixture suite, started by `check-staged.py` with
  that environment, wrote fifteen fixture sections into this repo's config, reset a branch, created fixture refs
  and pushed a `feature` branch to origin (a ticket). `check-staged.py` now strips those variables
  (`foreign_repo_env`) and `test-privacy-gates.sh` unsets them itself. Control: run the suite with `GIT_DIR`
  pointing at a throwaway repository; its config and refs must be byte-identical afterwards.

- Both privacy gates consume the generated finite policy in `hooks/lib/privacy-decision.sh`.
  Bend is the source of truth under `hooks/privacy-decision/`; its
  [README](privacy-decision/README.md) documents the laws and generation checks.
  The local pre-commit hook automatically checks an immutable staged snapshot on
  relevant edits: full fixture regressions for gates/scanner/lexer/dispatch, and
  proofs/native-table equivalence/freshness for policy/build changes. It never
  stages files. Law claims, LAWS-owned semantic predicates, and LAWS/Main import
  bindings are preserved against HEAD unless
  the owner explicitly authorizes a requirement change. `build.sh` regenerates;
  its proof and compiler inputs are one content-checked snapshot and publication
  refuses live source drift. Runtime policy uses only Bash builtins, with
  no engine selector, native binary or hash verification. The generated visibility
  fold drives the real target loops; unknown visibility still permits clean content
  after an all-class scan. Keep the existing privacy and deadline/fail-closed suites
  green. Do not change registered hook commands or trusted indices for this policy.
  Explicit gh content-file references must resolve and scan completely (1 MiB
  maximum; overflow refuses). Quote-aware extraction never evaluates expansions;
  dynamic payloads refuse while literal GraphQL variables remain valid. Quoted
  heredoc bodies are diagnostic/data tokens, not command positions; actual writes
  before/after remain judged and original text is still scanned. Multiple actual
  git pushes require separate tool commands before any early exit. Follow the
  README for local-hook installation, extension checks and the remaining bounds.
  a ticket strengthens the actual exported fold and checked scan-coverage verdict
  under 26 Bend laws. A scanner-reported class is required on clean/finding status;
  an all-class plan cannot be cleared by a secrets-only scan. Unknown network push
  destinations now select all-class scanning. A local path remains an owner-trusted
  audience assumption (a local repository may still be publicly served); private
  SSH aliases require exact ignored `private-push-destinations.txt` pins, an unchanged,
  proxy-free `ssh -G` mapping, and an endpoint inside the owner's overlay networks or DNS
  suffixes listed in the ignored `private-push-networks.txt`. No destination address,
  network or suffix is stored in tracked files.


## Codex dispatch and trust

- Codex gates every hook behind a `trusted_hash` in `~/.codex/config.toml [hooks.state]`, keyed by
  hooks.json path plus event and index. `codex/hooks/pre_tool_use.py` runs BOTH privacy gates in
  sequence — the gh gate under 3 s, then the pre-push gate under 18 s, first exit 2 wins; a timeout,
  a crash, a signal (TERM/HUP/INT/PIPE), a closed stderr or a malformed event all end in exit 2,
  because every other status permits. It dispatched only the gh gate until 2026-09-01, whose
  git-free prefilter allows at once, so every Codex `git push` went unscanned.
  Change a hook command and that hook stops running SILENTLY:
  nothing in the `--json` stream, nothing in `~/.codex/log/`. the operator re-approves once in the TUI
  startup hook review; automation verifies with `--dangerously-bypass-hook-trust`. Measured on
  0.151.0: a symlinked `hooks.json` is read, and hook processes inherit the caller's environment.
