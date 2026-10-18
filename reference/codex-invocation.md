<!-- keywords: codex cli, codex exec, codex review, codex invocation, hook trust, provider, login, stdin -->
# Codex CLI reference

Verified locally against `codex-cli 0.153.3`. Recheck with `codex --help`, `codex exec --help`, and `codex review --help` after an update.

## Before a launch

- Check authentication with `codex login status`; use `codex doctor --summary` when the CLI, config, or authentication looks suspect.
- Use the native subscription-backed route selected for the task. The local native slugs are `gpt-6-sol`, `gpt-5.6-terra`, and `gpt-6-luna`; do not fall back to Prime Inference.
- A model override is a deliberate choice, not boilerplate. `codex exec --model gpt-5.6-terra "PROMPT"` is the ordinary non-interactive form.
- Authorization still comes from the task and the workspace instructions. Do not add `--dangerously-bypass-approvals-and-sandbox` merely to make a command work; it disables confirmations and sandboxing.

## `codex exec`

`exec` runs a non-interactive turn. Give the prompt as an argument when possible:

```bash
codex exec --model gpt-5.6-terra "Review the current diff. Return findings only."
```

When the prompt is omitted, or is `-`, `exec` reads stdin. A background job with no intended stdin must close it:

```bash
codex exec "PROMPT" </dev/null >"/tmp/codex-$(date +%s).log" 2>&1 &
```

If both a prompt argument and piped stdin are present, the CLI appends stdin as a `<stdin>` block. Use that only when the extra material is intentional. `--skip-git-repo-check` is available for `exec`, but use it only when running outside a repository is actually required.

`codex exec resume` and `codex exec fork` are available; consult their own help before using them because their option surfaces differ.

## `codex review`

The installed CLI has both `codex review` and `codex exec review`. The top-level command is the short form for a repository review:

```bash
codex review --uncommitted
codex review --base main
codex review --commit <sha>
```

Add a quoted positional prompt for review-specific instructions. Use `-` only when deliberately piping those instructions on stdin. For a background review that does not receive piped instructions, close stdin as above and capture its output; choose any outer timeout based on the size and risk of the review rather than an inherited fixed duration.

`codex review --help` supports `--uncommitted`, `--base`, `--commit`, `--title`, `-c`, feature toggles, and `--strict-config`. Set a review-only model override through its config option, for example `codex review -c 'model="gpt-6-sol"' --uncommitted`. Do not copy an `exec` flag bundle into a review command.

## Hook trust

The managed hook file is `<codex-config>/hooks.json`, a link to this repository's `codex/hooks.json`. Codex records a `trusted_hash` per hook in `<codex-config>/config.toml` under `[hooks.state]`. Changing a hook command requires a fresh approval in the Codex startup hook review; until then that hook can silently stop running.

`--dangerously-bypass-hook-trust` exists for a one-off invocation whose automation has already vetted the hook source. It does not update the persisted trust record. Treat it as verification tooling, not a default launch flag.

Run `bash <agent-config>/codex/install.sh --check` after managed-link changes. The installer does not touch local credentials, sessions, or `config.toml`.
