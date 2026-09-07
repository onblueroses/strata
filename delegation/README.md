# Cross-runtime delegation

Native runtime and model provider are separate choices. Claude can dispatch Codex subprocesses or an explicitly authorized DeepSeek route; a Codex primary uses its native role tools. Kimi uses its own native client. A child remains a delegate regardless of the model's strength.

`codex-run.py` is the portable counterpart of the local `codex-fast` and `codex-strong` wrappers. It keeps native model tiers, subscription preflight, a bounded delegated prompt, process lifetime, and durable output. It leaves out private memory injection, cache/circuit-breaker state, and telemetry collectors. It defaults to a read-only sandbox; opt into workspace writes only for an authorized implementation brief.

```sh
python3 delegation/codex-run.py fast --dry-run "Review the proposed file list."
python3 delegation/codex-run.py strong --file .local/review-brief.md
python3 delegation/codex-run.py bounded --sandbox workspace-write --file .local/task-brief.md
```

The first command only prints the launch configuration. Actual runs verify `codex login status`, explicitly select `openai`, and use the ChatGPT subscription. They preserve event and error logs under the target repository's `.local/delegation/`. A timeout or interruption stops the child process group; the parent owns the handle until completion. Session IDs printed by Codex remain available for native `codex exec resume`; inspect its current help before resuming.

The wrapper does not grant memory authority and cannot sandbox external services merely through instructions. Configure native tool permissions and hook adapters for the target runtime. It does not bypass hook trust, install software, or silently switch providers.

For `dsh-primary`, `dsh-agent`, `ds-flash`, `ds-pro`, and `ds-codex`, see [the DeepSeek setup](../deepseek/README.md). These are metered routes with separate spend authorization. Their external harnesses and bridge are dependencies, not subscription fallbacks. The route matrix in [providers.toml](../providers.toml) records all observed routes; it is Strata inventory, not a native client configuration.
