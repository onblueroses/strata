# DeepSeek operating layer

This directory contains a user-facing primary profile, its isolated installer, startup memory renderer, provider doctor, static overlay, and lifecycle skills. `dsh-primary` lives under delegation/wrappers/ and installs with this profile. Delegated DeepSeek routes use a separate home and return memory candidates to a primary; the primary may settle accepted notes under the shared memory contract.

The primary launcher offers an offline `--print-prompt` path. Paid dispatch requires `--confirm-spend` after spend authorization, validates the official provider and the isolated profile, and writes a per-run overlay. The harness runs with broad local access, so its native child-launch plugins are disabled: a child launched inside the same process could inherit primary memory authority. The command-tool environment does not expose the provider key as a dependable isolation boundary.

Run `python3 deepseek/install.py --check` and `python3 deepseek/doctor.py` before dispatch. `python3 -m unittest discover -s deepseek/tests` exercises the installer, startup renderer, overlay, and launcher without a model call. `launch-adapter.sh`, `provider.env.example`, `codex-provider.example.toml`, and `primary-overlay.example.yml` remain portable entry and configuration examples for external clients. The installed profile uses primary-overlay.yml.

Persistent interactive mode and broader harness parity require separate validation. The issue tracker owns those follow-ups.
