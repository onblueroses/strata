---
name: to-issues
description: "Break a PRD, plan, or spec into independently-grabbable GitHub issues using tracer-bullet vertical slices, with a draft-and-approve gate before any issue is published. Each slice cuts end-to-end through every layer (schema, API, UI, tests) so it is demoable on its own, and the breakdown is walked with the user before anything reaches `gh`. Positioned downstream of /to-prd as the product-work alternative to /spec: /spec persists internal multi-phase implementation state on disk, /to-issues externalizes the work as grabbable tracker tickets for AFK agents or collaborators. Manual: /to-issues [issue-ref-or-path], or when a PRD/plan/spec is ready to fan out into a tracked issue set rather than an in-session spec."
disable-model-invocation: true
---

# To Issues

Break a PRD, plan, or spec into independently-grabbable GitHub issues using vertical slices (tracer bullets), then draft-and-approve every issue before it reaches the tracker.

```
Goal: Turn a plan into a dependency-ordered set of tracer-bullet GitHub issues,
      each demoable on its own, each approved by you before it is published.

Success means:
  - The breakdown is a set of thin vertical slices (each cuts through every layer)
  - You approved the granularity and the dependency graph
  - You saw the full body of every issue and approved it before any `gh issue create`
  - Issues were published in dependency order with real identifiers in "Blocked by"

Stop when: every approved slice exists as a real issue, or you paused the publish step.
```

## Where this sits

Run /to-issues when product work is ready to become tracked, grabbable tickets rather than an in-session implementation plan.

- **Downstream of /to-prd**: a PRD is the natural input. Pass the PRD path or paste it; this skill slices it into issues.
- **Alternative to /spec**: /spec writes one on-disk artifact that holds both the plan and the execution state, tuned for a single session that survives compaction. /to-issues externalizes the work as a set of GitHub issues that anyone (or an AFK agent) can grab independently. Reach for /to-issues when the work is fan-out product work with multiple grabbers; reach for /spec when it is one focused multi-phase build you will execute yourself.

When the work is small (1-2 files, obvious path), skip both: just do it.

## Tracker convention

This skill prepares GitHub issues for publication via the `gh` CLI; the repo's GitHub Issues is the tracker. Keep the convention thin:

- Run `gh repo view --json nameWithOwner` to confirm which repo the issues land in; confirm with the user when the working directory is ambiguous or maps to no remote.
- Triage label: GitHub repos rarely ship a fixed "ready for AFK agents" label. Read existing labels with `gh label list`. When a ready-state label exists (e.g. `ready`, `good first issue`, `agent-ready`), include it. When none exists, omit the label and tell the user which label, if any, they want created. Skip inventing labels unprompted.
- Reference issues by their real number once created, so "Blocked by" fields point at live identifiers.

## Process

### 1. Gather context

Work from whatever is already in the conversation. When the user passes an issue reference (number, URL, or path) as an argument, fetch it: `gh issue view <n> --json title,body,comments` for a tracker issue, or Read the file for a path. Read the full body and any comments before slicing.

### 2. Explore the codebase (optional)

When the codebase is not already loaded, explore it to ground the slices in current state. Issue titles and descriptions use the project's domain vocabulary and respect any ADRs in the area you are touching (Glob for `**/ADR*.md`, `**/decisions/**/*.md`, `**/CONTEXT.md`). Look for prefactoring that makes the implementation easier: make the change easy, then make the easy change.

For an unfamiliar surface, run /recon first and feed the brief into the slicing.

### 3. Draft vertical slices

Break the plan into tracer-bullet issues. Each issue is a thin vertical slice cutting through every integration layer end-to-end, not a horizontal slice of one layer.

<vertical-slice-rules>

- Each slice delivers a narrow but complete path through every layer (schema, API, UI, tests).
- A completed slice is demoable or verifiable on its own.
- Any prefactoring lands first, as its own slice.

</vertical-slice-rules>

### 4. Walk the breakdown with the user

Present the proposed breakdown as a numbered list. For each slice, show:

- **Title**: short descriptive name
- **Blocked by**: which other slices (if any) complete first
- **User stories covered**: which user stories this addresses (when the source has them)

Ask the user, via AskUserQuestion (load /ask-better and the Confidence Check first):

- Does the granularity feel right (too coarse / too fine)?
- Are the dependency relationships correct?
- Should any slices merge or split further?

Iterate until the user approves the breakdown shape.

### 5. Draft and approve each issue body

Before any `gh issue create`, draft the full body of every issue using the template below and show the user the complete text. Get explicit approval first. This is the cooperative gate, and it is load-bearing for two reasons:

1. **The no-public-posts discipline**: GitHub issues are published artifacts; show the draft and get explicit say-off before anything goes live.
2. **The `gate-gh-public-actions.sh` hook blocks `gh issue create` from the Bash tool**: the hook denies public GitHub writes and reminds you to show the exact content before publication. Drafting first supplies the approved content for the manual command the user runs outside the agent.

Show all issue bodies in dependency order, let the user edit or reject any of them, and treat their explicit "approved" / "go" as the gate. Carry their edits into the published text verbatim.

### 6. Publish the approved issues

For each approved slice, prepare the exact `gh issue create --title "<title>" --body "<body>"` command for the user to run manually outside the agent's Bash tool (add `--label <label>` only when the Tracker convention's label decision said to). The repo hook blocks `gh issue create` from Bash, so the actionable handoff is the approved command text and issue body. Order the commands by dependency (blockers first) so each "Blocked by" field can reference the real issue number of an already-created blocker.

Leave any parent issue untouched: do not close or modify it.

<issue-template>
## Parent

A reference to the parent issue (when the source was an existing tracker issue; omit this section otherwise).

## What to build

A concise description of this vertical slice. Describe the end-to-end behavior, not layer-by-layer implementation.

Skip specific file paths or code snippets; they go stale fast. Exception: when a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it and note briefly that it came from a prototype. Trim to the decision-rich parts.

## Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2
- [ ] Criterion 3

## Blocked by

- A reference to the blocking issue (when any), e.g. `#42`

Or "None - can start immediately" when there are no blockers.

</issue-template>

## Handoff

After the user publishes the issues, return the list of created issue numbers and their titles so the user can see the fan-out at a glance. The issues are the deliverable; implementation happens elsewhere, grabbed slice by slice.
