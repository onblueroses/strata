# strata

Strata is a skeleton for coding agents. Skills, hooks, commands, references; one CLAUDE.md as the spine. Harness is the composition primitive: cross-model adversarial generate-evaluate against frozen artifacts. The agent dispatches the thinking; you keep the synthesis.

## Layout

```
bin/        symbolic model lanes (strong | fast | grader | breadth) + dispatch + init
skills/     procedural knowledge the agent loads on demand (spec, recon, harness, ...)
commands/   user-invoked slash commands (verify, review, end, best-of-n, commit, pickup)
agents/     subagent definitions (orchestrator, planner, quick-research, code-reviewer, knowledge-lookup)
hooks/      event-driven scripts (Stop, PreToolUse, PostToolUse, SessionStart, ...)
reference/  long-form docs with a complete INDEX and per-doc Quick Navs
config/     model-map.toml (symbolic-lane bindings) + private-tokens.example.txt
telemetry/  opt-in delegation/cost telemetry (off by default; STRATA_TELEMETRY=1)
workspace/  PARA-flavored knowledge-base tree (areas | projects | resources | daily | inbox | archives)
```

CLAUDE.md at the repo root is the operating doctrine the agent reads first.

Reference docs use a pull model: the complete [reference index](reference/INDEX.md) lists every shipped doc, each doc carries a Quick Nav, and the agent's own intelligence decides what to read on demand.

## Install

```
git clone https://github.com/onblueroses/strata.git ~/.strata
~/.strata/bin/strata-init
```

`strata-init` writes a shell-rc block, populates the workspace tree, and prompts you to fill `config/model-map.toml` with the strongest models you currently have access to. See [SETUP.md](SETUP.md) for the walkthrough.

## Operating model

- **Delegate.** The orchestrator session dispatches code, reviews, and probes to lane wrappers (`bin/strong`, `bin/fast`, `bin/grader`, `bin/breadth`). Your context stays free for synthesis.
- **Gate completion.** The Stop hook enforces that `/verify` passes before the session can end on any tier above Skip. Run `/verify` after editing files; the hook blocks session close otherwise. Knowledge-base markdown auto-passes; code edits run inline or Codex checks.
- **Persist to files.** Specs at `workspace/state/specs/` survive context compaction. Sessions resume by reading `>> Current Step`.
- **Parallel-safe.** Every state file is session-id-keyed (`$CLAUDE_SESSION_ID`); concurrent sessions never clobber each other.
- **Harness for hard problems.** `/harness` generates N candidates, grades against a frozen rubric, iterates until aggregate PASS. `/best-of-n` runs the same shape for design-space questions.
- **Telemetry is opt-in.** Lane dispatches and session metrics emit nothing unless you `export STRATA_TELEMETRY=1`. When enabled, enveloped JSONL lands under `$STATE_DIR/telemetry` (never the tracked tree); `telemetry/` ships only the scripts. See [telemetry/README.md](telemetry/README.md).

## Skeleton, not config bundle

Strata ships the substrate, not a curated set of domain packs. Project-specific skills, vendor automations, and personal references live in separate repos. Adapt the kernel; bring your own packs.

## License

MIT

## Attributions

A few writing-craft skills under `skills/` are adapted from [Wondermonger-daydreaming/claude-skills-library](https://github.com/Wondermonger-daydreaming/claude-skills-library) (MIT).
