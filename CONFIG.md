# CONFIG.md

The lane contract every model bound in `config/model-map.toml` must satisfy. Tune the bindings as models churn; the lane shape stays.

## Symbolic lanes

| Lane | Role | Bind to |
|------|------|---------|
| `strong` | Heaviest reasoning. Load-bearing design, security review, hardest debugging, final adversarial pass. Reach for it only when synthesis quality genuinely depends on it. | The strongest reasoning model you have access to with tool use (read/write/bash/grep). Examples: `claude-opus-4-7`, `gpt-5.5`, `gemini-2.0-pro-thinking`. |
| `fast` | Cheap parallel code workhorse. Recon sparks, focused factual queries, code extraction, anywhere breadth-of-coverage beats depth-of-reasoning. | A fast code-tier model. Examples: `claude-haiku-4-5`, `gpt-5-mini`, `deepseek-v4-flash`. |
| `grader` | Cheap parallel sanity-check lane. 3-5 parallel review panels, pre-flight checks, bulk filtering. Sub-cent per call; bar for invocation is "would this change my next move". | The cheapest credible-quality model. Examples: `deepseek-v4-flash`, `gemini-2.0-flash`. |
| `breadth` | Non-primary breadth lane / strong-lane fallback. Second-opinion passes, codex throttle fallback, a different model voice without burning the strong budget. | A model from a different provider than `strong`. Examples: if strong = `claude-opus-4-7`, breadth = `gpt-5.5` or `deepseek-v4-pro`. |

## Provider routing

Model id prefix selects the provider in `bin/lib/agent.py`:

| Prefix | Provider | Env var |
|--------|----------|---------|
| `claude-` / `anthropic/` | Anthropic | `ANTHROPIC_API_KEY` |
| `gpt-` / `openai/` / `o1` / `o3` | OpenAI | `OPENAI_API_KEY` |
| `deepseek-` | DeepSeek (OpenAI-compatible) | `DEEPSEEK_API_KEY` |
| `gemini-` / `google/` | Google | `GEMINI_API_KEY` |

Set env vars in `$STRATA_HOME/.local/.env` (one `KEY=VALUE` per line, gitignored) or export them in your shell.

## Wrapper contract

Every lane wrapper exposes the same interface:

```
strong "prompt"                  # inline
strong --file PROMPT.md          # from file
echo "prompt" | strong           # from stdin

strong --system "override system prompt" "prompt"
strong --timeout 1800 "prompt"   # default 1800s
```

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success — final answer on stdout |
| 1 | Usage error (missing prompt, unknown flag, missing model-map binding) |
| 2 | API / model error (non-quota) |
| 3 | Rate limit / quota exhausted — caller should fall back per the all-lanes-throttled rule in CLAUDE.md |
| 4 | Auth error (missing or rejected API key) |
| 5 | Empty content from model after one re-prompt attempt |
(Internal: `timeout(1)` produces exit 124 when the wall-clock cap fires. The wrappers remap this to exit 3 so callers see a single quota-or-timeout fallback signal. A stderr line names the original timeout so logs preserve the distinction.)

### What goes to stdout vs stderr

- stdout: the model's final answer text
- stderr: diagnostics, throttle notices, error messages

Caller code should capture stdout and check the exit code to decide whether to proceed, fall back to a sibling lane, or escalate.

## Tuning

When a model id deprecates or a stronger model ships, edit `config/model-map.toml`. No other files need to change — every skill, hook, and command references the symbolic lane, not a specific model id.
