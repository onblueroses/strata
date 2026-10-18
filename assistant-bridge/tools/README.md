# Bridge operations

Python 3.11+ tools that move only policy-approved files between the vault and this
repository. Note contents are data, never commands. Denials, conflicts, scanner
uncertainty, remote mismatch, and audit failure stop the write-capable operation.

The server runs the jobs from a root-owned copy of `tools/` under
`/usr/local/lib/assistant-bridge/`, installed from a reviewed commit, never from the
worktree. The [deployment templates](../deploy/README.md) configure site paths and users:

| Job | User | Cadence | Does |
| --- | --- | --- | --- |
| publish | `bridge-vault` | 5 min | mirrors the policy subset of the vault into `vault/` on `main` |
| apply | `bridge-vault` | 1 min | writes the assistant's inbox pull requests into the vault |
| respond | root | 1 min | answers the assistant's issues, mirrors `for:assistant` Linear tickets |
| check | root | 15 min | restarts a failed job, pages the owner when one stays failed |

## Server layout

Python 3.11+, `rsync`, `git`, systemd, and gitleaks. The following paths are example values configured in [env.example](../deploy/env.example).

| Item | Location |
| --- | --- |
| Vault source | `/srv/brain-vault` |
| Git working copy | `/srv/assistant-bridge` |
| Policy | working copy `bridge-policy.toml` |
| Audit JSONL (publish, apply) | `/var/lib/assistant-bridge/audit.jsonl` |
| Apply backups | `/var/lib/assistant-bridge/backups/` |
| Shared lock | `/var/lib/assistant-bridge/bridge.lock` |
| Pending push | `/var/lib/assistant-bridge/publish-pending.json` |
| Responder state and audit | `/var/lib/assistant-respond/state/` (root, 0700) |
| Environment for all units | `$BRIDGE_CONFIG_DIR/bridge.env` (root-owned, 0644) |
| Pause markers | `$BRIDGE_PAUSE_DIR/<job>` (root-owned) |
| Check counters | `/var/lib/assistant-bridge/check/` |

The environment file is root-owned under `/etc` because respond and check run as root:
a user who could replace it would set a root job's environment. Secret file paths are
per unit: apply reads `bridge-vault`'s token copy, respond the root copies under
`$BRIDGE_CONFIG_DIR/`. Every token file must be a regular, singly linked file owned by
root or the reading user, mode `0600`, outside the vault and worktree. Tokens never
appear in output or audit records.

`origin` must equal `BRIDGE_REMOTE_URL` over a deploy key. Root-owned `$BRIDGE_VISIBILITY_ATTESTATION` attests that the
repository is private; publish and apply also check GitHub anonymously every run and
stop on a mismatch or API failure. Renew the attestation within 31 days and after any
identity or visibility change.

All flags have uppercase `BRIDGE_*` environment fallbacks (`VAULT`, `WORKTREE`,
`REMOTE_URL`, `POLICY`, `GITLEAKS`, `GITLEAKS_CONFIG`, `AUDIT_LOG`, `LOCK_FILE`,
`VISIBILITY_ATTESTATION`, `PUSH_STATE`, `BACKUP_DIR`, `TOKEN_FILE`, `REPO`, `AUTHOR`,
`API_URL`, `AUTO_APPLY_ROOTS`, `PAUSE_DIR`, `JOB_STATUS_DIR`); `BRIDGE_GIT_NAME` and
`BRIDGE_GIT_EMAIL` set the publisher's commit identity.

## Publish

The vault is the source of truth for `vault/`. Each run rebuilds `vault/` from the
policy subset, runs gitleaks from an empty temporary directory (a pushed
`.gitleaksignore` cannot suppress findings), commits only when something changed, and
pushes `main`. Preview with `--dry-run`; an unchanged mirror exits 0 without a commit.

When `origin/main` moved since the last run: if it descends from local `main`, publish
fast-forwards and then overwrites whatever the new commits changed under `vault/`
(printed as `reverted "<path>"`, recorded as `reverted_remote`), so an edit made on
GitHub never reaches the vault. Files outside `vault/` follow `main` but cannot change
what is published: the index for `vault/` is rebuilt with `git add --force`, attributes
are read from the empty tree, and the staged tree is compared entry by entry before the
commit (`publish-verify-failed` stops the run). A force push or other history rewrite
stops publish with `remote-history-changed`; a `main` that replaces `vault/` with a file
stops it with `publish-root-replaced`. A change to `bridge-policy.toml` on `main` stops
publish with `remote-history-changed` until the owner deploys it (the jobs read the
policy pinned to the checked-out commit).

Publish waits up to 30 seconds for the shared lock, then skips the run.

## Apply

Every minute, apply lists open pull requests by `BRIDGE_AUTHOR` (`assistant-account`)
and writes one into the vault when every changed file lies under an auto-apply root
(`BRIDGE_AUTO_APPLY_ROOTS`, default `5 Inbox`, compared exactly and case-sensitively)
and every check passes: policy allow and deny rules, no deletion or rename, valid
frontmatter, size limits, no conflict with a vault file changed since the PR's base,
gitleaks on the incoming bytes, free disk. The head is re-read just before the write and
must equal the inspected one. Each applied run creates a restore-compatible backup and
is remembered by `(repository, PR, head)` in the audit log, so a later GitHub failure
retries only the comment and close, never the write. The PR is then closed with a
comment naming the run.

A refusal (a denied path, a deletion, broken frontmatter, a secret, a conflict) is
commented once per head and category and audited; refusals decided by the diff alone
are skipped on later runs until a new head, while policy denials, secret findings,
conflicts and scanner errors are re-checked every run.

A pull request with any file outside the roots is held whole: one comment per head says
it is not applied automatically and waits for a person, who makes the change in the
vault by hand; a `held` audit record makes later runs skip it without fetching. A held
PR exits 0. `--require-label <name>` adds an operator label as an extra gate. The job is
a no-op unless the policy has `[inbound] enabled = true` and `mode = "review-gated"`,
the global inbound kill switch.

Reverse one applied run with `bridge-restore <run-id>`: it verifies every backup,
refuses if an imported target changed later, restores overwritten files atomically and
moves files that run created into its `restore-quarantine/`.

Dry-run apply as the unit would run it:

```sh
systemd-run --wait --pipe --collect -p User="$BRIDGE_VAULT_USER" \
  -p WorkingDirectory="$BRIDGE_WORKTREE" \
  -p EnvironmentFile="$BRIDGE_CONFIG_DIR/bridge.env" \
  -p Environment="BRIDGE_TOKEN_FILE=$BRIDGE_APPLY_TOKEN_FILE" \
  /usr/local/lib/assistant-bridge/bridge-apply --dry-run
```

## Respond

Every minute, as root, the responder has three ordered steps:

1. Answer new open GitHub issue and pull-request conversation items by the assistant once
   (a PR's own body is not a question). Only items whose login is `BRIDGE_AUTHOR` are
   answered; the owner, other agents, bots and the responder's own posts are skipped.
2. Mirror tickets in `BRIDGE_LINEAR_TEAM_KEY` labelled `for:assistant` into GitHub issues, including later
   field changes and the full body of every comment, and close completed mirrors. Only
   a body the secret scan flags is withheld; personal data is not, so a mirrored comment
   reaches every reader of this repository and their GitHub notifications.
3. The optional `for:claude` acknowledgement step is off by default because the
   dispatcher handles those tickets. `BRIDGE_ACK_FOR_CLAUDE=1` re-enables it. The
   responder is read-only: it may acknowledge a request or answer a factual question,
   and signs its own reply. Machine work goes to the dispatcher through `for:codex`.

The model call: the root wrapper creates a fresh mode-0700 run directory and launches
`codex exec --json` as the unprivileged `assistant-respond` user with the whole task on
stdin, instructions first, then the untrusted packet between `BEGIN`/`END UNTRUSTED
PACKET <nonce>` lines. A fresh receipt opens the packet and must come back in the
answer; the answer is schema-checked and gitleaks-scanned before any post. The model
runs read-only, runs no commands, and the run directory is removed afterwards. A failed
call is classified from Codex's failure events only (`class=auth|other`); an item that
fails is paused and retried with backoff; `BRIDGE_MAX_CODEX_RUNS_PER_HOUR` caps the
spend. The model user has its own ChatGPT login (`codex login --device-auth` as
`assistant-respond` from `/var/lib/assistant-respond/home`); never copy another
account's `auth.json`, two copies of one session invalidate each other's refresh token.

A Linear 5xx, rate limit or timeout skips the rest of that Linear step and the run
still exits 0; the third such run in a row exits 1. Without `BRIDGE_LINEAR_KEY_FILE`
the Linear steps are skipped. `--dry-run` fetches and decides without posting or writing.

Environment: `BRIDGE_REPO`, `BRIDGE_AUTHOR`, `BRIDGE_TOKEN_FILE`,
`BRIDGE_LINEAR_KEY_FILE`, `BRIDGE_RESPOND_STATE`, `BRIDGE_RESPOND_LOCK`,
`BRIDGE_RESPOND_AUDIT_LOG`, `BRIDGE_RESPOND_SCRATCH`, `BRIDGE_RESPOND_USER`,
`BRIDGE_CODEX_BIN`, `BRIDGE_CODEX_MODEL`, `BRIDGE_CODEX_TIMEOUT`,
`BRIDGE_MAX_CODEX_RUNS_PER_HOUR`, `BRIDGE_RULES_DIR`, `BRIDGE_API_URL`,
`BRIDGE_LINEAR_URL`, `BRIDGE_LINEAR_TEAM_KEY`, `BRIDGE_OTHER_AGENT_SIGNERS`,
`BRIDGE_GITLEAKS`, `BRIDGE_GITLEAKS_CONFIG`, `BRIDGE_PAUSE_DIR`. The signer list
contains comma-separated base names; each still accepts up to three qualifier words
in a dated signature. The portable example is in [env.example](../deploy/env.example).

## Check

`bridge-check` (bash) runs as root every fifteen minutes. For each of publish, apply
and respond: a paused job is skipped; a stopped timer is reported; a job whose last run
failed is reset and restarted, with a per-job counter. When a timer is stopped or a job
has failed at three checks in a row, the run exits 1 and the unit's
`OnFailure=bridge-alarm@%n.service` calls the site-provided pager; the pager folds repeat alerts. The check never enables a unit, never touches git, files, the
policy or GitHub, and tells nobody else: if the assistant's PR is not applied, it can ask.

## Pause, revoke, recover

- Pause a job: `touch /etc/assistant-bridge/paused/<job>` (`publish`, `apply`,
  `respond`). The job checks the marker before any work; publish and apply check it
  again once they hold the lock. For an emergency stop also
  `systemctl stop assistant-bridge-<job>.service`. Resume by removing the marker.
- Pause inbound: a reviewed policy change setting `inbound.enabled = false`.
- Revoke publication: remove the deploy key in GitHub. Revoke the assistant or the responder
  token in their UIs.
- Suspected exposure: pause every job, revoke and rotate the affected credential,
  identify affected commits, review before reconnecting.
- A remote mistake is reverted through normal Git history; a local apply is reversed
  with `bridge-restore`. Audit records and backups contain paths and hashes, never note
  bodies or secret values.

## Tests and deploy

```sh
python3 -m unittest discover -s tools/tests -t tools
```

Use [deploy/README.md](../deploy/README.md) for the reviewed-commit gate, unit templates, and dry-run sequence. The gate requires a readable `DEPLOYED_REV`, equality of controls on `origin/main` and the reviewed revision, and owner authorship and committer identity for every control change since the deployed revision.
