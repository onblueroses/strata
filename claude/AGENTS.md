# AGENTS.md — the agent-config repository

Repo-local knowledge for the agent configuration repository (the live `~/.claude`): cross-file invariants,
operator rulings, and traps that already bit once. The constitution is the shared contract at the root of
this snapshot, not this file.

## Instruction files

- Claude Code reads `AGENTS.md` natively since 2.1.277. The user setting
  `pluginConfigs.agents-md@builtin.options.instructionFiles = claude-md-and-agents-md` (settings.json,
  2026-09-21) loads both files in repos that carry a `CLAUDE.md` and an `AGENTS.md`; the default skips
  `AGENTS.md` there. Project and local settings ignore this key.
- Because the config directory sits inside `$HOME`, `~/AGENTS.md` and this file load into every session
  under `$HOME` as project instructions of `~`. Keep this file short; it is read far outside the config repo.

## Hooks

- The hooks in this tree only add context (memory wake, core notes, clock, compaction restore, notification).
  The guards and gates of the live setup are private.
- Tests must exercise the intended failure with positive and negative controls. A test that runs a hook under
  the real `HOME` sets `TELEMETRY_SYNTHETIC=1`.
- The privacy protection at the public boundary is the Privacy Steward's; see [stewards/](../stewards/README.md).

## Skills

- Ruling of 2026-09-04: queue loading only when picking up work, Linear for work needing follow-through,
  independent review according to risk, and continuity saves only when useful. Claude's local settings no
  longer register a session queue summary. Compaction still restores existing saves without a missing-save
  instruction.
- The same day, generic process skills moved to a shelf. The current managed Codex set is in
  `codex/install.sh`; do not restore retired links just because a historical skill references them. Keep
  archived eval tools and rendering assets available for deliberate use.
- `settings.json` is intentionally untracked because it can contain credentials. The 2026-09-04 cut disabled
  sibling narration, context nudges, resource-sizing warnings, lint-on-write, browser-window movement, and
  workspace-wide unpushed warnings. Privacy, continuity and notifications remain configured. Session briefs
  live in the notes tree.
- The broad built-in docs skill of Codex is disabled in the local Codex config; its MCP tools remain
  available. Changing the system skill package is unnecessary. Restart Codex after local config changes.
- A skill description over ~600 characters is dropped wholesale from the ambient listing: the skill stops
  auto-triggering while looking healthy on disk. Budget 200-400 characters.
- Two skills (a desktop-config skill and a crash-diagnosis skill) are symlinks into the desktop package's
  skill directory, owned by the package and mirrored by its migrations into every runtime's skill directory.
  Never edit, shelve, or add them to `codex/install.sh`; `--check` ignores them.
- Atlas skills (ruling of 2026-08-27): the atlas store is curated markdown, hand-edited by the primary only.
  No JSON stores, no patch pipelines.

## Delegation and tooling

- Laptop provider bridges are on demand (2026-10-16): `delegate/ensure-provider-bridge` starts only the
  selected DeepSeek/OpenRouter user service and waits for local health; `ds-codex` calls it before dispatch.
  They are disabled at login and stay shared until explicitly stopped. Do not enable them merely to repair a
  wrapper.
- The Codex layer is symlinks only (ruling of 2026-09-01: thousands of lines managed by one link, a few
  links and one hook). `codex/install.sh` writes them, `--check` audits them; a regular file at a managed path
  is reported and left as found. Editing a hook here changes live Codex behaviour at once.
- Codex keeps a trust entry per hook in its config. After changing a hook command, the operator approves it
  again in the startup TUI; preserve trusted indices.
- `deepseek/CORE-compact.md` serves the DeepSeek dispatch agent, the `~/.agents/CORE.md` symlink, and the
  cached harness prefix. Keep its leading bytes stable: DeepSeek's prefix cache matches exact leading bytes,
  so an edit near the top invalidates it for every dispatch.
- Agent-tier tools in `delegate/` and `scripts/` each keep a symlink at their original `~/.local/bin` path,
  pinned absolutely by systemd units and reference docs; never delete one without editing its caller.
- **Free models**: Free models run only on public inputs, inside a sandbox with no view of the machine, and every quote they return is checked with `quote-check`. Free endpoints log prompts, so public topics and public professionals' names
  only (ruling of 2026-11-03), never private data or vault text. For private inputs and quick lookups use
  `codex-fast --web-search on --oneshot`. Never fall back to a paid model. Details:
  [reference/model-delegation.md](../reference/model-delegation.md).
- A paid search API (ruling of 2026-11-04) serves depth the hosted search lacks, such as pages a plain fetch
  cannot read. Its key lives in the secret store and tools run under the store's runner. Queries leave the
  machine: public topics only, never a private brief or the company's description.
- `eval/skill-activation/run.py`: `--tools` removes tools from the model's view entirely, so denying `Skill`
  that way zeroes fired-detection; it does not cover MCP tools; and the prompt must sit immediately after
  `-p`, before the variadic `--tools`.

## The work system

- One work system (ruling of 2026-10-10): the assistant files tickets for the operator; the work system
  routes them. The **Linear Steward** owns the record (rules in
  [reference/followup-convention.md](../reference/followup-convention.md)) and signs `(linear-steward, date)`.
  The Privacy Steward and the Infrastructure Steward own the public boundary and the health of the machines;
  the Infrastructure Steward takes the label `for:infrastructure` and signs `(infrastructure-steward, date)`.
  The chat agent keeps the operator's chat and files or changes a ticket on their word. The **dispatcher** is
  the one claimer: it starts the work the Linear Steward orders, one fresh worker per ticket. Workers sign
  their milestones and end with one signed outcome. Four things always need the operator's tap on the phone:
  money, messages as the operator, secrets and destruction that cannot be undone. Design: [work/](../work/README.md).
- Linear caps descriptions at 250,000 characters.
- Phone pushes have three channels, split by what the operator must do (2026-10-01): **approve** for a
  waiting tap, **alarm** for something broken, **fyi** for "run finished". A new sender picks a channel by
  that question and reads the topic from its file, never inline.
- Local collaboration: `agent-bridge`, hcom and `connectome-lab` are opt-in launchers; see
  [reference/agent-communication.md](../reference/agent-communication.md). Traps: a piped Connectome run with
  the web UI on never exits (use `--no-webui`); the lab's bun is a local npm package under `.local/` and needs
  `node install.js` after an npm update. `agent-bridge` avoids the existing `/usr/bin/bridge` networking
  command. hcom keeps no hooks in `settings.json` or the Codex `hooks.json`. Do not
  nest bridge and hcom on one session.
- The assistant bridge (2026-09-22): the assistant reads a published copy of the vault, suggests edits and
  files tickets; everything is reviewed before it lands, and the vault stays the source of truth. Labels
  `for:assistant` and `from:assistant` mark tickets for and from the assistant. Design:
  [assistant-bridge/](../assistant-bridge/README.md).

## Reference docs

- The model-delegation reference carries only what `<wrapper> --help` and the contract cannot; the derivable
  parts were cut, because a duplicate goes out of date while the source stays current.
- The server runbook stays private. Verify any deploy path against `pm2 show <name>`
  before trusting a deploy recipe.
