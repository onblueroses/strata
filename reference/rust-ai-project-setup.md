<!-- keywords: rust, cargo, clippy, tokio, workspace, crate, pre-commit, rustfmt, actix, axum, rust project, cargo.toml, lints -->
# Rust AI-Agent Project Setup

Mandatory reference for setting up any new Rust project where Claude Code will write the majority of the code. The setup creates a three-layer self-correcting feedback loop: advisory rules (CLAUDE.md) for intent, deterministic hooks for hard stops, and automated linters for everything pattern-matchable. The compiler catches structural mistakes, clippy enforces style, pre-commit hooks gate commits, `#[expect]` annotations auto-expire when code gets wired up, and coverage + mutation testing verify test quality.

Design goal: zero human code review required. The toolchain IS the reviewer.

Proven on: a NEAT neuroevolution simulator (~37 source files) and strata itself (40+ source files: a CLI tool with scanner, lint engine, and template system).

Evidence base: Rust-SWE-bench (Feb 2026, 500 tasks/34 repos), Microsoft Pragmatic Rust Guidelines for AI (Sept 2025), Anthropic's 100k-line C compiler, Vjeux's 100k-line TS-to-Rust port, arXiv instruction-following research (20 frontier models), Chroma context-rot study, Tweag Agentic Coding Handbook.

---

## Quick Nav

| Task | Section |
|------|---------|
| Configure lints for new project | 1. Cargo.toml Lints |
| Set up pre-commit hooks | 4. Pre-Commit Hook |
| Handle dead code properly | 6. Dead Code Management |
| Design error types | 7. Error Type Design |
| Apply pedantic lints to existing code | 8. Applying Pedantic Lints |
| Structure project for AI agents | 19. Project Structure |
| Avoid common AI mistakes in Rust | 20. Rust AI Anti-Patterns |
| Set up testing pipeline | 17. Testing Strategy |
| Full setup from scratch | Setup Checklist (bottom) |

---

## 1. Cargo.toml Lints

<details>
<summary>1. Cargo.toml Lints</summary>

Add after `[profile.*]` sections. Two variants depending on project type:

### Library / Application (default)

```toml
[lints.clippy]
pedantic = { level = "warn", priority = -1 }
# Safety: prevent AI shortcuts
unwrap_used = "deny"
expect_used = "deny"
panic = "deny"
panic_in_result_fn = "deny"
todo = "deny"
unimplemented = "deny"
dbg_macro = "deny"
print_stdout = "deny"
print_stderr = "deny"
allow_attributes = "deny"
# Elegance: push toward idiomatic Rust
manual_let_else = "warn"
cloned_instead_of_copied = "warn"
redundant_else = "warn"
unnested_or_patterns = "warn"
uninlined_format_args = "warn"
semicolon_if_nothing_returned = "warn"
inconsistent_struct_constructor = "warn"
needless_pass_by_value = "warn"
implicit_clone = "warn"
map_unwrap_or = "warn"
unnecessary_wraps = "warn"
# Pedantic overrides - too noisy, low signal
missing_errors_doc = "allow"
missing_panics_doc = "allow"
module_name_repetitions = "allow"
must_use_candidate = "allow"
# Numeric casts - common in simulations/games, reviewer overhead not worth it
cast_possible_truncation = "allow"
cast_sign_loss = "allow"
cast_precision_loss = "allow"
cast_possible_wrap = "allow"

[lints.rust]
missing_debug_implementations = "warn"
unreachable_pub = "warn"
```

### CLI Tool variant

For projects where stdout/stderr IS the primary output (CLI tools, TUI apps):

```toml
# Same as above, except:
print_stdout = "allow"
print_stderr = "allow"
```

Do not use `#[expect(clippy::print_stdout)]` on individual functions in a CLI - it creates annotation noise across dozens of call sites. Allow it crate-wide in the lint config instead.

**Why this matters for AI agents:**
- `allow_attributes = "deny"` is the single most important line. It prevents the AI from silencing warnings with `#[allow(clippy::something)]`. Forces `#[expect(...)]` instead, which produces a compiler error when the expectation becomes unfulfilled (the underlying issue was fixed). Self-correcting.
- `unwrap_used`/`expect_used` = "deny" forces proper error handling from the start. AI agents default to `.unwrap()` constantly. Use `.ok_or_else(|| Error::General("...".to_string()))` or `?` instead.
- `todo`/`unimplemented` = "deny" prevents placeholder code from surviving past the current session.
- `print_stdout`/`print_stderr` = "deny" (for non-CLI) forces structured logging.
- `pedantic` at warn with priority -1 means all pedantic lints fire but the specific deny rules above take precedence.

**Elegance lints (new - push AI toward idiomatic code):**
- `manual_let_else` - forces `let Some(x) = expr else { return }` instead of nested `if let`/`match`. Keeps the happy path flat.
- `cloned_instead_of_copied` - forces `.copied()` for `Copy` types. Documents the guarantee, no allocation.
- `redundant_else` - removes `else` after diverging `if` (after `return`/`break`). Less nesting.
- `unnested_or_patterns` - `Foo(A | B)` over `Foo(A) | Foo(B)`. Terser pattern matching.
- `uninlined_format_args` - `format!("{x}")` over `format!("{}", x)`. Modern Rust style.
- `inconsistent_struct_constructor` - field order matches definition. Visual consistency.
- `semicolon_if_nothing_returned` - explicit semicolons when blocks return `()`. Clear intent.
- `needless_pass_by_value` - take `&T` if you don't consume the value. Better API design.
- `implicit_clone` - prefer explicit `.clone()` over `.to_owned()` / `.to_vec()` when cloning.
- `map_unwrap_or` - use `map_or` / `map_or_else` instead of `.map().unwrap_or()`. Single combinator.
- `unnecessary_wraps` - don't return `Option`/`Result` if every path returns `Some`/`Ok`. Honest signatures.
- `unreachable_pub` (rust lint) - flags `pub` items that are not reachable from the crate root. Prevents over-visibility.

**Pedantic overrides rationale:**
The "allow" entries suppress pedantic lints that generate noise without catching real bugs. `module_name_repetitions` triggers on `brain::brain_config` patterns that are sometimes the clearest naming. `must_use_candidate` flags every pure function. The numeric cast family (`cast_possible_truncation` etc.) fires on `as usize` / `as u32` conversions that are routine in grid/simulation code. Keep these allowed unless the project handles untrusted numeric input.

</details>

---

## 2. clippy.toml

<details>
<summary>2. clippy.toml</summary>

Create at project root:

```toml
msrv = "1.85"
cognitive-complexity-threshold = 30
too-many-lines-threshold = 120
type-complexity-threshold = 250
```

Default thresholds (25 complexity, 100 lines) are too tight for AI-generated code that sometimes needs longer match arms or initialization sequences. These values give breathing room while still catching genuinely tangled functions.

Set `msrv` to match your `rust-version` in Cargo.toml. This prevents clippy from suggesting APIs that don't exist in your minimum supported version.

</details>

---

## 3. Cargo Aliases + Tooling

<details>
<summary>3. Cargo Aliases + Tooling</summary>

Create `.cargo/config.toml`:

```toml
[alias]
lint = "clippy --all-targets -- -D warnings"
ca = "check --all-targets"
ta = "nextest run --no-tests=pass"
cov = "llvm-cov nextest --fail-under-lines 80"
```

AI agents use these constantly. Short names reduce token waste and typo risk. `--all-targets` catches issues in tests and benches, not just lib code. `--no-tests=pass` prevents nextest from failing when no tests exist yet.

### Windows-specific: MSVC target

On Windows with MSYS2/Git Bash, the default GNU target may fail with `dlltool.exe not found`. Add to `.cargo/config.toml`:

```toml
[build]
target = "x86_64-pc-windows-msvc"
```

And install the target: `rustup target add x86_64-pc-windows-msvc`. The MSVC target links against Windows SDK instead of MinGW, avoiding missing linker tool errors. This file should be in `.gitignore` since it's machine-specific - other contributors may use a different target.

### Required cargo extensions

Install these tools on any machine that will run Rust AI-agent projects:

```bash
# Core (integrated into feedback loop)
cargo install cargo-nextest --locked   # parallel test runner
cargo install cargo-llvm-cov           # LLVM source-based coverage with thresholds
cargo install cargo-mutants            # mutation testing - do your tests actually catch bugs?
cargo install cargo-machete            # find unused dependencies
cargo install cargo-deny               # license + advisory + supply chain policy

# Diagnostics (on-demand, not in feedback loop)
cargo install cargo-expand             # print macro expansions
cargo install cargo-audit              # RustSec vulnerability scan
cargo install cargo-outdated           # show outdated dependencies
cargo install cargo-bloat              # binary size analysis
cargo install cargo-semver-checks      # semver compliance checking
cargo install flamegraph               # CPU profiling

# Situational (install when needed)
cargo install cargo-watch              # auto-rebuild on file save (human workflow)
cargo install cargo-generate           # project scaffolding from templates
cargo install samply                   # profiling with Firefox Profiler UI
cargo install tokio-console --locked   # async runtime debugging (async projects only)
```

**Core tools (integrated into aliases, hooks, /lint):**
- **cargo-nextest**: Replaces `cargo test` in aliases and hooks. Parallel execution, per-test timing, better failure output. Use `--no-tests=pass` flag to succeed when no tests exist yet.
- **cargo-llvm-cov**: LLVM source-based code coverage. Integrates directly with nextest via `cargo llvm-cov nextest`. Use `--fail-under-lines 80` to enforce minimum coverage. Use `--html --open` for visual gap analysis. Works on Windows/Mac/Linux.
- **cargo-mutants**: Replaces function bodies with plausible mutations (return defaults, flip operators, change comparisons) and checks if tests catch each one. Surviving mutants = test gaps. Use `--in-diff HEAD~1` to test only changed files. Use `--timeout 30` to cap per-mutant time.
- **cargo-machete**: Finds crate dependencies declared in Cargo.toml but never imported. Add false positives (feature-gated or build-only deps) to `[package.metadata.cargo-machete] ignored = [...]` in Cargo.toml.
- **cargo-deny**: Checks licenses, security advisories, duplicate crates, and source provenance against a `deny.toml` policy file.

**Diagnostic tools (on-demand):**
- **cargo-expand**: Run `cargo expand module::path` when debugging derive macro errors or understanding what a proc macro generates.
- **cargo-audit**: Run `cargo audit` to check dependencies against RustSec advisory database. Pairs with `/xbow` security skill.
- **cargo-outdated**: Run `cargo outdated` to see which dependencies have newer versions. `cargo update --dry-run` covers 80% of this.
- **cargo-bloat**: Run `cargo bloat --release` to see which functions/crates contribute most to binary size. Run `cargo bloat --release --crates` for crate-level breakdown.
- **cargo-semver-checks**: Run `cargo semver-checks` on library crates to verify public API changes don't break semver. Not relevant for binary-only projects.
- **cargo flamegraph**: Run `cargo flamegraph` to generate a CPU flamegraph (flamegraph.svg). Requires a release build. On Windows, may need admin privileges for ETW tracing.

**Situational tools:**
- **cargo-watch**: Run `cargo watch -x check` for auto-rebuild on file save. Useful for humans watching a terminal; Claude Code runs commands explicitly and doesn't need file watching.
- **cargo-generate**: Run `cargo generate --git <template-repo>` for project scaffolding. One-time use per project.
- **samply**: Run `samply record ./target/release/binary` for profiling with Firefox Profiler UI. Not a cargo subcommand.
- **tokio-console**: Run `tokio-console` for async runtime debugging. Only relevant for async projects. Requires `--cfg tokio_unstable` in rustflags.

### Toolchains and miri

```bash
rustup default stable-x86_64-pc-windows-msvc     # default (MSVC Build Tools)
rustup toolchain install stable-x86_64-pc-windows-gnu  # for CodeLLDB debugging
rustup toolchain install nightly --component miri  # for UB detection
```

- **MSVC (default)**: Required for most cargo extensions on Windows. The GNU toolchain needs MinGW's `dlltool.exe` which isn't installed - any crate linking `windows-sys` will fail to compile under GNU.
- **GNU (kept for CodeLLDB)**: Use `cargo +stable-x86_64-pc-windows-gnu build` when you need to build with debug info compatible with the CodeLLDB VS Code debugger.
- **Nightly + miri**: Run `cargo +nightly miri test` to detect undefined behavior in unsafe code. Only useful when the project contains `unsafe` blocks. Miri interprets the code rather than compiling it, so it's slow but thorough.

### settings.json allow entries

When setting up a new project, include permissions for all installed tools:

```json
"Bash(cargo nextest*)",
"Bash(cargo expand*)",
"Bash(cargo audit*)",
"Bash(cargo machete*)",
"Bash(cargo deny*)",
"Bash(cargo bloat*)",
"Bash(cargo outdated*)",
"Bash(cargo semver-checks*)",
"Bash(cargo watch*)",
"Bash(cargo generate*)",
"Bash(cargo add*)",
"Bash(cargo rm*)",
"Bash(cargo upgrade*)",
"Bash(cargo flamegraph*)",
"Bash(cargo +nightly*)"
```

Note: `cargo add` and `cargo rm` are built into cargo (since 1.62). `cargo upgrade` comes from the separate `cargo-edit` crate.

</details>

---

## 4. Pre-Commit Hook (cargo-husky user-hooks)

<details>
<summary>4. Pre-Commit Hook (cargo-husky user-hooks)</summary>

Add to Cargo.toml:

```toml
[dev-dependencies.cargo-husky]
version = "1"
default-features = false
features = ["precommit-hook", "user-hooks"]
```

Create `.cargo-husky/hooks/pre-commit` (git-tracked):

```sh
#!/bin/sh
set -e
export PATH="$HOME/.cargo/bin:$PATH"

echo '+cargo nextest run'
cargo nextest run --no-tests=pass
echo '+cargo clippy -- -D warnings'
cargo clippy -- -D warnings
echo '+cargo fmt -- --check'
cargo fmt -- --check
```

**Why user-hooks, not the default features:**
The default cargo-husky features (`run-cargo-fmt`, `run-cargo-clippy`, `run-cargo-test`) generate the hook at build time and overwrite `.git/hooks/pre-commit` on every rebuild. If the shell PATH doesn't include `~/.cargo/bin` (common on Windows/non-login shells), the hook breaks after a clean build with no visible trace.

With `user-hooks`, the hook source lives in `.cargo-husky/hooks/` (git-tracked). cargo-husky copies it to `.git/hooks/` on build, but the source is durable and editable. The `export PATH` line in the hook script fixes the PATH issue permanently.

**Hook order:** test -> clippy -> fmt. Tests first because they're the most informative failure. Clippy second because it catches logic issues. fmt last because it's the easiest to auto-fix.

**Installation:** Run `cargo test` once after adding cargo-husky. This triggers the build script that copies the hook. Note: cargo-husky only copies the hook on first install or clean rebuild. If you update `.cargo-husky/hooks/pre-commit`, manually copy it to `.git/hooks/pre-commit` or do a clean rebuild.

</details>

---

## 5. deny.toml (Supply Chain Policy)

<details>
<summary>5. deny.toml (Supply Chain Policy)</summary>

Create `deny.toml` at project root:

```toml
# cargo-deny configuration (v0.19+)
# https://embarkstudios.github.io/cargo-deny/

[advisories]
yanked = "warn"
unmaintained = "workspace"
ignore = []  # Add RUSTSEC-YYYY-NNNN entries for acknowledged advisories

[licenses]
allow = [
    "MIT",
    "Apache-2.0",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "ISC",
    "Unicode-3.0",
    "Unicode-DFS-2016",
    "Zlib",
]
confidence-threshold = 0.8

[bans]
multiple-versions = "warn"
wildcards = "deny"

[sources]
unknown-registry = "deny"
unknown-git = "deny"
allow-registry = ["https://github.com/rust-lang/crates.io-index"]
allow-git = []
```

The license allowlist covers the vast majority of Rust ecosystem crates. `wildcards = "deny"` prevents `*` version requirements. `unknown-registry`/`unknown-git` = "deny" blocks dependencies from unknown sources.

**Config version note:** The deny.toml schema changes between cargo-deny versions. The `[advisories]` section above targets v0.19+. Fields like `vulnerability`, `notice`, and `severity-threshold` were removed - all vulnerability advisories now emit errors automatically. Check your installed version with `cargo deny --version`.

</details>

---

## 6. Dead Code Management with #[expect]

<details>
<summary>6. Dead Code Management with #[expect]</summary>

**Never use blanket suppression.** Do not put `#![expect(dead_code)]` or `#![allow(dead_code)]` at the crate root. This silences the entire codebase and defeats the feedback loop.

**Per-item annotations with reason strings:**

```rust
#[expect(
    dead_code,
    reason = "constructed by population init; remove when prey spawning is implemented"
)]
pub(crate) struct Prey {
    // ...
}
```

The reason string serves two purposes: (1) it tells the AI agent when to remove the annotation, (2) the compiler will error with "this lint expectation is unfulfilled" when the item gets used, and the reason string appears in the error message pointing at what changed.

**Per-field annotations when only some fields are dead:**

When a struct is live but individual fields are only used in tests or reserved for future use:

```rust
#[derive(Debug, Clone)]
pub struct IndexEntry {
    pub path: String,
    #[expect(dead_code, reason = "used in tests and available for future lint rules")]
    pub description: String,
}
```

This is more precise than annotating the whole struct. When the field gets used in non-test code, the expectation fires.

**Per-file annotations for cohesive dead modules:**

When an entire file is dead (all items unused), use the file-level inner attribute:

```rust
#![expect(
    dead_code,
    reason = "NeatNetwork used when brain-agent integration is wired up; remove then"
)]
```

This is acceptable because the file is a cohesive unit - when one item gets used, the whole file likely becomes live.

**Dead code cascade behavior (important):**
Rust's dead_code lint does NOT cascade through items whose dead_code is suppressed. If `NeatNetwork` has `#![expect(dead_code)]` and it calls `apply_activation`, then `apply_activation` is NOT considered dead - it has a live reference from NeatNetwork (even though NeatNetwork itself is "dead"). This means you do NOT need to annotate dependencies of already-suppressed items. When you remove the suppression (item gets wired up), the entire dependency chain becomes live automatically.

**#[expect] vs test targets (gotcha):**
A field annotated `#[expect(dead_code)]` that is used in `#[cfg(test)]` code will produce an "unfulfilled lint expectation" warning when compiling with `--test` (since the field IS used in the test binary), but will correctly suppress in the regular binary target. This is a known Rust limitation - the expectation is correct for the bin target. The warning only appears in `cargo test` output, not in `cargo clippy`. Accept it or use `#[cfg_attr(not(test), expect(dead_code))]` if it bothers you (usually not worth the complexity).

</details>

---

## 7. Error Type Design for AI Agents

<details>
<summary>7. Error Type Design for AI Agents</summary>

AI agents constantly hit `From<X>` bounds when using `?`. Design your error type to handle this smoothly:

### Always include a General/Other variant

```rust
#[derive(Debug, thiserror::Error)]
pub enum AppError {
    #[error("IO error: {0}")]
    Io(#[from] std::io::Error),

    // ... typed variants ...

    #[error("{0}")]
    General(String),
}
```

The `General(String)` variant is the escape hatch for third-party crates that don't have standard `From` impls. Without it, the AI will fight the type system every time it uses a new crate.

### Manual From impls for third-party errors

Many popular crates (dialoguer, globset, walkdir) don't implement conversion to `std::io::Error` or your app error. Write manual `From` impls:

```rust
// dialoguer::Error -> our error (no io::Error conversion available)
impl From<dialoguer::Error> for AppError {
    fn from(e: dialoguer::Error) -> Self {
        AppError::General(format!("Prompt error: {e}"))
    }
}

// walkdir::Error -> our error (has into_io_error() but it's Option)
impl From<walkdir::Error> for AppError {
    fn from(e: walkdir::Error) -> Self {
        match e.into_io_error() {
            Some(io_err) => AppError::Io(io_err),
            None => AppError::General("walkdir error".to_string()),
        }
    }
}

// globset::Error -> our error (placed in the module that uses globset)
impl From<globset::Error> for AppError {
    fn from(e: globset::Error) -> Self {
        AppError::General(format!("Glob pattern error: {e}"))
    }
}
```

**Pattern:** Put manual `From` impls either in `error.rs` (for widely-used crates) or in the specific module that uses the crate (for localized usage). The second approach keeps error.rs from accumulating imports for every transitive dependency.

**Avoid `.expect()` as a workaround.** When `expect_used = "deny"`, the AI can't use `.expect("should exist")`. Use `.ok_or_else(|| AppError::General("...".to_string()))` instead:

```rust
// Bad (denied by clippy):
config_path.parent().expect("config path has parent").to_path_buf()

// Good:
config_path
    .parent()
    .map(Path::to_path_buf)
    .ok_or_else(|| AppError::General("config path has no parent".to_string()))
```

</details>

---

## 8. Applying Pedantic Lints to Existing Code

<details>
<summary>8. Applying Pedantic Lints to Existing Code</summary>

When adding `pedantic = "warn"` to a codebase that wasn't written with pedantic lints, expect 30-60 warnings. The fix workflow:

### Step 1: Auto-fix mechanical issues

```bash
cargo clippy --fix --allow-dirty
```

This fixes ~80% of pedantic issues automatically: `uninlined_format_args` (the biggest category), `if_not_else`, `doc_markdown`, `explicit_iter_loop`, etc.

### Step 2: Manual fixes for the remaining ~20%

Common patterns that need manual fixes:

| Lint | Bad | Good |
|------|-----|------|
| `format_push_string` | `s.push_str(&format!("x={}", y))` | `use std::fmt::Write; let _ = writeln!(s, "x={y}");` |
| `needless_pass_by_value` | `fn f(x: Option<String>)` | `fn f(x: Option<&str>)` - update call sites with `.as_deref()` |
| `needless_borrow` | `if let Some(ref x) = opt_ref` | `if let Some(x) = opt_ref` (when already a reference) |
| `if_not_else` | `if !x.exists() { bad } else { good }` | `if x.exists() { good } else { bad }` |
| `while_let_on_iterator` | `while let Some(x) = iter.next()` | `for x in iter` |
| `derivable_impls` | manual `Default` impl identical to derive | `#[derive(Default)]` |
| `match_wildcard_for_single_variants` | `_ => {}` with one variant | name the variant |

### Step 3: Verify

```bash
cargo fmt && cargo clippy -- -D warnings && cargo test
```

### The `needless_pass_by_value` cascade

This is the most disruptive pedantic lint. When you change a function signature from `Option<String>` to `Option<&str>`, every call site must add `.as_deref()`. For clap-derived structs where fields are `Option<String>`, the dispatch code becomes:

```rust
// Before:
commands::lint::run(path, rule, quiet, &format)

// After (rule: Option<String> from clap, but lint::run now takes Option<&str>):
commands::lint::run(path, rule.as_deref(), quiet, &format)
```

This also changes `if let Some(ref x) = opt` to `if let Some(x) = opt` since `opt` is now `Option<&str>` - taking a `ref` of `&str` creates `&&str` which triggers `needless_borrow`.

</details>

---

## 9. Visibility Hardening

<details>
<summary>9. Visibility Hardening</summary>

Use `pub(crate)` for everything internal. Only use `pub` for types that are part of the external API (snapshots, configs, types used across the public boundary).

This gives compile-time enforcement of module boundaries. If brain/ tries to import an agent/ internal type that's `pub(crate)`, the compiler rejects it. No documentation needed - the compiler IS the documentation.

**Pattern for public API boundary:**
Define read-only snapshot types (e.g., `WorldSnapshot`, `AgentSnapshot`) as `pub`. Everything behind them is `pub(crate)`. External consumers (visualization, serialization) go through snapshots only.

**Exception for binary crates:**
In a pure binary crate (no lib.rs), `pub` and `pub(crate)` are functionally identical. Still prefer `pub(crate)` for consistency and as documentation of intent - if you later extract a library, the visibility is already correct.

</details>

---

## 10. .claude/settings.json Permissions

<details>
<summary>10. .claude/settings.json Permissions</summary>

```json
{
  "permissions": {
    "allow": [
      "Bash(cargo build*)",
      "Bash(cargo check*)",
      "Bash(cargo clippy*)",
      "Bash(cargo test*)",
      "Bash(cargo fmt*)",
      "Bash(cargo doc*)",
      "Bash(cargo run*)",
      "Bash(cargo lint*)",
      "Bash(cargo ca*)",
      "Bash(cargo ta*)",
      "Bash(cargo nextest*)",
      "Bash(cargo expand*)",
      "Bash(cargo audit*)",
      "Bash(cargo machete*)",
      "Bash(cargo deny*)",
      "Bash(cargo bloat*)",
      "Bash(cargo outdated*)",
      "Bash(cargo semver-checks*)",
      "Bash(cargo watch*)",
      "Bash(cargo generate*)",
      "Bash(cargo add*)",
      "Bash(cargo rm*)",
      "Bash(cargo upgrade*)",
      "Bash(cargo flamegraph*)",
      "Bash(cargo llvm-cov*)",
      "Bash(cargo mutants*)",
      "Bash(cargo insta*)",
      "Bash(cargo +nightly*)",
      "Bash(git status*)",
      "Bash(git log*)",
      "Bash(git diff*)",
      "Bash(git show*)",
      "Bash(git branch*)",
      "Bash(git add*)",
      "Bash(git commit*)"
    ],
    "deny": [
      "Bash(git push --force*)",
      "Bash(git push -f*)",
      "Bash(git push*--force*)",
      "Bash(git push*-f *)",
      "Bash(git push* -f)",
      "Bash(git commit --no-verify*)",
      "Bash(git commit*--no-verify*)",
      "Bash(rm -rf*)",
      "Bash(cargo publish*)"
    ]
  }
}
```

**Deny patterns must be position-independent.** Glob `*` matches any characters, so `git push*--force*` catches `git push origin --force`, `git push origin main --force`, etc. Without the wildcard variants, an AI agent can bypass the deny by putting arguments between `push` and the flag.

The `--no-verify` deny prevents the AI from skipping the pre-commit hook. `cargo publish` prevents accidental crate publication.

</details>

---

## 11. .claude/rules/ Path-Scoped Context

<details>
<summary>11. .claude/rules/ Path-Scoped Context</summary>

Create one rule file per module in `.claude/rules/`. Each file has YAML frontmatter with glob patterns:

```markdown
---
globs: ["src/brain/**/*.rs"]
---

# Brain Module Rules

## Dependency boundary
brain/ must NEVER import from world/, agent/, or signal/...
```

These files are loaded into context ONLY when the AI touches a matching file. Zero cost when working on other modules. Write only what an AI agent would get wrong without instruction - invariants, forbidden imports, data format contracts, non-obvious ordering requirements.

**What to include in rules:**
- Dependency boundaries (what this module can and cannot import)
- Data invariants (sorted arrays, index formulas, count constraints)
- Ordering requirements (lifecycle steps, processing order)
- Non-obvious design decisions with rationale

**What NOT to include:**
- General Rust best practices (clippy handles those)
- API documentation (that goes in doc comments)
- Implementation details that change frequently

</details>

---

## 12. CLAUDE.md Structure (Lean Router Pattern)

<details>
<summary>12. CLAUDE.md Structure (Lean Router Pattern)</summary>

The project-level CLAUDE.md should be under 80 lines. It is a router, not a manual.

Structure:
1. **One-liner** - what the project does
2. **Commands** - exact cargo commands with alias explanations
3. **Architecture pointer** - reference to ARCHITECTURE.md with section index (don't duplicate content)
4. **Dependency diagram** - ASCII art showing module relationships
5. **Invariants** - 5-10 project-wide rules (numbered, each one sentence)
6. **Boundaries** - three tiers: Always / Ask first / Never

The CLAUDE.md is loaded on every session. Rules files handle module-specific detail. ARCHITECTURE.md handles deep design docs. This layering keeps context costs proportional to what the AI is actually working on.

</details>

---

## 13. /lint Skill

<details>
<summary>13. /lint Skill</summary>

Create a project-local `/lint` skill (e.g. inside a project-local `skills/lint/SKILL.md` or a `.claude/skills/lint/SKILL.md` override):

```markdown
---
name: lint
description: "Run the full 8-step verification pipeline: fmt, clippy, test, coverage, mutants, machete, deny, doc. Manual: invoke with /lint."
---

# /lint - Full Verification Pipeline

Run all eight checks in sequence. Stop on first failure.

## Steps

1. **Format check**: `cargo fmt -- --check`
2. **Clippy lint**: `cargo lint` (alias for `cargo clippy --all-targets -- -D warnings`)
3. **Test**: `cargo ta` (alias for `cargo nextest run`)
4. **Coverage**: `cargo cov` (alias for `cargo llvm-cov nextest --fail-under-lines 80`)
5. **Mutation (changed files only)**: `cargo mutants --in-diff HEAD~1 --timeout 30` - skip if no recent commits
6. **Unused dependencies**: `cargo machete`
7. **Supply chain check**: `cargo deny check`
8. **Doc check**: `cargo doc --no-deps 2>&1`

## Output

Report results as a summary table. On failure, show first 3 errors and stop.
```

</details>

---

## 14. .gitignore Additions

<details>
<summary>14. .gitignore Additions</summary>

Append to any Rust .gitignore:

```
# Claude Code
.claude/worktrees/
.claude/settings.local.json
.claude/auto-context-save-*.md
.claude/plans/

# Machine-specific
.cargo/config.toml
```

Note: `.cargo/config.toml` is gitignored because it contains machine-specific settings like the build target (MSVC on Windows, native on Linux/Mac). Each developer's machine may need different settings. Aliases can go in a separate checked-in `.cargo/config-shared.toml` that developers symlink, but for single-developer projects just put everything in the gitignored file.

</details>

---

## 15. Edition 2024 + MSRV

<details>
<summary>15. Edition 2024 + MSRV</summary>

Rust edition 2024 is stable as of Rust 1.85 (February 2025). Use it for all new projects:

```toml
[package]
edition = "2024"
rust-version = "1.85"
```

Edition 2024 changes include: `unsafe_op_in_unsafe_fn` is warn by default, new lifetime capture rules in `impl Trait`, `gen` is a reserved keyword, and `#[must_use]` on more standard library types. No action needed - these are all improvements.

If targeting older Rust versions, use `edition = "2021"` with `rust-version = "1.70"` or similar.

</details>

---

## 16. Release Profile

<details>
<summary>16. Release Profile</summary>

For binary distribution:

```toml
[profile.release]
lto = true
strip = true
codegen-units = 1
```

- `lto = true` - link-time optimization across all crates. Slower compile, smaller/faster binary.
- `strip = true` - strip debug symbols. Reduces binary size significantly (often 50%+).
- `codegen-units = 1` - single codegen unit for maximum optimization. Only slows release builds.

</details>

---

## 17. Testing Strategy for Autonomous AI

<details>
<summary>17. Testing Strategy for Autonomous AI</summary>

When no human reviews AI-generated code, tests are the only defense against semantic bugs. The compiler catches structural correctness; tests catch behavioral correctness. This section configures a multi-layer testing strategy that AI agents follow automatically.

### Dev-Dependencies

Add to Cargo.toml:

```toml
[dev-dependencies]
proptest = "1"
insta = { version = "1", features = ["yaml"] }
```

For CLI projects, also add (strata already has these):

```toml
assert_cmd = "2"
predicates = "3"
assert_fs = "1"
```

### nextest Configuration

Create `.config/nextest.toml`:

```toml
[profile.default]
# Catch tests that spawn processes/threads without cleanup (common AI mistake)
leak-timeout = { period = "500ms", result = "fail" }

[[profile.default.overrides]]
filter = 'all()'
# Kill runaway tests - AI sometimes generates accidental infinite loops
slow-timeout = { period = "10s", terminate-after = 3 }
```

Leak detection catches a specific AI failure mode: tests that spawn child processes or threads and forget to join/kill them. Without this, leaked resources accumulate across test runs and cause flaky failures that are hard to diagnose.

### CLAUDE.md Testing Rules

Add this block to your project CLAUDE.md (adapting the invariant examples to your project):

```markdown
## Testing Rules

MANDATORY: Every new public function MUST have tests.

### Test-first workflow
- Write the test BEFORE writing the implementation. This prevents tautological tests
  where you read the implementation and write a test that mirrors it.
- Flow: write test (red) -> implement (green) -> refactor -> commit.
- If modifying existing code: write a new test that captures the desired change FIRST,
  verify it fails, then make the change.

### Test style
- Test BEHAVIOR, not implementation details. Name: `test_<function>_<scenario>_<expected>`
- Arrange-Act-Assert. One assertion concept per test.
- Every public function MUST have at least one error/edge case test. Happy-path-only is insufficient.
- For any pure function: write at least one proptest (roundtrip or no-panic). Unit tests for edge cases.

### Forbidden test patterns
- `assert!(result.is_ok())` without checking the value (no-op assertion)
- Tests that mirror implementation logic (tautological - if the impl is wrong, the test passes anyway)
- Tests that only verify "runs without panicking" and assert nothing
- Hardcoding expected values copied from running the implementation (circular validation)

### Before reporting done
Run `cargo nextest run`. All tests must pass.
```

**Why these specific rules matter for AI:** AI agents default to writing tests that confirm the code they just wrote. They read the implementation, see it returns `Ok(42)`, and write `assert_eq!(result, Ok(42))`. This is tautological - the test passes because the AI wrote both sides. The forbidden patterns above block the most common versions of this.

### Property Testing with proptest

Property tests explore the input space instead of testing examples. They catch edge cases that AI-written unit tests miss because AI anchors on obvious values (0, 1, empty string, "hello").

**Two mandatory patterns for every pure function:**

```rust
use proptest::prelude::*;

// Pattern 1: Roundtrip (parse then format, serialize then deserialize)
proptest! {
    #[test]
    fn parse_roundtrip(n: u32) {
        let s = n.to_string();
        let parsed = parse(&s).unwrap();
        prop_assert_eq!(parsed, n);
    }
}

// Pattern 2: No-panic on arbitrary input
proptest! {
    #[test]
    fn parse_never_panics(s in "\\PC*") {
        let _ = parse(&s); // must not panic, only return Ok or Err
    }
}
```

**For complex types, use proptest strategies:**

```rust
proptest! {
    #[test]
    fn config_roundtrip(
        name in "[a-z]{1,20}",
        count in 0u32..1000,
        enabled in proptest::bool::ANY,
    ) {
        let config = Config { name, count, enabled };
        let json = serde_json::to_string(&config).unwrap();
        let parsed: Config = serde_json::from_str(&json).unwrap();
        prop_assert_eq!(config.name, parsed.name);
        prop_assert_eq!(config.count, parsed.count);
    }
}
```

**What proptest catches that unit tests don't:**
- Off-by-one errors at boundary values the AI didn't think to test
- Unicode handling issues (AI tests with ASCII only)
- Integer overflow on large inputs
- Empty/whitespace-only strings that pass naive validation

### Snapshot Testing with insta

Snapshot tests pin complex output so AI can't silently change behavior. First run creates `.snap` files. Subsequent runs diff against them. If AI refactors a function and its output changes, the snapshot test fails.

**Setup:** Create `.config/insta.yaml` at project root:

```yaml
behavior:
  require_full_match: true
```

**Pattern for CLI output:**

```rust
use insta::assert_snapshot;

#[test]
fn test_lint_report_format() {
    let output = run_lint_on_fixture("tests/fixtures/broken_project");
    assert_snapshot!(output);
}

#[test]
fn test_config_default_serialization() {
    let config = Config::default();
    insta::assert_yaml_snapshot!(config);
}
```

**For CI (and the /lint skill):** set `INSTA_UPDATE=no` to hard-fail on any snapshot change:

```bash
INSTA_UPDATE=no cargo nextest run
```

**When to use snapshots vs assertions:**
- Snapshots: complex structured output (JSON, YAML, multi-line CLI output, error messages)
- Assertions: simple values, numeric results, boolean conditions
- Proptests: invariants that should hold across all inputs

### Coverage Enforcement with cargo-llvm-cov

Coverage thresholds catch modules where AI wrote code but skipped tests entirely.

**Threshold enforcement:**

```bash
# Fail if line coverage drops below 80% (alias: cargo cov)
cargo llvm-cov nextest --fail-under-lines 80

# Visual coverage report - identify gaps to feed back to Claude
cargo llvm-cov --html --open
```

**Too slow for pre-commit** (instrumented build = 2-4x slower than regular build). Use in the pre-push hook (Section 18) or CI instead.

**Feeding coverage gaps back to AI:** Run `cargo llvm-cov --html --open`, find uncovered functions (red lines in the report), and paste them back:

```
These functions have zero test coverage:
- src/scanner/links.rs: resolve_link (lines 47-82)
- src/lint/dead_links.rs: check_cross_references (lines 15-40)
Write targeted tests for each. Focus on error paths and edge cases.
```

**What 80% means in practice:** 80% line coverage means 1 in 5 lines has no test exercising it. This is a floor, not a ceiling. For critical logic (parsers, validators, lint rules), aim higher. The threshold prevents the case where AI writes a whole module and skips tests entirely - which it will do unless forced.

### Mutation Testing with cargo-mutants

Mutation testing answers: "If I break this code, do my tests notice?" Coverage says "this line ran." Mutation testing says "if this line returned garbage, would any test fail?"

**Run on changed files only (practical for CI and /lint):**

```bash
cargo mutants --in-diff HEAD~1 --timeout 30
```

**Run on a specific module:**

```bash
cargo mutants --file src/lint/dead_links.rs --timeout 30
```

**When a mutant survives,** feed it back to the AI:

```
This mutation survived my tests: replaced `>` with `>=` in
src/lint/rules_completeness.rs line 42. Write a test that catches
this specific boundary condition.
```

**Too slow for pre-commit or pre-push.** A small crate (200 lines) takes 2-5 minutes. Include in CI on PRs, or run manually on critical modules after implementation via `/lint`.

**Skip functions that are legitimately hard to test:**

```rust
#[mutants::skip] // UI formatting only, tested visually
fn format_progress_bar(pct: f64) -> String { ... }
```

### Testing Tiers Summary

| Layer | Tool | When | What it catches |
|-------|------|------|-----------------|
| Unit tests | cargo-nextest | Pre-commit hook | Basic behavioral correctness |
| Property tests | proptest | Pre-commit (runs with nextest) | Edge cases, boundary conditions, invariant violations |
| Snapshot tests | insta | Pre-commit (runs with nextest) | Silent output changes from refactoring |
| Coverage | cargo-llvm-cov | Pre-push hook, CI, /lint | Untested modules and functions |
| Mutation | cargo-mutants | CI, /lint (changed files only) | Weak tests that don't assert enough |

</details>

---

## 18. Pre-Push Hook (Coverage Gate)

<details>
<summary>18. Pre-Push Hook (Coverage Gate)</summary>

The pre-commit hook (Section 4) stays fast: nextest + clippy + fmt. The pre-push hook adds the slower coverage check as a gate before code reaches the remote.

Create `.cargo-husky/hooks/pre-push` (git-tracked):

```sh
#!/bin/sh
set -e
export PATH="$HOME/.cargo/bin:$PATH"

echo '+cargo llvm-cov nextest --fail-under-lines 80'
cargo llvm-cov nextest --fail-under-lines 80
```

**Why pre-push, not pre-commit:** Coverage requires an instrumented build (2-4x slower). Running it on every commit makes the feedback loop too slow (45-120s vs 10-30s). Pre-push is the right gate: you can commit freely during development, but pushing to the remote requires meeting the coverage threshold.

**Installation:** cargo-husky automatically copies hooks from `.cargo-husky/hooks/` to `.git/hooks/` on build. If you add the pre-push hook after initial setup, run `cargo test` once or manually copy it to `.git/hooks/pre-push`.

</details>

---

## 19. Project Structure for AI Agents

<details>
<summary>19. Project Structure for AI Agents</summary>

Based on Microsoft's Pragmatic Rust Guidelines for AI (September 2025) and Rust-SWE-bench failure analysis. 43.7% of AI agent failures in Rust are cross-file comprehension errors (E0433 undeclared modules, E0432 unresolved imports, E0425 unresolved names). These structural choices reduce that failure rate.

### Module Design

**Small modules, explicit re-exports.** Each module should fit in one context window (~500 lines max). Use `mod.rs` or top-level `lib.rs` to re-export the public interface:

```rust
// src/lib.rs - explicit re-exports, agent sees the full API surface in one file
pub mod config;
pub mod error;
pub mod lint;
pub mod scanner;

pub use config::Config;
pub use error::AppError;
```

**Prefer concrete types over deep generics.** `Service<Backend<Store<T>>>` creates cognitive load for agents. Use concrete types and introduce generics only when you have 2+ real implementations:

```rust
// Bad for AI - agent will struggle with bounds
fn process<S: Store + Send + Sync, B: Backend<S>>(backend: &B) -> Result<()>

// Good for AI - concrete, discoverable
fn process(backend: &SqliteBackend) -> Result<()>
```

**Essential functionality as inherent methods, not trait impls.** Agents find inherent methods via type navigation. Trait methods require knowing which trait to `use` - agents miss these constantly.

```rust
// Bad - agent won't discover this without explicit `use Validate`
impl Validate for Config {
    fn validate(&self) -> Result<()> { ... }
}

// Good - always discoverable on the type
impl Config {
    pub fn validate(&self) -> Result<()> { ... }
}
```

**Use traits only when you need polymorphism** (multiple types implementing the same interface). Don't create a trait for a single implementation.

### Dependency Direction

Keep a clear dependency DAG. Every module should import "inward" toward core types, never create cycles:

```
main.rs -> commands/ -> lint/ -> scanner/ -> config/
                                          -> error/
```

Put this DAG in the project CLAUDE.md (Section 12) so the agent sees it every session. When agents violate the DAG, the path-scoped rules (Section 11) catch it.

### File Organization

```
src/
  main.rs           # Entry point, arg parsing, dispatch only
  lib.rs            # Public re-exports (for integration testing and lib consumers)
  error.rs          # Central error type (Section 7)
  config.rs         # Configuration types + loading
  commands/         # One file per CLI subcommand
    mod.rs
    init.rs
    check.rs
    lint.rs
  scanner/          # File scanning, parsing
    mod.rs
    walker.rs
    links.rs
  lint/             # Lint rule implementations
    mod.rs
    rules/
      mod.rs
      dead_links.rs
      orphan_files.rs
```

Each directory gets a `mod.rs` that re-exports the public interface. This is the map agents navigate by.

### Visibility Strategy (expanded from Section 9)

- `pub` only for types/functions that appear in the library's public API or that integration tests need
- `pub(crate)` for everything shared between modules
- Private (default) for module internals
- `pub(super)` rarely useful - prefer `pub(crate)` for clarity

**For binary-only crates:** Still use `pub(crate)` for internal types. If you later extract a library, the visibility is already correct. More importantly, it serves as documentation of intent that agents can read.

### Reference: Microsoft Rust Guidelines for Agents

Microsoft published a condensed ~22k token version of their Rust guidelines optimized for AI agent context windows: `https://microsoft.github.io/rust-guidelines/agents/all.txt`

Download Microsoft's Rust guidelines and keep them as a project reference (alongside CLAUDE.md) for projects that benefit from Microsoft's conventions. Reference the file from CLAUDE.md.

</details>

---

## 20. Rust AI Anti-Patterns

<details>
<summary>20. Rust AI Anti-Patterns</summary>

AI agents produce specific recurring anti-patterns in Rust. These are the documented failure modes from Rust-SWE-bench, Anthropic's C compiler project, and the 100k-line TypeScript-to-Rust port. Add the rules from this section to your project CLAUDE.md.

### Clone Abuse

The #1 AI Rust anti-pattern. When the borrow checker complains, agents reach for `.clone()` as the path of least resistance. The code compiles but is non-idiomatic and can be slow.

**CLAUDE.md rule:**

```markdown
## Clone Policy
- NEVER add `.clone()` to silence a borrow checker error without first trying:
  1. Restructure to avoid the simultaneous borrow
  2. Use references with appropriate lifetimes
  3. Use `Cow<'_, T>` for conditionally-owned data
- If `.clone()` is genuinely the right choice, add a comment: `// clone: <reason>`
- `.clone()` is acceptable for: config values at startup, small Copy types, test setup
```

Clippy lint support: `clippy::redundant_clone` catches unnecessary clones but not semantically-wrong ones. No lint catches "you should have restructured instead of cloning." The CLAUDE.md rule is the only defense.

### Arc<Mutex<T>> Proliferation

AI defaults to `Arc<Mutex<T>>` for any shared state, even when channels, `RwLock`, or ownership transfer would be more appropriate.

**CLAUDE.md rule:**

```markdown
## Shared State
- Prefer message passing (channels) over shared state
- If shared state is needed, prefer `RwLock` over `Mutex` when reads dominate
- `Arc<Mutex<T>>` is acceptable for: connection pools, caches, simple counters
- NEVER wrap large structs in `Arc<Mutex<T>>` - split into smaller independently-lockable pieces
```

### Unwrap/Expect Evasion

Already handled by `unwrap_used = "deny"` and `expect_used = "deny"` in Section 1. This is the strongest protection in the setup - the compiler catches it.

### Async Pitfalls (for async projects)

Add these rules to CLAUDE.md for any project using tokio:

```markdown
## Async Rules
- Use `tokio::sync::Mutex`, NOT `std::sync::Mutex` in async code (std Mutex blocks the runtime)
- NEVER call `block_on()` inside an async function (deadlocks the tokio worker)
- NEVER use `async-std` - this project uses tokio exclusively
- Use `tokio::spawn` for concurrent tasks, not `std::thread::spawn`
- Always handle `JoinHandle` results - don't let spawned tasks silently fail
```

### Trait Bound Explosion

AI agents accumulate trait bounds across function signatures until they become unreadable. This is especially bad in generic code.

**Prevention:** Follow the "concrete types first" rule from Section 19. When trait bounds are necessary, use `where` clauses instead of inline bounds for readability:

```rust
// Bad (AI-generated mess)
fn process<T: Store + Send + Sync + Clone + Debug, U: Into<T> + From<String>>(input: U) -> T

// Better - where clause, and question whether you need all these bounds
fn process<T>(input: impl Into<T>) -> T
where
    T: Store + Send + Sync,
{
```

### Silent Simplification

Documented in the 100k-line port: Claude skips difficult methods and produces "simplified versions" unless explicitly told to implement fully. The fix is in the prompt, not the setup:

- Use `/spec` to break work into individual method-level steps
- In specs, write: "Implement ALL methods. Do not skip or simplify."
- Review code size against expectations - if a complex function is suspiciously short, it was probably simplified

### Context Poisoning

Also from the 100k-line port: Claude modified source comments, then replicated errors in subsequent work. Ultra-granular commits (one per task) allow easy reversion. The pre-commit hook ensures each commit is at least compilable and passing tests.

</details>

---

## 21. Context Management for Long Sessions

<details>
<summary>21. Context Management for Long Sessions</summary>

Context windows degrade as they fill. Research (Chroma 2025) found every frontier model tested loses accuracy as input length increases - performance drops 30%+ when relevant information sits in the middle of the context. This section covers session hygiene.

### Session Boundaries

- **One feature per session.** Don't mix unrelated work. Use `/clear` between unrelated tasks.
- **Commit and restart** for features that span 3+ hours. Export progress to a spec file, start fresh.
- **Ultra-granular commits** during implementation. Each small task = one commit. This creates save points for easy revert.

### Context Economics

Claude Code's 200K-token window accommodates roughly 150K words. Baseline system prompt + CLAUDE.md + rules files consume ~20K tokens, leaving ~180K for actual work. Each file read, grep result, and exploration dead-end stays in the window.

**Strategies:**
- Manual file reads outperform automatic discovery. Telling the agent exactly which file to read prevents it from spawning slow background searches that pull in irrelevant content.
- Undo wrong directions instead of correcting them. Conversation rewinding beats corrective follow-ups.
- Use subagents (Task tool) for exploration. The subagent's full investigation history stays in its own context, and only the distilled result returns to the main window.

### Post-Compaction Recovery

When context is compacted, CLAUDE.md rules lose priority. The spec file (`.claude/specs/`) survives because it's read from disk. This is why the spec-driven workflow matters - the spec IS the persistent state.

### The Three-Attempt Pattern

Expect first-shot code to be ~95% wrong (Sanity engineering report, 2025). The first attempt builds system context. The second attempt (~50% wrong) incorporates feedback. The third attempt is usually workable. Budget for iteration, not perfection.

</details>

---

## 22. CLAUDE.md Compliance Research

<details>
<summary>22. CLAUDE.md Compliance Research</summary>

Research testing 20 frontier models on instruction-following (arXiv 2025) found:

- 10 instructions: 94-100% accuracy
- 100 instructions: 27-98% (massive variance)
- 500 instructions: best model achieves only 68%
- **The math: overall compliance = (per-instruction compliance)^(number of instructions)**
- 20 rules at 95% per-rule compliance = **36% overall compliance** (0.95^20)

This means every line in CLAUDE.md competes for attention. Claude Code's system prompt already contains ~50 instructions, leaving limited capacity for yours.

### Implications for Section 12

The "under 80 lines" guidance in Section 12 is correct, but here's the research backing:

1. **Front-load critical rules.** Models attend more to the beginning and end of context. Put safety rules and testing requirements at the top.
2. **Positive framing outperforms negative.** "Always use `?` for error propagation" beats "Never use `.unwrap()`". When you must use "Never," pair it with what to do instead.
3. **One code example beats three paragraphs.** Show the pattern, don't describe it.
4. **Don't duplicate what linters enforce.** If clippy catches it, don't burn a CLAUDE.md rule on it. CLAUDE.md rules are for things the toolchain can't catch (architecture decisions, naming conventions, business logic constraints).
5. **Three-tier boundaries are the most effective constraint pattern:**
   - **Always**: autonomous, no approval needed
   - **Ask first**: needs human sign-off
   - **Never**: hard stop (pair with "instead, do X")

### The Three-Layer Enforcement Model

| Layer | Mechanism | What it catches | Reliability |
|-------|-----------|----------------|-------------|
| CLAUDE.md / rules/ | Advisory instructions | Architecture, naming, patterns, intent | ~80-95% per rule, degrades with count |
| Hooks | Deterministic gates | Test failures, format violations, coverage drops | 100% (cannot be bypassed without denied --no-verify) |
| Linters + CI | Automated validation | Everything pattern-matchable: style, unused deps, vulnerabilities, dead code | 100% for covered patterns |

Instructions explain the "what and why." Hooks prevent the worst outcomes. Linters catch everything in between. No single layer is sufficient. The setup in this document implements all three.

</details>

---

## 23. Code Elegance

<details>
<summary>23. Code Elegance</summary>

Rust-specific applications of the universal code quality principles. For the language-agnostic philosophy (parse-don't-validate, comment discipline, anti-defensiveness, AI slop tells, testing philosophy, agent workflow), see `$STRATA_HOME/reference/code-quality-principles.md`. This section covers how those principles manifest in Rust specifically.

### The Elegance Philosophy

**Trust the type system.** Validate at system boundaries. Everything internal trusts the types. If a function receives a `Username`, it's already validated - don't check again.

**Parse, don't validate.** Convert raw input into semantically rich types that encode invariants. A function taking `NonZeroU32` cannot receive zero - no error handling needed. A function taking `Email` already has a valid email - no regex check inside.

```rust
// Defensive (validates everywhere)
fn send_email(to: &str) -> Result<()> {
    if !is_valid_email(to) { return Err(Error::InvalidEmail); }
    // ...
}

// Elegant (impossible to misuse)
fn send_email(to: &Email) -> Result<()> {
    // `to` is guaranteed valid by construction. No check needed.
}
```

**Flat over nested.** Use `let-else` and `?` to keep the happy path at the left margin. Each level of nesting is a cognitive tax.

```rust
// Nested (AI default)
fn process(input: Option<&str>) -> Result<i32> {
    match input {
        Some(s) => match s.parse::<i32>() {
            Ok(n) => Ok(n * 2),
            Err(e) => Err(e.into()),
        },
        None => Err(Error::Missing),
    }
}

// Flat (elegant)
fn process(input: Option<&str>) -> Result<i32> {
    let Some(s) = input else { return Err(Error::Missing) };
    let n = s.parse::<i32>()?;
    Ok(n * 2)
}
```

**Combinators over match on Option/Result.** `.map()`, `.and_then()`, `.unwrap_or_else()` compile to identical machine code as manual matching but communicate intent more clearly.

```rust
// Verbose match
let name = match user.nickname() {
    Some(n) => n.to_uppercase(),
    None => "ANONYMOUS".to_string(),
};

// Combinator
let name = user.nickname()
    .map(|n| n.to_uppercase())
    .unwrap_or_else(|| "ANONYMOUS".to_string());
```

**Iterator chains when the pipeline is linear.** Use explicit loops when the body is large, has multiple concerns, or needs early returns from the enclosing function.

**Enums over trait objects for closed sets.** If you know all variants at compile time, use an enum. Reserve `dyn Trait` for when downstream code needs to add variants.

**Honest signatures.** A function that always succeeds should not return `Result`. A function that takes `&str` but immediately clones it should take `impl Into<String>`. The signature is the documentation.

### CLAUDE.md Code Style Rules

Add this block to every project CLAUDE.md. These are the rules that lints cannot enforce - they require judgment.

```markdown
## Code Style

Write code for the reader who knows Rust. No training wheels.

- Comments explain WHY, never WHAT or HOW. If a comment restates the code, delete it.
  No doc comments on private functions with clear names. No `// increment counter`.
  Module-level `//!` docs for concepts and invariants are good.
- No defensive checks on internal code. Validate at system boundaries only (CLI args,
  file input, API requests). Internal functions trust their types.
- Use newtypes and parse-don't-validate to make invalid states unrepresentable.
  Prefer `Email` over `String`, `NonZeroU32` over `u32` when the constraint matters.
- Prefer `let-else` over nested `if let`/`match`. Keep the happy path flat.
- Prefer `?` and combinators (`.map()`, `.and_then()`) over explicit `match` on
  Option/Result. Use `match` when you need exhaustive enum handling.
- Iterator chains for clear linear pipelines. Explicit loops for complex bodies.
- No unnecessary derives. Add Clone, Debug, etc. when actually needed, not "just in case".
- No wrapper types that add no semantic value. No abstractions for one use case.
- No getters/setters on structs with no invariants. Make fields pub instead.
- Match the style of surrounding code. Consistency within a file beats any abstract rule.
- Solve the actual problem. No speculative flexibility, no "what if we need to..."
```

### Killing AI Slop

AI-generated Rust has specific tells. These rules target them directly:

**Over-commenting (the #1 tell):**
```rust
// BAD - AI writes this constantly
/// Gets the configuration.
pub fn config(&self) -> &Config {
    &self.config
}

// GOOD - the signature says everything. No comment needed.
pub fn config(&self) -> &Config {
    &self.config
}
```

**Universal defensive programming:**
```rust
// BAD - checking things that can't be wrong
pub(crate) fn process_entries(entries: &[Entry]) -> Vec<Output> {
    if entries.is_empty() {
        return Vec::new(); // unnecessary - the loop handles empty naturally
    }
    entries.iter().map(|e| transform(e)).collect()
}

// GOOD - trust the types, let the code be simple
pub(crate) fn process_entries(entries: &[Entry]) -> Vec<Output> {
    entries.iter().map(|e| transform(e)).collect()
}
```

**Getter/setter proliferation (Java-in-Rust):**
```rust
// BAD - no invariant to protect, just ceremony
impl Config {
    pub fn port(&self) -> u16 { self.port }
    pub fn set_port(&mut self, port: u16) { self.port = port; }
}

// GOOD - if there's no invariant, pub field is simpler and more honest
pub struct Config {
    pub port: u16,
    pub host: String,
}
```

**Stringly-typed APIs:**
```rust
// BAD - can swap name and email by accident
fn create_user(name: &str, email: &str, role: &str) -> Result<User>

// GOOD - the compiler prevents argument confusion
fn create_user(name: Username, email: Email, role: Role) -> Result<User>
```

**Returning bool where Result/Option belongs:**
```rust
// BAD - caller gets no information about what went wrong
fn is_valid(&self) -> bool

// GOOD - caller gets proof of validity in the type
fn validate(self) -> Result<ValidConfig, ValidationError>
```

### Style Examples File

The single most effective technique for getting AI to match your style: include 2-3 exemplary functions in a project-local reference file (e.g. `<project>/.claude/style-examples.rs` or anywhere referenced from CLAUDE.md). LLMs are pattern matchers. Showing a 30-line function that embodies your style teaches more than 30 lines of rules.

Reference it from project CLAUDE.md: "For code style, see `style-examples.rs` and match that style."

Select examples that demonstrate:
1. Flat control flow with `let-else` and `?`
2. Iterator chains at the right complexity level
3. Error handling with context (`.context("what we were doing")`)
4. Type-driven design (newtypes, parse-don't-validate)
5. The right amount of commenting (almost none, except WHY)

Update the examples when your style evolves. Stale examples teach the wrong style.

### What the Lints Handle (don't duplicate in CLAUDE.md)

The elegance lints in Section 1 already enforce these - no need for CLAUDE.md rules:
- `let-else` over nested matching (`manual_let_else`)
- `.copied()` over `.cloned()` for Copy types (`cloned_instead_of_copied`)
- Inlined format args (`uninlined_format_args`)
- Redundant else after return (`redundant_else`)
- Honest return types (`unnecessary_wraps`)
- Pass by reference when not consuming (`needless_pass_by_value`)
- Unreachable pub items (`unreachable_pub`)

CLAUDE.md should focus on what lints CANNOT catch: comment quality, abstraction level, type design, API aesthetics.

</details>

---

## Setup Checklist

<details>
<summary>Setup Checklist</summary>

When starting a new Rust project, apply in order:

1. [ ] Add `[lints.clippy]` and `[lints.rust]` to Cargo.toml (use CLI variant if applicable)
2. [ ] Create `clippy.toml` at project root with msrv + thresholds
3. [ ] Create `.cargo/config.toml` with aliases including `cov` (and MSVC target on Windows)
4. [ ] Add `General(String)` variant to error enum + manual `From` impls for third-party crates
5. [ ] Add cargo-husky to `[dev-dependencies]` with user-hooks
6. [ ] Create `.cargo-husky/hooks/pre-commit` (uses nextest)
7. [ ] Create `.cargo-husky/hooks/pre-push` (coverage gate: `cargo llvm-cov nextest --fail-under-lines 80`)
8. [ ] Run `cargo test` once to install hooks
9. [ ] Create `deny.toml` with license/advisory policy
10. [ ] Add `[package.metadata.cargo-machete]` if false positives exist
11. [ ] Add `proptest` and `insta` to `[dev-dependencies]`
12. [ ] Create `.config/nextest.toml` with leak-timeout and slow-timeout
13. [ ] Create `.config/insta.yaml` with `require_full_match: true`
14. [ ] Structure project following Section 19 (small modules, explicit re-exports, concrete types)
15. [ ] Add Rust anti-pattern rules to project CLAUDE.md (Section 20: clone policy, shared state, async)
16. [ ] Add testing rules to project CLAUDE.md (Section 17: test-first, forbidden patterns)
17. [ ] Create `.claude/settings.json` with permissions (include all cargo tool commands)
18. [ ] Create `.claude/rules/` with one file per module (include dependency boundaries)
19. [ ] Add code style rules to project CLAUDE.md (Section 23: no slop, trust types, comments=WHY)
20. [ ] Write project CLAUDE.md (lean router pattern, under 80 lines, front-load critical rules)
21. [ ] Add 2-3 exemplary functions in your style to the project for the agent to reference (under `$KB_DIR/resources/` or project docs)
22. [ ] Wire a project-local `/lint` skill or pre-commit step (8-step pipeline)
23. [ ] Update .gitignore with Claude Code entries + `.cargo/config.toml`
22. [ ] Apply `pub(crate)` to all internal types
23. [ ] Add per-item `#[expect(dead_code, reason = "...")]` to stubs
24. [ ] Set `[profile.release]` with lto + strip + codegen-units
25. [ ] (Optional) Download Microsoft Rust Guidelines for agents to `$STRATA_HOME/reference/`
26. [ ] Verify: `cargo fmt && cargo lint && cargo ta && cargo cov && cargo machete && cargo deny check && cargo doc --no-deps`

</details>

---

## The Feedback Loop (Three-Layer Enforcement)

<details>
<summary>The Feedback Loop (Three-Layer Enforcement)</summary>

The setup implements three distinct enforcement layers. No single layer is sufficient - they complement each other:

**Layer 1: Advisory (CLAUDE.md + .claude/rules/)**
Intent, architecture, naming, anti-patterns. ~80-95% compliance per rule, degrades with rule count (see Section 22). This is the only layer that catches semantic intent ("use channels, not mutexes" or "this module must not import from that module").

**Layer 2: Deterministic (hooks)**
Cannot be bypassed (`--no-verify` denied in settings.json). Pre-commit: nextest + clippy + fmt. Pre-push: coverage gate. 100% reliable for what they check.

**Layer 3: Automated (linters + CI)**
Everything pattern-matchable: clippy's 800+ lints, cargo-deny supply chain, cargo-machete unused deps, cargo-mutants test quality. 100% reliable for covered patterns.

The full chain:

```
Write test first (TDD - red)
  -> Write implementation (green)
  -> cargo lint catches violations (clippy pedantic + deny rules)
  -> Fix violations
  -> #[expect] annotations error when expectations become unfulfilled
  -> Remove stale annotations (item is now live)
  -> Expand tests (proptest for pure functions, snapshots for complex output)
  -> cargo nextest run (leak detection + timeouts catch runaway tests)
  -> cargo machete catches unused dependencies
  -> cargo deny check catches license/advisory issues
  -> git commit triggers pre-commit hook (Layer 2)
  -> Hook re-runs nextest + clippy + fmt
  -> Commit blocked until everything passes
  -> git push triggers pre-push hook (Layer 2)
  -> Hook runs cargo llvm-cov nextest --fail-under-lines 80
  -> Push blocked until coverage threshold met
  -> CI runs cargo mutants --in-diff on changed files (Layer 3)
  -> Surviving mutants flagged for additional tests
```

An AI agent cannot bypass this chain without explicitly violating the deny list in settings.json (which Claude Code blocks). The compiler is the first reviewer, the pre-commit hook is the second, the coverage gate is the third, and mutation testing is the final check. No human review required - the toolchain IS the reviewer.

</details>

---

## Common Gotchas (Reference)

<details>
<summary>Common Gotchas (Reference)</summary>

Quick lookup for issues that come up during Rust AI-agent development:

| Issue | Symptom | Fix |
|-------|---------|-----|
| Windows GNU target | `dlltool.exe not found` | Add `target = "x86_64-pc-windows-msvc"` to `.cargo/config.toml` |
| Third-party `From` missing | `? requires From<crate::Error>` | Add manual `From` impl using `General(format!(...))` |
| Test output assertion | Test checks stdout but errors go to stderr | Use `assert_cmd`'s combined output or check stderr explicitly |
| `#[expect]` unfulfilled in tests | Warning only when compiling with `--test` | Accept it (only appears in test output, not clippy) |
| `cargo clippy --fix` incomplete | ~20% of pedantic issues need manual fixes | See Section 8 for the manual fix patterns |
| `needless_pass_by_value` cascade | Changing `String` to `&str` breaks call sites | Add `.as_deref()` at call sites, remove `ref` in patterns |
| TOML `[[array]]` as wiki-link | Scanner finds false crosslinks in .toml files | Exclude config file types from link scanning |
| Relative path resolution | `../INDEX.md` in `sub/RULES.md` resolves wrong | Resolve link targets relative to source file's parent, not project root |
| `format_push_string` | `s.push_str(&format!(...))` flagged | `use std::fmt::Write; let _ = writeln!(s, ...);` |
| Pre-commit hook PATH | `cargo: command not found` in hook | `export PATH="$HOME/.cargo/bin:$PATH"` in hook script |
| Coverage too slow in pre-commit | Build + instrumented run takes 45-120s | Put coverage in pre-push hook, not pre-commit. Pre-commit stays fast (nextest + clippy + fmt). |
| `cargo-llvm-cov` not on Windows | `llvm-profdata` not found | Install via `cargo install cargo-llvm-cov`. Requires `rustup component add llvm-tools-preview`. |
| proptest + `#[expect(dead_code)]` | Proptest macro generates code that triggers dead_code in some cases | Use `#[cfg_attr(not(test), expect(dead_code))]` on the struct, or move proptest to integration tests |
| insta snapshots in CI | New snapshots cause test failure | Set `INSTA_UPDATE=no` in CI. Locally, run `cargo insta review` to accept changes. |
| cargo-mutants timeout | Mutation testing hangs on infinite-loop mutants | Always use `--timeout 30` (seconds per mutant). Increase for slow integration tests. |
| AI writes tautological tests | Test mirrors implementation logic, always passes | CLAUDE.md rule: "Test behavior from the function's docstring, not by reading the implementation" |
| AI adds `.clone()` everywhere | Borrow checker errors disappear but code is non-idiomatic | CLAUDE.md clone policy (Section 20). No lint catches "should have restructured." |
| AI wraps everything in `Arc<Mutex<T>>` | Compiles but creates bottlenecks and deadlock risk | CLAUDE.md shared state rules. Prefer channels or `RwLock` when reads dominate. |
| AI uses `std::sync::Mutex` in async | Blocks tokio worker thread, causes stalls | Use `tokio::sync::Mutex`. Add async rules to CLAUDE.md (Section 20). |
| AI skips difficult methods | Function suspiciously short, missing edge cases | Use `/spec` with per-method steps. Write "implement ALL methods, do not skip or simplify." |
| AI produces deep generic signatures | `fn process<T: A + B + C, U: D + E>(...)` | Prefer concrete types. Introduce generics only with 2+ real implementations (Section 19). |
| Context degrades in long sessions | Agent starts ignoring rules, making inconsistent choices | Commit and restart. One feature per session. See Section 21. |
| First attempt is 95% wrong | Code doesn't work, agent seems confused | Normal. Budget for 3 iterations. First attempt builds context (Section 21). |
| Cross-file import errors pile up | E0433, E0432, E0425 in agent output | Structure with explicit re-exports in lib.rs/mod.rs (Section 19). |

</details>
