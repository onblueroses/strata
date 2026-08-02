# strata

Strata is a skeleton for coding agents. Skills, hooks, commands, references; one CLAUDE.md as the spine. Harness is the composition primitive: cross-model adversarial generate-evaluate against frozen artifacts. The agent dispatches the thinking; you keep the synthesis.

## Layout

```
bin/        symbolic model lanes (strong | fast | grader | breadth) + dispatch + init
skills/     procedural knowledge the agent loads on demand (spec, recon, harness, ...)
commands/   user-invoked slash commands (verify, review, end, best-of-n, commit)
agents/     subagent definitions (orchestrator, planner, quick-research, code-reviewer)
hooks/      event-driven scripts (PreToolUse, PostToolUse, SessionStart, ...)
reference/  long-form docs with a complete INDEX and per-doc Quick Navs
config/     model-map.toml (symbolic-lane bindings) + private-tokens.example.txt
telemetry/  opt-in delegation/cost telemetry (off by default; STRATA_TELEMETRY=1)
workspace/  runtime continuity (state/specs | state/handoffs)
```

CLAUDE.md at the repo root is the operating doctrine the agent reads first.

Reference docs use a pull model: the complete [reference index](reference/INDEX.md) lists every shipped doc, each doc carries a Quick Nav, and the agent's own intelligence decides what to read on demand.

## Install

```
git clone https://github.com/onblueroses/strata.git ~/.strata
~/.strata/bin/strata-init
```

`strata-init` writes a shell-rc block, creates the runtime workspace, and prompts you to fill `config/model-map.toml` with the strongest models you currently have access to. See [SETUP.md](SETUP.md) for the walkthrough and [MIGRATION.md](MIGRATION.md) after upgrading an existing install.

## Operating model

- **Delegate.** The orchestrator session dispatches code, reviews, and probes to lane wrappers (`bin/strong`, `bin/fast`, `bin/grader`, `bin/breadth`). Your context stays free for synthesis.
- **Persist to files.** Specs at `workspace/state/specs/` survive context compaction. Sessions resume from `>> Current Step`; handoffs and post-compaction pointer maps carry the rest.
- **Session-aware.** Edit receipts and compaction pointers use `$CLAUDE_SESSION_ID`; specs record ownership so concurrent sessions can detect overlap.
- **Harness for hard problems.** `/harness` generates N candidates, grades against a frozen rubric, iterates until aggregate PASS. `/best-of-n` runs the same shape for design-space questions.
- **Telemetry is opt-in.** Lane dispatches and session metrics emit nothing unless you `export STRATA_TELEMETRY=1`. When enabled, enveloped JSONL lands under `$STATE_DIR/telemetry` (never the tracked tree); `telemetry/` ships only the scripts. See [telemetry/README.md](telemetry/README.md).

## Skeleton, not config bundle

Strata ships the substrate, not a curated set of domain packs. Project-specific skills, vendor automations, and personal references live in separate repos. Adapt the kernel; bring your own packs.

## License

MIT

## Attributions

A few writing-craft skills under `skills/` are adapted from [Wondermonger-daydreaming/claude-skills-library](https://github.com/Wondermonger-daydreaming/claude-skills-library) (MIT).
