# Kimi Code route

The inspected Kimi Code client uses its native CLI and OAuth-backed managed provider. The observed default model is `kimi-code/k3-256k`; the configured model catalog also contains `kimi-code/k3`, `kimi-code/kimi-for-coding`, and `kimi-code/kimi-for-coding-highspeed`.

The client reads an instruction file through `AGENTS.md`. The live file is a symlink to the operator's shared instruction source. Load the repository's shared `AGENTS.md` first, then apply [kimi/AGENTS.md](AGENTS.md) as an overlay where the target client supports a second instruction layer; otherwise merge its short Kimi-specific rules into the shared file. Do not replace the shared contract with this overlay. This repository does not copy the live link target or session state.

[config.example.toml](config.example.toml) preserves the observed provider, model aliases, context sizes, thinking settings, and search/fetch service shape. OAuth storage remains a local client concern. Empty API-key fields are placeholders, not credentials.

Kimi is a subscription or managed-client route according to the target account. Verify the current account, model availability, permissions, and metering before launch. This snapshot provides no Kimi launcher, install flow, or paid-client invocation.
