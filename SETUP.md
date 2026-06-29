# Setup

Walks you from `git clone` to a working install.

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

1. Detects your shell (`$SHELL`), prompts before writing a guarded block to `~/.zshrc` or `~/.bashrc`. The block sets `STRATA_HOME`, `KB_DIR`, `STATE_DIR`, `SPECS_DIR` and prepends `$STRATA_HOME/bin` to `PATH`.
2. Symlinks `$HOME/.claude/{skills,commands,agents,hooks,reference}` to `$STRATA_HOME/` (backing up any existing entries first). This is how Claude Code discovers strata's content at session start.
3. Installs `$STRATA_HOME/settings.json` into `$HOME/.claude/settings.json` (backup + overwrite). Wires the Stop/PreToolUse/PostToolUse hooks to `$STRATA_HOME/hooks/`.
4. Populates `workspace/` with PARA-flavored seed templates: `areas/`, `projects/`, `resources/`, `daily/`, `inbox/`, `archives/`. Each directory ships a README explaining the pattern; entity directories include a `summary.md` schema and an `items.json` example. This is the substrate your agent reads, writes, and grows over time.
5. Prompts you to fill `config/model-map.toml` with the strongest models you currently have access to (see step 3 of this document).
6. Prints a one-line check command to verify the install: `strong --help && fast --help && grader --help && breadth --help`.

Source the new rc block (`source ~/.zshrc` or open a new shell) before continuing.

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

`strata-init` (step 2) installs `$STRATA_HOME/settings.json` into `$HOME/.claude/settings.json` (backing up any existing file first). Claude Code reads that file at session start and wires the strata hooks to `$STRATA_HOME/hooks/`. If you declined the install during step 2, copy or merge `$STRATA_HOME/settings.json` into `$HOME/.claude/settings.json` (or `<project>/.claude/settings.json`) yourself.

Open a Claude Code session in any project. Strata's CLAUDE.md, hooks, skills, commands, and reference docs auto-load from `$STRATA_HOME`.

## 5. First spec

Inside a Claude Code session, type:

```
/spec example-feature
```

The skill walks you through recon → plan → spec-on-disk. The spec lives at `$SPECS_DIR/example-feature.md` and survives compaction. Read its `>> Current Step` after any context reset.

## 6. Build your knowledge base

`workspace/` is where your operating context accumulates. As you work, the agent reads and writes:

- `areas/` — ongoing responsibilities you maintain over time
- `projects/<entity>/summary.md` — architecture, recent sessions, gotchas per project
- `resources/` — reusable references not tied to a project
- `daily/` — session journals named `YYYY-MM-DD-<slug>-<session-id>.json`
- `inbox/` — unsorted captures
- `archives/` — deprecated entities you've stopped touching

The `summary.md` + `items.json` per entity is the pattern. Skills like `/pickup`, `/end`, and `knowledge-lookup` read and write this tree. Over time it becomes the persistent memory the orchestrator dispatches off.

## 7. Read the doctrine

`CLAUDE.md` at the install root is the operating doctrine the agent reads first every session. Skim it once. The patterns it encodes (orchestrator delegation, gated completion, harness-as-composition, privacy as the immovable rail) are the working OS.

## 8. (Optional) Enable telemetry

Telemetry is **off by default** and wired nowhere in `settings.json`. To opt in, export one env var (e.g. in your rc block):

```
export STRATA_TELEMETRY=1
```

When enabled, lane dispatches (`bin/strong` and siblings) append one enveloped JSONL event per call, and the runtime sink lives under `$STATE_DIR/telemetry` — never the tracked tree. `telemetry/` ships only the scripts: `telemetry-emit.sh` (emitter), `unify.py` (read-time merger, refuses to export raw event text to a tracked path), `rotate_telemetry.sh` (size rotation), `cost_rollup.py` (cost ledger over `model_rates.json`). Fill `telemetry/model_rates.json` with your own per-model rates to get cost rollups. Full event spec: `telemetry/README.md`.
