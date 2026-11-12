# Claude Code operating layer

The agent definitions in agents/ implement bounded review, research, and orchestration roles. settings.example.json contains only model, effort, default permission mode, the subagent default model, native hook registrations, instruction-file plugin choice, and external-memory setting. hooks.example.json gives the same native hook topology with __STRATA_ROOT__ paths for a checkout-based install. Merge the entries appropriate to the target account; hook command paths and permissions need deliberate local review.

The hooks/ tree contains the hooks that add context: the session wake and core-note hooks, the clock, compaction continuity, and the desktop notification. The guards and gates of the live setup are private. Settings for the hooks are in [config/hooks-runtime.env.example](config/hooks-runtime.env.example). Run the shell tests from hooks/ before changing a registration. Native command-hook timeouts are seconds.

hcom registers its own hooks at each launch, so no hcom entries belong in settings.json.

OptMem and the issue tracker are external services. The native hooks use their command interfaces; credentials belong in local configuration.
