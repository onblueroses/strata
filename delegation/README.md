# Cross-runtime delegation

The wrappers/ directory holds the operational dispatch routes for OpenCode Go, Codex and DeepSeek. A caller owns the brief, provider choice, spend boundary, child lifecycle, and review of results. The delegate returns findings and memory candidates; it does not settle shared memory.

Route order (ruling of 2026-11-12): `opencode-fast` comes first for bulk work and groundwork, meaning implementation, edits, extraction and chores that are not hard. `codex-fast` takes mechanical work that needs Codex, and `codex-strong` takes difficult work and review.

codex-run.py is a smaller portable Codex route. It supports fast, bounded, and strong tiers, requires a ChatGPT subscription login, selects the OpenAI provider explicitly, and keeps events and errors in the target repository's .local/delegation/ directory. `python3 delegation/codex-run.py fast --dry-run "Review this change"` inspects the command without launching. Workspace writes require an explicit sandbox choice.

The DeepSeek routes are metered and need spend authorization. Free models run only on public inputs, inside a sandbox with no view of the machine, and every fleet's output goes through [quote-check](quote-check) (ruling of 2026-11-10): it opens the page behind each quoted table row and reports whether the quote is there exactly, in part, not at all, or whether the page did not load. A found quote confirms the wording, not the report's reading of it. See [wrapper contracts](wrappers/README.md) and [provider inventory](../providers.toml). Never use prime-inference or fall back to it; verify the provider before every launch.
