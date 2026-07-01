---
name: setup-pre-commit
disable-model-invocation: true
description: "One-shot bootstrap of a Husky pre-commit gate for a JavaScript/TypeScript repo: lint-staged + Prettier on staged files, plus a full-project typecheck and test run on every commit. Scoped to JS/TS package.json repos only; leave Rust (cargo) and Python repos alone. An edit-time format/lint hook (if your harness runs one) already owns format/lint on individual writes; this skill's value-add is the whole-project typecheck + test gate that a per-file hook cannot provide. Manual: invoke /setup-pre-commit inside a JS/TS repo that has package.json and lacks a working pre-commit gate, when the user wants commit-time typecheck/test enforcement on top of edit-time linting."
---

# Setup Pre-Commit Hooks (JS/TS)

Bootstrap a commit-time gate for one JavaScript/TypeScript repository in a single pass.

```
Goal: Install a working Husky pre-commit gate in the current JS/TS repo — lint-staged + Prettier
      on staged files, then a full-project typecheck and test run.

Success means:
  - The repo has package.json and a detected package manager (npm/pnpm/yarn/bun)
  - .husky/pre-commit contains and runs lint-staged, then typecheck, then test
  - .lintstagedrc, a Prettier config, and the `prepare: "husky"` script all exist
  - the hook body is verified for all three stages before `./.husky/pre-commit` or the exact hook commands run clean as the smoke test

Stop when: the gate is installed, the hook includes and passes lint-staged, typecheck, and test, and the original goal includes both typecheck and test.
```

## Scope: JS/TS only

Run this only inside a JavaScript or TypeScript repo that carries a `package.json`. The whole apparatus (Husky, lint-staged, Prettier) is npm-ecosystem tooling; it has no business in a Rust crate, a Python project, or any non-Node tree.

Guard before doing anything:

1. Confirm `package.json` exists at the repo root. When it is absent, stop and tell the user this skill is JS/TS-only.
2. Run `ls Cargo.toml pyproject.toml setup.py 2>/dev/null`. When the repo is primarily Rust or Python (those files present, no meaningful `package.json`), stop and say so; a Rust/Python repo gets its own pre-commit story, not this one.

## What this adds over the edit-time hook

An edit-time format/lint hook (PostToolUse on Edit/Write, if your harness runs one) already auto-fixes lint and format on each file as it is written, and a sound code-quality discipline treats that hook surface as owned. Re-running Prettier at commit time is belt-and-suspenders for human-authored or externally-pasted edits the hook never saw; the real value-add here is the part a per-file hook cannot give you: a **full-project typecheck and test run gated on every commit**. Keep that framing in mind; the typecheck + test lines are the point, lint-staged is the cheap fast pass that precedes them.

## Steps

### 1. Detect the package manager

Check for a lockfile and pick the matching manager: `package-lock.json` → npm, `pnpm-lock.yaml` → pnpm, `yarn.lock` → yarn, `bun.lockb` → bun. Default to npm when none is present. Substitute the detected manager into every command and into the hook body below.

### 2. Install dev dependencies

Install `husky lint-staged prettier` as devDependencies with the detected manager (`npm install -D ...`, `pnpm add -D ...`, `yarn add -D ...`, `bun add -d ...`).

### 3. Initialize Husky

```bash
npx husky init
```

This creates `.husky/` and adds `prepare: "husky"` to package.json. Husky v9+ needs no shebang in hook files.

### 4. Write `.husky/pre-commit`

Write the three-stage gate, fast pass first:

```
npx lint-staged
npm run typecheck
npm run test
```

Adapt the runner to the detected package manager. Read package.json `scripts` first. Treat any missing `typecheck` or `test` script as a blocking gap under this skill's original goal: add repo-appropriate scripts with the user, or confirm the user wants a downgraded lint-staged-only goal. Report the original goal successful only after both scripts exist and both hook commands run. Call a downgraded result lint-staged-only so it is distinct from the full typecheck/test gate.

### 5. Write `.lintstagedrc`

```json
{
  "*": "prettier --ignore-unknown --write"
}
```

`--ignore-unknown` skips files Prettier cannot parse (images and the like).

### 6. Write a Prettier config only when none exists

Create `.prettierrc` only when the repo has no Prettier config already (`.prettierrc`, `.prettierrc.json`, `prettier.config.js`, or a `prettier` key in package.json). Respect an existing config; overwriting it churns the repo and fights whatever convention is in place. Defaults when creating fresh:

```json
{
  "useTabs": false,
  "tabWidth": 2,
  "printWidth": 80,
  "singleQuote": false,
  "trailingComma": "es5",
  "semi": true,
  "arrowParens": "always"
}
```

### 7. Verify

Check each invariant:

- `.husky/pre-commit` exists and is executable
- `.lintstagedrc` exists
- the `prepare` script in package.json reads `"husky"`
- a Prettier config exists
- `typecheck` and `test` scripts exist in package.json for the original goal
- `.husky/pre-commit` contains the three stage commands in order: lint-staged, typecheck, test
- Report any hook missing typecheck or test as a blocking gap, even when direct hook execution exits 0
- after the stage-order check passes, run `./.husky/pre-commit` from the repo root; when direct hook execution is unavailable, run the exact command lines from `.husky/pre-commit` in order and require each to pass

### 8. Commit (ask first)

Ask the user before committing rather than auto-committing. When they say go, stage the created and changed files and commit with a subject like `Add pre-commit hooks (husky + lint-staged + prettier)`, or hand the staged changes to `/commit`. The commit itself routes through the new gate, which doubles as the end-to-end smoke test that lint-staged, typecheck, and test all pass.

## Notes

- Husky v9+ hook files need no shebang.
- `prettier --ignore-unknown` keeps the staged pass from choking on binary or unparseable files.
- The hook order is intentional: lint-staged is fast and staged-only, so it runs first; the full typecheck and test run after, since they are the slower, higher-value gate.
- When the repo already has a Husky setup or a different pre-commit framework (lefthook, simple-git-hooks, pre-commit), surface that to the user and ask before layering Husky on top; do not stack two gates blindly.
