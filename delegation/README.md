# Cross-runtime delegation

The wrappers/ directory holds the operational dispatch routes for Codex, DeepSeek, and free models. A caller owns the brief, provider choice, spend boundary, child lifecycle, and review of results. The delegate returns findings and memory candidates; it does not settle shared memory.

codex-run.py is a smaller portable Codex route. It supports fast, bounded, and strong tiers, requires a ChatGPT subscription login, selects the OpenAI provider explicitly, and keeps events and errors in the target repository's .local/delegation/ directory. `python3 delegation/codex-run.py fast --dry-run "Review this change"` inspects the command without launching. Workspace writes require an explicit sandbox choice.

The DeepSeek routes are metered and need spend authorization. Free routes accept public material only and run in a bubblewrap silo. See [wrapper contracts](wrappers/README.md) and [provider inventory](../providers.toml). Never use prime-inference or fall back to it; verify the provider before every launch.
