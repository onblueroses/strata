<!-- keywords: codex exec, codex review, fast, strong, codex invocation, codex cli, codex flag, codex-review, gate-codex, dangerously-bypass-approvals, skip-git-repo-check, codex config -->
# Codex Invocation Standard

How to invoke the bare `codex` CLI. The flag set differs by subcommand. Pick the right form — flags valid for `codex exec` are NOT all valid for `codex review`. Verified against `codex review --help` (CLI v0.124.0, 2026-04-29).

For day-to-day code/analysis delegation, use the `fast` / `strong` wrappers instead — see `model-delegation.md`. This doc covers the bare `codex` invocations used by specific skills (`/codex-review`, `/verify`, `/review`, `/best-of-n`).

## Quick Nav

| Task | Section |
|------|---------|
| `codex exec` flag form (skill use only) | codex exec |
| `codex review` flag form (diff/commit review) | codex review |
| Defaults from config.toml | Config defaults |
| Which skill uses which form | Skills Using This Standard |

---

## `codex exec` (non-interactive prompt execution)

**Default: do NOT call `codex exec` directly.** Use the wrappers (`fast`, `strong`) — they encode the canonical flag set, handle quota fallback, and are documented in `model-delegation.md`. Bare `codex exec` is blocked by `gate-codex-exec.sh` (PreToolUse Bash hook).

The full-flag form below is reserved for the `/codex-review` skill's Step 3 invocation. The hook allows it through because the `--dangerously-bypass-approvals-and-sandbox` flag is present:

```
codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check \
  -c tools.web_search=true -c model_reasoning_effort=xhigh -c service_tier=fast \
  --model gpt-5.5 "PROMPT"
```

Top-level flags (`--dangerously-bypass-approvals-and-sandbox`, `--skip-git-repo-check`) are valid here. `--model` overrides config.toml's default model.

## `codex review` (diff/commit review subcommand)

```
codex [--dangerously-bypass-approvals-and-sandbox] [-c tools.web_search=true] \
  review [--uncommitted | --base BRANCH | --commit SHA]
```

`--dangerously-bypass-approvals-and-sandbox` is a top-level codex flag and works for `review` (mostly redundant since config.toml already sets approval=never + sandbox=danger-full-access, but defensive).

`--skip-git-repo-check` is `exec`-only — it is NOT a top-level flag. Passing it fails with `error: unexpected argument '--skip-git-repo-check' found`. Drop it for review.

`--model` is also `exec`-only at the CLI flag level for review; override the model via `-c model="..."` instead if you need a non-default.

`-c key=value` flags must come BEFORE the `review` subcommand (top-level config overrides). The review-target flags (`--uncommitted` / `--base` / `--commit`) come AFTER `review`. Sandbox / approval / reasoning / service-tier all come from `~/.codex/config.toml` defaults.

Review takes 5-15 minutes on substantial diffs (xhigh + agentic exploration). Always dispatch in background via `run_in_background: true`; use `Monitor` on the log file to watch progress.

## Config defaults

`~/.codex/config.toml` sets `approval_policy = "never"`, `sandbox_mode = "danger-full-access"`, `model_reasoning_effort = "xhigh"`, `service_tier = "fast"`, `model = "gpt-5.4"`. The exec-form flags are defensive against config drift; for review, the config defaults are sufficient.

`tools.web_search=true` is NOT in config defaults — pass `-c tools.web_search=true` explicitly for either subcommand if web search matters.

## Skills Using This Standard

- `/codex-review` — Step 3 invocation, uses `codex exec`
- `/verify` — F0, uses `codex review --uncommitted`
- `/review` — Step 1a + Step S0, uses `codex review`
- `/best-of-n` — Phase 1 + 2, uses `codex exec`

When updating any of these skills, use the per-subcommand form above — do not paste the `exec` flag set into a `review` invocation.
