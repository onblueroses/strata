<!-- keywords: review fan-out, specialist review, bucket categorization, parallel review panel, sequential fallback, large diff review, grader lane, breadth lane, deduplicate findings -->
# /review Fan-Out

Read this protocol when `/review` Step 1b sees at least 10 changed files or at least 500 changed lines. Smaller diffs stay on the single-reviewer path.

## Quick Nav

| Need | Section |
|------|---------|
| Assign every changed file once | [Bucket categorization](#bucket-categorization) |
| Choose and run specialist passes | [Specialist reviewers](#specialist-reviewers) |
| Keep each review prompt consistent | [Specialist prompt template](#specialist-prompt-template) |
| Reconcile overlapping findings | [Deduplicate and merge](#deduplicate-and-merge) |
| Verify the fan-out was complete | [Fan-out self-check](#fan-out-self-check) |

## Bucket categorization

Categorize every changed file into one of six buckets. Apply the first matching bucket because order carries precedence.

| Priority | Bucket | Path patterns |
|----------|--------|--------------|
| 1 | test | `*.test.*`, `*.spec.*`, `__tests__/**`, `test/**`, `tests/**`, `*_test.go`, `*_test.rs` |
| 2 | deps | `package.json`, `package-lock.json`, `yarn.lock`, `pnpm-lock.yaml`, `Cargo.toml`, `Cargo.lock`, `go.mod`, `go.sum`, `requirements.txt`, `pyproject.toml`, `composer.json`, `Gemfile*` |
| 3 | config | `.env*`, `*.config.*`, `tsconfig*`, `.eslintrc*`, `.prettierrc*`, `Dockerfile*`, `docker-compose*`, `.github/**`, `.gitignore`, `*.yaml` outside `docs/`, `*.yml` outside `docs/` |
| 4 | docs | `*.md`, `*.mdx`, `docs/**`, `LICENSE*`, `CHANGELOG*`, root `*.txt` |
| 5 | api | `**/api/**`, `**/routes/**`, `**/endpoints/**`, `**/handler*.*`, `**/middleware/**`, `**/controllers/**` |
| 6 | code | Everything else |

Store the result as `{bucket: [filepath, ...]}`.

## Specialist reviewers

Use the configured `grader` lane for bucket specialists and keep the independent whole-diff `breadth` pass from `/review` Step 1a. Each specialist receives one non-empty bucket and the same frozen diff revision.

| Bucket | Specialist perspective | Focus |
|--------|------------------------|-------|
| code | Logic reviewer | Correctness, edge cases, type safety, dead code |
| api | API contract reviewer | Breaking changes, authorization gaps, input validation, error responses |
| docs | Documentation reviewer | Accuracy against code, stale references, broken links |
| config | Configuration reviewer | Secrets, environment consistency, missing defaults |
| deps | Dependency reviewer | Version conflicts, licenses, unused dependencies, lockfile consistency |
| test | Test reviewer | Coverage gaps, flaky patterns, assertion quality, missing edge cases |

### Parallel execution

When the host provides a parallel Workflow or review-panel primitive, dispatch one specialist per non-empty bucket before reading any specialist result. Run the ordinary Steps 2-4d concurrently, then collect every specialist result and merge once.

### Sequential fallback

When parallel dispatch is unavailable, run the same specialist prompts sequentially in bucket-priority order. Keep the diff, constraints, lane, and prompts frozen across passes; collect each response without revising the code between specialists. Merge only after the final bucket completes. This fallback changes latency, not review coverage or output semantics.

## Specialist prompt template

```text
Goal: Review {N} files in the "{bucket}" category of a {total_files}-file diff from the {focus} perspective.

Success means:
  - Read the project constraints and every provided file.
  - Report every concrete finding with file, line, failure mode, and fix direction.
  - Use one severity from: CRITICAL, HIGH, MEDIUM, LOW.
  - Return one finding per line in the required format.
  - Return an empty response when the bucket contains no findings.

Stop when: Every provided file has been reviewed and the response contains every supported finding.

PROJECT CONSTRAINTS:
{constraints}

FILES TO REVIEW:
{file_list_with_full_content}

PUBLIC_REPO: {true|false}

Required format:
[SEVERITY] file:line - failure mode; fix direction

Severity mapping:
CRITICAL = security/data loss
HIGH = correctness/breaking
MEDIUM = quality
LOW = style/minor

Trace each issue through the changed code before reporting it.
```

## Deduplicate and merge

Deduplicate findings with `${file}:${line}:${description_normalized}`. When findings share a file and line and describe the same failure, keep the higher severity. Sort the merged list by severity (CRITICAL first), then file path.

When a specialist returns more than 20 findings, retain the 10 highest-severity findings and append `[N additional LOW/MEDIUM findings omitted]`.

Steps 4 and 4a-4d still run in fan-out mode and merge with specialist output. The independent `breadth` pass always reviews the whole diff.

## Fan-out self-check

1. Apply the threshold at `>= 10` files or `>= 500` changed lines.
2. Assign every changed file to exactly one bucket.
3. Dispatch every eligible parallel pass before reading results, or complete the documented sequential fallback.
4. Deduplicate by file, line, and normalized description.
5. Cap noisy specialist output at the 10 highest-severity findings.
