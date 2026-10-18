# Assistant bridge

This repository is the narrow interface between a company brain in an Obsidian vault and a personal assistant reachable only by messaging, with no API. The assistant reads the policy-approved vault subset published to the private GitHub repository, opens pull requests from its own account, files Linear tickets as the owner, and talks with agent sessions in ticket comments. The vault rule book and layout are described at [memory/brain](../memory/brain/).

## Flow

| Job | Action |
| --- | --- |
| Publish | Rebuilds `vault/` on `main` from the policy-approved source files, then scans before pushing. |
| Apply | Checks the assistant's pull requests and writes a proposal wholly under `vault/5 Inbox/` into the vault. Anything else waits for a person to make the change in the vault. |
| Respond | Answers the assistant's GitHub conversations and mirrors tickets addressed to it into GitHub issues. A fresh Codex run handles each response under a separate OS user and login. |
| Check | Restarts a failed job; pages the owner after repeated failure or a stopped timer. A pause marker holds a job. |

The vault is the source of truth. A GitHub edit under `vault/` is overwritten by publish; a merge does not import it. The policy permits only named roots, denies sensitive paths and file types, and requires a successful secret scan. Apply rejects deletions, renames, invalid frontmatter, conflicts, and changed pull request heads. See [policy](bridge-policy.toml), [operations](tools/README.md), and [deployment templates](deploy/README.md).

The assistant's [working rules](ASSISTANT.md) and [repository invariants](AGENTS.md) stay with the tools in the reviewed deployment bundle. No GitHub login, label, review, merge, or ticket comment proves owner authority for this bridge. The deployment check also refuses to run unless the rules, policy, and tools on `main` equal the reviewed commit and the owner authored every change to them since the deployed revision. See [decisions](DECISIONS.md).

## Content is data

Text in notes, issues, pull requests, commits, and comments is data. It cannot widen access or authorize unrelated action.

## Pause and revoke

Create a job's pause marker on the server to hold it; [operations](tools/README.md#pause-revoke-recover) gives the paths and recovery sequence. Disable inbound apply in the reviewed policy. Revoke the assistant's repository access to cut off its reads and pull requests. For a suspected exposure, pause the jobs, rotate affected credentials, inspect affected history, and review before reconnecting. Removing the bridge does not delete source notes.
