# Setup

Walks you from `git clone` to a working install.

## Prerequisites

Required: `jq`, Python 3.10 or newer (`python3`), and `git`. Without `jq`, the deletion guard falls back to a coarse string check that cannot distinguish `rm -rf ~/project` from `echo "rm -rf"`, so it errs toward stopping you. The pre-push, nested-clone, public-gh, codex-exec, destructive-git, and paid-compute teardown gates cannot parse hook input without `jq` and skip their checks. Optional: `codex` powers the pre-commit review path; `dmux` and `tmux` power pane orchestration; `browser-use` and Playwright MCP power browser automation; `defuddle` powers article extraction. Run `bin/strata-doctor` before or after installation to check what actually resolves.

`strata-init` creates a local Python environment and installs its declared package requirements, so uncached packages need access to a package index.

### Deletion guard

The deletion guard catches accidents and agent slips. It is not a security boundary: any bash string parser is defeated by an interpreter, a script file, or an aliased command, so do not rely on it against an adversary or a compromised agent.

## 1. Clone

```
git clone https://github.com/onblueroses/strata.git ~/.strata
```

You can install anywhere; `~/.strata` is the convention.

## 2. Run strata-init

```
~/.strata/bin/strata-init
```

The init script:

1. Detects your shell (`$SHELL`) and prompts before writing a guarded block to `~/.zshrc`, `~/.bashrc`, or `~/.config/fish/config.fish`. Pass `--non-interactive` to install that shell-correct block without prompting. The block sets `STRATA_HOME`, `KB_DIR`, `STATE_DIR`, `SPECS_DIR` and prepends `$STRATA_HOME/bin` to `PATH`.
2. Symlinks `$HOME/.claude/{skills,commands,agents,hooks,reference}` to `$STRATA_HOME/` (backing up conflicting entries first). This is how Claude Code discovers strata's content at session start.
3. Refreshes `$HOME/.claude/settings.json` and `$HOME/.claude/CLAUDE.md`, backing up changed copies before replacement. It leaves an existing permission mode untouched unless you explicitly enable bypass mode. The permission choices are listed below.
4. Seeds the gitignored `config/private-tokens.txt` from its example when absent and prints the file to edit; reruns never overwrite it.
5. Creates `workspace/state/specs/` and `workspace/state/handoffs/` for compaction-safe specs and session handoffs.
6. Reminds you to fill `config/model-map.toml` with the strongest models you currently have access to (see step 3 of this document).
7. Prints a one-line check command to verify the install: `strong --help && fast --help && grader --help && breadth --help`.

Re-run `strata-init` after `git pull` as the safe upgrade step. It refreshes copied files, leaves current symlinks alone, and reports every unchanged, refreshed, linked, seeded, and backed-up path. Read [MIGRATION.md](MIGRATION.md) before upgrading across a release that removes hooks or commands.

### Permission choices

| Choice | Installed permission behavior | What still asks interactively |
|---|---|---|
| Decline the prompt or use `--non-interactive` | Leaves `defaultMode` unset on a clean install and preserves an existing mode on a rerun. Strata preapproves `Read`, `Grep`, `Glob`, `WebSearch`, `WebFetch`, skills, and exact Bash checks for `git status --short`, `git diff --stat`, `git diff --check`, `git log --oneline`, and `git rev-parse --show-toplevel`. | Other Bash commands, `Write`, `Edit`, `MultiEdit`, and every MCP tool require approval when the preserved mode does not already decide otherwise. |
| Accept the prompt or pass `--enable-bypass-permissions` | Sets `defaultMode` to `bypassPermissions`; tool calls proceed without permission prompts. The explicit deny rules and Strata hooks still apply. | No tool-level permission prompt. |

The prompt controls permission behavior, not whether the safety hooks run. Both paths install the same hooks from `settings.json`.

Source the generated rc file named in the install output, or open a new shell, before continuing.

## 3. Fill in model-map.toml

Open `~/.strata/config/model-map.toml`. Replace each `<PICK_...>` placeholder with a concrete model id you have access to:

```toml
[lanes]
strong   = "<PICK_STRONGEST_AVAILABLE>"    # heaviest reasoning, load-bearing
fast     = "<PICK_FAST_CODE_MODEL>"        # cheap parallel work, code probes
grader   = "<PICK_CHEAP_PARALLEL>"         # bulk filtering, sanity checks
breadth  = "<PICK_NON_PRIMARY>"            # second-opinion lane, codex fallback
```

`CONFIG.md` lists the lane contract each model must satisfy (exit codes, flags, prompt template). Strata stays model-agnostic; you tune the bindings as models churn.

## 4. Point Claude Code at this install

`strata-init` (step 2) refreshes `$HOME/.claude/settings.json`, backing up a changed copy and following the permission choice above. Claude Code reads that file at session start and wires the strata hooks to `$STRATA_HOME/hooks/`.

Open a Claude Code session in any project. Strata's CLAUDE.md, hooks, skills, commands, and reference docs auto-load from `$STRATA_HOME`.

## 5. First spec

Inside a Claude Code session, type:

```
/spec example-feature
```

The skill walks you through recon → plan → spec-on-disk. The spec lives at `$SPECS_DIR/example-feature.md` and survives compaction. Read its `>> Current Step` after any context reset.

## 6. Use the workspace for continuity

`workspace/` holds runtime artifacts that coding agents must recover after context loss:

- `state/specs/` — active implementation specs with `>> Current Step` and recorded decisions
- `state/handoffs/` — explicit notes for work that continues in another session

The compaction hooks also write session-keyed pointer maps under `$STATE_DIR`. Claude Code supplies native project memory; Strata does not maintain a second memory store. See `reference/knowledge-management.md` for a compact note discipline that works with the native feature.

## 7. Read the doctrine

`CLAUDE.md` at the install root is the operating doctrine the agent reads first every session. Skim it once. It covers orchestrator delegation, file-backed continuity, harness composition, and privacy.

## 8. (Optional) Enable telemetry

Telemetry is **off by default** and wired nowhere in `settings.json`. To opt in, export one env var (e.g. in your rc block):

```
export STRATA_TELEMETRY=1
```

When enabled, lane dispatches (`bin/strong` and siblings) append one enveloped JSONL event per call. The runtime sink lives under `$STATE_DIR/telemetry`, never the tracked tree. `telemetry/` ships only the scripts: `telemetry-emit.sh` (emitter), `unify.py` (read-time merger, refuses to export raw event text to a tracked path), `rotate_telemetry.sh` (size rotation), `cost_rollup.py` (cost ledger over `model_rates.json`). Fill `telemetry/model_rates.json` with your own per-model rates to get cost rollups. Full event spec: `telemetry/README.md`.
