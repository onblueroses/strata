# Session-Type Conditional Blocks

Use one or two templates that match the classified session type. Copy them into the save file and replace every placeholder with current session state.

## If debugging

```markdown
## Debug State
**Symptom:** [observable behavior]
**Reproducer:** [exact steps or command]
**Hypothesis tree:**
  - [H1] [hypothesis]; status: [confirmed/rejected/untested]; evidence: [...]
  - [H2] ...
**Currently testing:** [H#]
**Smallest failing case:** [minimal reproducer, if isolated]
```

## If implementing

```markdown
## Implementation State
**Spec phase:** [phase name and step number]
**Code shape so far:** [one to three sentences on the structure being built]
**Wired up:** [components connected and working]
**Stubbed:** [placeholders awaiting implementation]
**Tests written / passing:** [counts and what they cover]
```

## If exploring

```markdown
## Exploration State
**Question:** [the open question driving the exploration]
**Surveyed:** [paths, sources, and key findings reviewed]
**Candidate approaches:**
  - [A1]: pros / cons
  - [A2] ...
**Leaning toward:** [Ax] because [why]
**Open sub-questions:** [what remains unresolved]
```

## If writing

```markdown
## Writing State
**Piece:** [title / file path]
**Register / voice notes:** [tone, audience, and defining style]
**Last revision delta:** [what changed in the last pass]
**Open craft questions:** [sentences or sections still being refined and why]
**Reference texts:** [exemplars or sources to keep in view]
```

## If experimenting (ML / data)

```markdown
## Experiment State
**Setup:** [system / dataset / pipeline in one sentence]
**Parameters in play:** [key controls and current values]
**Last run:** [configuration and headline metric]
**Comparison table so far:**
| Run | Configuration diff | Metric | Notes |
|-----|--------------------|--------|-------|
**Next configuration to try:** [parameters and why]
**Compute notes:** [resource topology, bottleneck/utilization, budget remaining, teardown deadline]
```

## If dispatching

```markdown
## Dispatch State
**Outstanding dispatches:**
| Lane / worker | Task | Started | Where output lands |
|---------------|------|---------|--------------------|
**Completed dispatches awaiting integration:**
| Lane / worker | Result summary | Action needed |
|---------------|----------------|---------------|
**On resume:** check [paths or commands] for outputs before continuing.
```
