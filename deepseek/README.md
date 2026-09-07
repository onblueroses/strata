# DeepSeek routes

This directory records the live DeepSeek primary and delegate routes in portable form. It does not include the DeepSeek Harness, its virtual environment, telemetry collector, credentials, memory store, or private issue and vault integrations. The installed Harness did not expose a public upstream remote in the inspected files; provide the official Harness source through the target installation process.

## Routes

| Route | Role | Observed model | Spend and authority |
| --- | --- | --- | --- |
| `dsh-primary` | User-facing primary | `deepseek-v4-flash`; `--pro` selects `deepseek-v4-pro` | Metered DeepSeek API. Every paid run requires `--confirm-spend`. The primary owns acceptance and shared-ledger writes. |
| `dsh-agent` | Bounded agentic delegate | `deepseek-v4-flash`; `--pro` selects `deepseek-v4-pro` | Metered DeepSeek API. It follows a bounded brief and returns results or memory candidates. |
| `ds-flash` | Agentic delegate | `deepseek-v4-flash` | Metered DeepSeek API through the external `pydantic-ai` delegate harness. It has read, write, directory, shell, and grep tools. |
| `ds-pro` | Agentic delegate | `deepseek-v4-pro` | Metered DeepSeek API through the same external `pydantic-ai` harness, with a deeper model. |
| `ds-codex` | Codex-shaped agentic delegate bridge | `deepseek-v4-flash` by default; model override supports the observed Pro route | Metered DeepSeek API through a local LiteLLM bridge and the local Codex CLI. It supports sandbox, resume, JSONL, and tool execution through those external components. |

The primary uses the official DeepSeek provider and the API endpoints in [primary-overlay.example.yml](primary-overlay.example.yml). The overlay disables native child, fork, workflow, and Ralph surfaces because the live harness cannot attenuate child memory authority. Delegate through a separately managed bounded launcher.

Load the repository's shared `AGENTS.md` first. Add `deepseek/AGENTS.md` for the user-facing primary or `deepseek/AGENTS.delegate.md` for a bounded child; the overlay narrows and specializes the shared contract. Do not replace the shared contract with the DeepSeek overlay.

## Adaptation

`AGENTS.md` is the primary instruction overlay. `AGENTS.delegate.md` is the delegated boundary. `primary-overlay.example.yml` preserves the live provider and disabled-surface shape with a portable home placeholder. `provider.env.example` shows the required secret name without a value. `codex-provider.example.toml` records the separate local bridge used only by `ds-codex`.

`launch-adapter.sh` is a small guard around an externally installed `dsh-primary`. It supports offline prompt or help inspection and requires an explicit spend flag for a paid run. It makes no claim to replace the Harness installer or driver.

Do not run a paid route from this repository until the target operator supplies credentials, installs the external harness, verifies the provider, and authorizes the spend. The adapter's validation path makes no network call; a paid invocation intentionally forwards to the external launcher and may call the provider.
