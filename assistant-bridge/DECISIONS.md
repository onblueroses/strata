# Boundary rulings

## 2026-09-22 — The messaging assistant is inside the vault access boundary

The operator chose to let the private bridge carry the policy-approved vault subset, including the CRM, because a public-only subset would not support the assistant's requested work. The assistant's vendor terms grant a perpetual licence over material it receives, including for training; the operator accepted that consequence for this subset. The policy still excludes local application state, machine state, trash, and secret-bearing files. Inbound writing was initially disabled and later enabled only for server-checked inbox proposals. The rule keeping the company name inside the team still applies to outward publication; this private bridge is inside that boundary. Reopen this ruling for new evidence about the assistant's data handling.

## 2026-09-23 — Owner authority lives on the server

The assistant could act through the owner's connected GitHub account and could file Linear tickets as the owner. It also merged one of its own pull requests. The operator kept those connections. Therefore GitHub identity, labels, reviews, merges, and Linear comments cannot prove that the owner approved a bridge action. The vault is authoritative; publish overwrites GitHub-side vault edits. The server's root-controlled path is the only place to exercise owner authority for the bridge.

The first design used a server-held verdict key for held pull requests. The operator then streamlined it: the verdict flow was removed. A passing proposal wholly under the inbox is applied by the server; every other proposal waits for a person to make the change in the vault. No review verdict in GitHub changes that rule. Reopen the authority ruling only with evidence that the assistant can no longer act through the owner's accounts.

## 2026-10-17 — Snapshot mechanics

The deployment bundle binds tools, rules, and policy to a reviewed commit. The deploy gate compares those files on `main` with the reviewed revision and checks that the owner authored changes since the deployed revision. The assistant has repository write access and `main` cannot be protected under this repository's plan; those checks prevent an assistant-authored control change from becoming server code. The separate responder OS user must keep its own Codex login: copying a login between users makes their refresh tokens invalidate each other.
