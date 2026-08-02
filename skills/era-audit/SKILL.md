---
name: era-audit
description: "Audit coding-agent instruction libraries for model-era rot by probing live ground truth, freezing the corpus, and producing quote-verifiable findings. Auto-trigger when reviewing skills, commands, rules, AGENTS.md, CLAUDE.md, or agent prompts for stale model assumptions, obsolete workarounds, dead tooling, retired routers, old delegation shapes, small-context rituals, or outdated self-check scaffolding."
---

# Era Audit

Goal: Find instructions that encode what an earlier reader or toolchain needed and that conflict with the install that reads them now.

Success means:

- Probe machine-visible facts and preserve inaccessible facts as `unknown` until the operator declares them with evidence.
- Freeze the exact instruction corpus before semantic review.
- Give every file a disposition.
- Give every finding a verbatim quote, category, present-ground-truth failure mode, and concrete fix direction.
- Validate the final JSON against `findings.schema.json` and validate every quote against the frozen source.
- Re-derive cross-cutting patterns from the local findings.

Does not count:

- Applying a fixed word list or the dated pattern prior as truth.
- Calling an instruction stale because it is long, strict, numerical, or unfamiliar.
- Inferring a capability from an installed binary or inferring absence from an inaccessible tool surface.
- Copying the dated example into a live ground-truth file without re-probing.

Stop when: the frozen corpus has one disposition per file, all findings validate, local patterns are synthesized, and the chosen remediation gate is recorded.

Verify by: run the schema and quote validator, render sampled file briefs, compare current file hashes with the frozen manifest, and report any drift.

Runtime requirement: Python 3.10 or newer, because the scripts use modern union type syntax. The shipped validator uses only the standard library and checks the schema vocabulary present in the shipped schemas.

## Build current ground truth

Run the probe from the library root:

```bash
python3 <skill-dir>/scripts/probe_ground_truth.py \
  --root . \
  --output <run-dir>/ground-truth.probed.json
```

The probe observes the platform, every executable name that resolves on `PATH`, lane bindings in `config/model-map.toml`, and wrapper presence. It leaves reader behavior, in-process agent tools, house standards, retired systems, and incident history unknown.

For a public snapshot, repeat `--cli-tool <name>` for executables referenced by the audited corpus. This keeps machine inventory focused while recording both resolved and missing tools. Omit the option when a complete local `PATH` inventory is appropriate.

Inspect MCP health only with a timeout chosen from this install's observed command latency:

```bash
python3 <skill-dir>/scripts/probe_ground_truth.py \
  --root . \
  --active-timeout-seconds <operator-chosen-seconds> \
  --output <run-dir>/ground-truth.probed.json
```

Copy `ground-truth.template.json` to an answers file. Fill the unknown facts that matter to this library. Give each declaration a value and evidence. Leave the rest unknown. Then merge declarations into a fresh probe:

```bash
python3 <skill-dir>/scripts/probe_ground_truth.py \
  --root . \
  --answers <run-dir>/ground-truth.answers.json \
  --active-timeout-seconds <operator-chosen-seconds> \
  --output <run-dir>/ground-truth.json
```

Declare `runtime_capabilities` from the tools presented to the running agent. A subprocess cannot discover that surface. Treat CLI presence and agent capability as separate facts.

Read `examples/ground-truth-2026-07-30.example.json` only as a worked snapshot from one install on that date. Its facts are not defaults.

## Freeze and audit the corpus

Measure the library before choosing batching and concurrency:

```bash
python3 <skill-dir>/scripts/measure_library.py \
  --root . \
  --output <run-dir>/metrics.json
```

Choose `batch-count` from the measured corpus size and the reader's verified context capacity. Choose `jobs` from the provider's documented or measured concurrency. Record both bases. When either capacity is unknown, run a reversible pilot and measure before expanding.

Create `<run-dir>` outside the audited library. It contains full source copies, ground truth, prompts, raw runner logs, and results, so treat it as private working state. `prepare` rejects an in-tree run directory and writes owner-only files. Review every artifact before publishing it; only the deliberately redacted final export belongs in a public repository.

Prepare hash-bound prompts. The default corpus includes model-facing root files, commands, agents, YAML agent metadata, skill bodies, root and skill rule files, and operational skill references. Symlinked instruction files are rejected. Add `--include` or `--exclude` when the runtime injects a different set.

```bash
python3 <skill-dir>/scripts/era_audit.py prepare \
  --root . \
  --ground-truth <run-dir>/ground-truth.json \
  --pattern-prior <skill-dir>/references/pattern-prior-2026-07-30.md \
  --batch-count <chosen-count> \
  --batch-basis <measurement-or-named-requirement> \
  --run-dir <run-dir>
```

Run with the tested Codex backend. Omit `--model` to use the install's live default; pass it only when the operator chose and verified a specific reader.

```bash
python3 <skill-dir>/scripts/era_audit.py run \
  --root . \
  --run-dir <run-dir> \
  --runner codex \
  --jobs <chosen-concurrency> \
  --jobs-basis <measurement-or-provider-limit> \
  --runner-timeout-seconds <measured-deadline> \
  --runner-timeout-basis <measurement-or-named-requirement>
```

For another backend, pass `--runner custom` and an argv template through `--runner-command`. Supported placeholders are `{root}`, `{prompt_path}`, `{output_path}`, and `{schema_path}`. The command runs without a shell and receives the full prompt on stdin.

Merge only after every batch succeeds:

```bash
python3 <skill-dir>/scripts/era_audit.py merge \
  --run-dir <run-dir> \
  --root-label <public-library-name> \
  --ground-truth-label <public-ground-truth-path> \
  --pattern-candidates-output <run-dir>/pattern-candidates.json \
  --output <run-dir>/findings.json
```

## Enforce the finding contract

Use these categories:

- `hand-holding`: micro-scripting work the current reader completes directly.
- `small-context`: retention, truncation, or staged-reading rituals sized to an earlier context limit.
- `distrust-scaffolding`: emphasis, repetition, or self-attestation compensating for an earlier error rate.
- `stale-facts`: dead tools, paths, flags, models, platforms, stores, or ecosystem claims.
- `old-delegation`: orchestration shaped around retired or missing dispatch capabilities.
- `obsolete-workaround`: a workaround whose protected failure mode no longer exists.
- `register-miscalibration`: explanations or scripts aimed below the current reader's demonstrated judgment.

Use these dispositions:

- `REWRITE`: stale assumptions are load-bearing.
- `MODERNIZE`: the core is sound and several sections need targeted change.
- `TOUCH-UP`: a small number of lines need change.
- `CURRENT`: no checkable stale prior was found.

Validate the merged artifact against the frozen manifest:

```bash
python3 <skill-dir>/scripts/validate_findings.py \
  --schema <skill-dir>/findings.schema.json \
  --findings <run-dir>/findings.json \
  --manifest <run-dir>/manifest.json \
  --root .
```

For a published example whose audited files are still present at their recorded hashes, omit `--manifest` and pass `--root`. Full mode reconstructs source content from the artifact's corpus metadata, verifies every current hash, loads the adjacent ground-truth file named by the artifact, and checks the quotes. When neither matching sources nor a frozen manifest are available, use `--schema-only`; that mode says nothing about quote provenance and never prints `quotes=verbatim`.

Render an editor brief:

```bash
python3 <skill-dir>/scripts/brief.py \
  --findings <run-dir>/findings.json \
  path/to/instruction.md
```

## Re-derive local patterns

Read `references/pattern-prior-2026-07-30.md` after quote validation. Cluster the local findings by shared mechanism, not shared word. Retain a prior pattern only when the local findings independently support it. Drop unsupported patterns and name new ones. Record the measured file and finding counts behind each local pattern in the run report.

## Remediate with independent defenses

Read `references/remediation.md` before applying findings. Preserve three separate roles:

- A fixer applies or rejects each requested finding.
- An independent verifier that did not write the fix checks completeness, current facts, and operational integrity.
- A collateral critic asks only what the edit removed that no finding requested.

Verify every review claim against the live machine or authoritative file before repairing it. A reviewer can be wrong. Stop on the declared ship gate; do not iterate toward zero findings.

The run report is the finalization artifact. It records the synthesized local patterns with supporting files and finding counts, the chosen remediation gate and its basis, ranked findings, unknowns, and deferrals. The merge output's batch-local pattern candidates are leads for this synthesis, not accepted patterns.

## Report provenance

Report the ground-truth observation time, frozen corpus time, Git commit and dirty state when available, include and exclude patterns, file count, byte count, line count, runner, chosen batching and concurrency bases, unknown ground-truth fields, validation result, and current-tree drift. Separate observed facts from declarations and unknowns.
