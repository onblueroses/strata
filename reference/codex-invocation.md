<!-- keywords: codex exec, codex exec resume, codex review, codex cli, codex invocation, codex flags, fast lane, strong lane, codex-review skill, verify, review, gate-codex-exec, gate-codex hooks, dangerously-bypass-approvals-and-sandbox, skip-git-repo-check, service_tier fast, model_reasoning_effort, config.toml defaults, web_search, background stdin hang, dev/null, uncommitted diff review, output schema -->
# Codex Invocation Standard

How to invoke the bare `codex` CLI. Each subcommand accepts a different flag set.

These forms match codex-cli 0.145.0.

For day-to-day code/analysis delegation, use the `fast` / `strong` lane wrappers instead — see `reference/model-delegation.md`. This doc covers the bare `codex` invocations strata genuinely uses: the `/codex-review`, `/verify`, and `/review` skills, plus the `gate-codex-*` hooks.

## Quick Nav

| Task | Section |
|------|---------|
| `codex exec` flag form (skill use only) | codex exec |
| Continue a stored Codex session | codex exec resume |
| `codex review` flag form (diff/commit review) | codex review |
| Defaults from config.toml | Config defaults |
| Which skill uses which form | Skills Using This Standard |

---

## `codex exec` (non-interactive prompt execution)

**Default: do NOT call `codex exec` directly.** Use the lane wrappers (`fast`, `strong`) — they encode the canonical flag set, handle quota fallback, and are documented in `reference/model-delegation.md`. Bare `codex exec` is blocked by `gate-codex-exec.sh` (PreToolUse Bash hook).

The full-flag form below is reserved for the `/codex-review` skill's invocation. The hook allows it through because the `--dangerously-bypass-approvals-and-sandbox` flag is present:

```
codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check \
  -c tools.web_search=true -c model_reasoning_effort=xhigh -c service_tier=fast \
  --model <PICK_REVIEW_MODEL> "PROMPT"
```

Top-level flags (`--dangerously-bypass-approvals-and-sandbox`, `--skip-git-repo-check`) are valid here. `--model` overrides the config.toml default model. When run in the background (`run_in_background: true`), append `< /dev/null` so codex does not hang forever on "Reading additional input from stdin" at 0 CPU.

## `codex exec resume`

`codex exec resume` exists in codex-cli 0.145.0 and later. It adds a follow-up turn to stored history.

```bash
codex exec resume 12345678-1234-4123-8123-123456789abc "Follow-up prompt"
codex exec resume --last "Follow-up prompt"
```

Resume rejects `-s` and `-C`. Map the sandbox through `-c 'sandbox_mode="read-only"'`.

The original working directory persists.

Use an explicit `-` prompt position when piping stdin.

```bash
codex exec resume 12345678-1234-4123-8123-123456789abc - < prompt.txt
```

Without `-`, the pipeline waits for prompt input. `--last` selects the newest stored session.

`--output-schema FILE` works with both `exec` and `exec resume`.

## `codex review` (diff/commit review subcommand)

```
codex [--dangerously-bypass-approvals-and-sandbox] [-c tools.web_search=true] \
  review [--uncommitted | --base BRANCH | --commit SHA]
```

`--dangerously-bypass-approvals-and-sandbox` is a top-level codex flag and works for `review` (mostly redundant since config.toml already sets approval=never + sandbox=danger-full-access, but defensive).

`--skip-git-repo-check` is `exec`-only — it is NOT a top-level flag. Passing it fails with `error: unexpected argument '--skip-git-repo-check' found`. Drop it for review.

`--model` is a top-level flag, valid only BEFORE the `review` subcommand; use `codex --model <PICK_MODEL> review ...` or `codex review -c model="<PICK_MODEL>" ...` for a non-default. Passing `--model` AFTER `review` fails.

`-c key=value` flags must come BEFORE the `review` subcommand (top-level config overrides). The review-target flags (`--uncommitted` / `--base` / `--commit`) come AFTER `review`. Sandbox / approval / reasoning / service-tier all come from `~/.codex/config.toml` defaults.

Review takes 5-15 minutes on substantial diffs (xhigh + agentic exploration). Always dispatch in background via `run_in_background: true`, append `< /dev/null` so it does not hang on stdin, and use `Monitor` on the log file to watch progress.

## Config defaults

`~/.codex/config.toml` sets `approval_policy = "never"`, `sandbox_mode = "danger-full-access"`, `model_reasoning_effort = "xhigh"`, and `model = "<PICK_DEFAULT_MODEL>"`. `service_tier = "fast"` is NOT a config default; pass `-c service_tier=fast` explicitly when you want it (the exec form above does). The exec-form `-c` overrides are defensive against config drift; for review, the config defaults are sufficient.

`tools.web_search=true` is NOT in config defaults — pass `-c tools.web_search=true` explicitly for either subcommand when web search matters.

## Skills Using This Standard

- `/codex-review` — uses `codex exec` (the full-flag form above).
- `/verify` (Full/Deep tier) — uses `codex review --uncommitted`.
- `/review` — uses `codex review --uncommitted`.

When updating any of these, use the per-subcommand form above — do not paste the `exec` flag set into a `review` invocation.
