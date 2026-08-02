# Dated pattern prior: 2026-07-30

This starting prior was derived on 2026-07-30 from 272 findings across 69 instruction files in one install. It is not ground truth, a ruleset, or a lexical detector. Re-derive patterns from your validated findings before trusting any item below.

## How to use this prior

1. Audit against live ground truth and exact quotes.
2. Cluster validated findings by the mechanism that makes each instruction stale.
3. Record the measured files and findings supporting every local cluster.
4. Keep prior patterns only when local evidence independently reproduces them.
5. Add local patterns this list missed and drop patterns your corpus does not support.

## Starting attention patterns

1. **Collapsed model-facing bodies.** Markup intended to save human reading space can add tokens without changing what the model loads. Verify the runtime's loading behavior before changing it.
2. **Activation text addressed to a retired router.** Body trigger lists and routing keys can outlive the mechanism that once read them. Trace the current activation surface.
3. **Dead instruction graphs.** Pairings, related skills, commands, and reference paths can point at moved, shelved, renamed, or absent targets. Resolve every edge.
4. **Fixed quotas and fabricated precision.** Enumeration counts, sentence rations, time budgets, retry ladders, and thresholds can encode an old resource limit. Keep a scalar only with its current basis.
5. **Self-attestation and compliance restatement.** Repeated warnings and "did you really do it" checks can compensate for an earlier reader's error rate. Preserve checks that still decide an external fact.
6. **Converge-to-zero review loops.** An emptiness gate can persist after the organization adopts a bounded ship gate. Find the current stopping policy.
7. **Persona and permission preambles.** Identity costumes or permission incantations can survive after direct outcome and register instructions work better. Preserve behavioral content.
8. **Dead tooling, paths, flags, and platforms.** Operational instructions decay with binaries, hosts, storage, wrappers, operating systems, and CLI surfaces. Test them.
9. **Mechanism stories and borrowed statistics.** Claims about model internals or another generator's measured habits can be applied to a reader they never measured. Separate analogy from evidence.
10. **Frozen measurements presented as standing facts.** Counts and ratios from a growing or changing system can teach the reader to accept an anomalous result. Measure at run time or date the snapshot.
11. **Hand-built orchestration after native fan-out arrives.** Manual waves, sentinels, and blanket delegation bans can outlive the harness limitation that required them. Confirm current orchestration tools and limits.
12. **Redundant observability sinks.** Hand-written ledgers can remain after native telemetry becomes authoritative. Trace both writers and consumers before removing one.
13. **Foreground dispatch with inherited timeouts.** Blocking calls and fixed caps can truncate work after resumable or background execution exists. Check the current runner contract.
14. **Small-window reading rituals.** Retain-for-later notes, shallow-first passes, byte gates, and line slices can hide relevant context after the reader's capacity changes. State owed coverage instead.
15. **Scripted questions and dictated speech.** Fixed menus and verbatim phrases can replace current judgment and context use. Preserve the disclosure or decision obligation.
16. **Mechanical truncation under a hard budget.** Character-peeling procedures can produce worse artifacts than composition plus validation. Keep the real bound and validator.
17. **Examples pitched below the reader.** Repeated good/bad pairs and long demonstrations can anchor content after the criterion itself is sufficient. Keep examples that still calibrate form or teach non-obvious domain craft.
