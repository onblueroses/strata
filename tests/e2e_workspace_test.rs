#![expect(clippy::unwrap_used, reason = "test code - unwrap is acceptable")]
#![expect(clippy::expect_used, reason = "test code - expect is acceptable")]

mod common;

use assert_cmd::Command;
use assert_fs::prelude::*;
use predicates::prelude::*;

/// Full workspace manager e2e test:
/// init --preset full -> session start -> spec new -> generate --target claude -> lint
#[test]
fn test_workspace_manager_full_workflow() {
    let dir = common::temp_project();
    let dir_path = dir.path().to_str().unwrap();

    // 1. Init with full preset
    Command::new(common::strata_bin())
        .args([
            "init",
            "--name",
            "test-workspace",
            "--domains",
            "Core,Docs",
            "--path",
            dir_path,
            "--preset",
            "full",
        ])
        .assert()
        .success()
        .stdout(predicate::str::contains("full preset"));

    // Verify full preset scaffolding
    assert!(dir.path().join("strata.toml").exists());
    assert!(dir.path().join("PROJECT.md").exists());
    assert!(dir.path().join("INDEX.md").exists());
    assert!(dir.path().join("MEMORY.md").exists());
    assert!(dir.path().join(".strata/hooks/session-start.sh").exists());
    assert!(dir.path().join(".strata/hooks/session-stop.sh").exists());
    assert!(dir.path().join(".strata/hooks/pre-compact.sh").exists());
    assert!(dir.path().join(".strata/specs").is_dir());
    assert!(dir.path().join(".strata/sessions").is_dir());
    assert!(dir.path().join("skills/review/SKILL.md").exists());
    assert!(dir.path().join("skills/commit/SKILL.md").exists());
    assert!(dir.path().join("skills/verify/SKILL.md").exists());
    assert!(dir.path().join("references/code-quality.md").exists());
    assert!(dir.path().join("references/skill-design.md").exists());

    // 2. Session start
    Command::new(common::strata_bin())
        .args(["session", "start", "--name", "test-session"])
        .current_dir(dir.path())
        .assert()
        .success()
        .stdout(predicate::str::contains("Session started"));

    // Verify current-session marker
    assert!(dir.path().join(".strata/current-session").exists());

    // Verify daily note created
    let sessions_dir = dir.path().join(".strata/sessions");
    let entries: Vec<_> = std::fs::read_dir(&sessions_dir)
        .unwrap()
        .flatten()
        .collect();
    assert!(!entries.is_empty(), "Daily note should be created");

    // 3. Spec new
    Command::new(common::strata_bin())
        .args(["spec", "new", "test-feature", "--session", "abc12345"])
        .current_dir(dir.path())
        .assert()
        .success()
        .stdout(predicate::str::contains("Created spec"));

    assert!(dir.path().join(".strata/specs/test-feature.md").exists());

    // 4. Spec list
    Command::new(common::strata_bin())
        .args(["spec", "list"])
        .current_dir(dir.path())
        .assert()
        .success()
        .stdout(predicate::str::contains("test-feature"));

    // 5. Spec status
    Command::new(common::strata_bin())
        .args(["spec", "status", "test-feature"])
        .current_dir(dir.path())
        .assert()
        .success();

    // 6. Generate with --target claude
    Command::new(common::strata_bin())
        .args(["generate", "--target", "claude"])
        .current_dir(dir.path())
        .assert()
        .success()
        .stdout(predicate::str::contains("CLAUDE.md"));

    assert!(dir.path().join(".strata/context.md").exists());
    assert!(dir.path().join("CLAUDE.md").exists());

    let claude_content = std::fs::read_to_string(dir.path().join("CLAUDE.md")).unwrap();
    assert!(claude_content.contains("test-workspace"));

    // 7. Generate with --skills
    Command::new(common::strata_bin())
        .args(["generate", "--skills"])
        .current_dir(dir.path())
        .assert()
        .success();

    // 8. Lint should run clean (no errors)
    Command::new(common::strata_bin())
        .args(["lint"])
        .current_dir(dir.path())
        .assert()
        .success();

    // 9. Session list
    Command::new(common::strata_bin())
        .args(["session", "list"])
        .current_dir(dir.path())
        .assert()
        .success();

    // 10. Session save
    Command::new(common::strata_bin())
        .args(["session", "save"])
        .current_dir(dir.path())
        .assert()
        .success()
        .stdout(predicate::str::contains("Context saved"));

    // 11. Spec complete
    Command::new(common::strata_bin())
        .args(["spec", "complete", "test-feature"])
        .current_dir(dir.path())
        .assert()
        .success()
        .stdout(predicate::str::contains("complete"));

    let spec_content =
        std::fs::read_to_string(dir.path().join(".strata/specs/test-feature.md")).unwrap();
    assert!(spec_content.contains("Status: `complete`"));
}

/// Test minimal preset produces only basic structure.
#[test]
fn test_minimal_preset_no_hooks() {
    let dir = common::temp_project();
    let dir_path = dir.path().to_str().unwrap();

    Command::new(common::strata_bin())
        .args([
            "init",
            "--name",
            "minimal-project",
            "--domains",
            "Core",
            "--path",
            dir_path,
            "--preset",
            "minimal",
        ])
        .assert()
        .success();

    assert!(dir.path().join("strata.toml").exists());
    assert!(dir.path().join("PROJECT.md").exists());
    // Minimal should NOT have hooks, skills, references, or memory
    assert!(!dir.path().join(".strata/hooks").exists());
    assert!(!dir.path().join("skills/review").exists());
    assert!(!dir.path().join("MEMORY.md").exists());
    assert!(!dir.path().join("references").exists());
}

// --- Monorepo / workspace tests ---

fn workspace_root_toml(members: &[&str]) -> String {
    let members_str = members
        .iter()
        .map(|m| format!("\"{m}\""))
        .collect::<Vec<_>>()
        .join(", ");
    format!("[workspace]\nmembers = [{members_str}]\n")
}

fn minimal_member_toml(name: &str) -> String {
    format!("[project]\nname = \"{name}\"\n")
}

fn make_valid_member(dir: &assert_fs::TempDir, member: &str) {
    dir.child(format!("{member}/strata.toml"))
        .write_str(&minimal_member_toml(member))
        .unwrap();
    dir.child(format!("{member}/PROJECT.md"))
        .write_str("# Project\ndescription: A test project")
        .unwrap();
    dir.child(format!("{member}/INDEX.md"))
        .write_str("# Index\n\n| File | Description |\n|------|-------------|\n")
        .unwrap();
}

/// Workspace check: both members pass -> output contains per-member [name] lines, exit 0.
#[test]
fn test_monorepo_check_all_pass() {
    let dir = common::temp_project();

    dir.child("strata.toml")
        .write_str(&workspace_root_toml(&["alpha", "beta"]))
        .unwrap();

    make_valid_member(&dir, "alpha");
    make_valid_member(&dir, "beta");

    Command::new(common::strata_bin())
        .args(["check"])
        .current_dir(dir.path())
        .assert()
        .success()
        .stdout(predicate::str::contains("[alpha]"))
        .stdout(predicate::str::contains("[beta]"));
}

/// Workspace check: one member is missing required files -> exit 1, both members shown.
#[test]
fn test_monorepo_check_partial_failure() {
    let dir = common::temp_project();

    dir.child("strata.toml")
        .write_str(&workspace_root_toml(&["alpha", "beta"]))
        .unwrap();

    make_valid_member(&dir, "alpha");

    // beta: only strata.toml, missing PROJECT.md and INDEX.md
    dir.child("beta/strata.toml")
        .write_str(&minimal_member_toml("beta"))
        .unwrap();

    let output = Command::new(common::strata_bin())
        .args(["check"])
        .current_dir(dir.path())
        .output()
        .expect("strata failed");

    // ui::success writes to stdout; ui::error writes to stderr
    let stdout = String::from_utf8_lossy(&output.stdout);
    let stderr = String::from_utf8_lossy(&output.stderr);
    let combined = format!("{stdout}{stderr}");
    assert!(
        combined.contains("[alpha]"),
        "Missing [alpha] in combined output: {combined}"
    );
    assert!(
        combined.contains("[beta]"),
        "Missing [beta] in combined output: {combined}"
    );
    assert!(
        !output.status.success(),
        "Expected non-zero exit when a member fails"
    );
}

/// Workspace lint: custom rule in one member fires with member-prefixed location in JSON output.
#[test]
fn test_monorepo_lint_member_prefix_in_json() {
    let dir = common::temp_project();

    dir.child("strata.toml")
        .write_str(&workspace_root_toml(&["alpha", "beta"]))
        .unwrap();

    make_valid_member(&dir, "alpha");
    make_valid_member(&dir, "beta");

    // Add a custom rule to beta that will fire (README.md is absent)
    let beta_toml = format!(
        "{}\n[[custom_rules]]\nname = \"require-readme\"\nseverity = \"warning\"\ncheck = \"file_exists\"\nglob = \"README.md\"\nmessage = \"README.md is missing\"\n",
        minimal_member_toml("beta")
    );
    dir.child("beta/strata.toml").write_str(&beta_toml).unwrap();

    let output = Command::new(common::strata_bin())
        .args(["lint", "--format", "json"])
        .current_dir(dir.path())
        .output()
        .expect("strata failed");

    let json: serde_json::Value = serde_json::from_slice(&output.stdout).expect("invalid json");

    let locs: Vec<&str> = json
        .as_array()
        .unwrap()
        .iter()
        .filter_map(|d| d["location"].as_str())
        .collect();

    // beta diagnostic location should be prefixed with "beta/"
    assert!(
        locs.iter().any(|l| l.starts_with("beta/")),
        "Expected beta/-prefixed location, got: {locs:?}"
    );
    // alpha has no custom rules and all structure checks pass - no alpha/ prefixed diagnostics
    assert!(
        !locs.iter().any(|l| l.starts_with("alpha/")),
        "Unexpected alpha/-prefixed location: {locs:?}"
    );
}

/// Test standard preset has hooks and skills but not specs/sessions dirs.
#[test]
fn test_standard_preset() {
    let dir = common::temp_project();
    let dir_path = dir.path().to_str().unwrap();

    Command::new(common::strata_bin())
        .args([
            "init",
            "--name",
            "standard-project",
            "--domains",
            "Core",
            "--path",
            dir_path,
            "--preset",
            "standard",
        ])
        .assert()
        .success();

    assert!(dir.path().join(".strata/hooks/session-start.sh").exists());
    assert!(dir.path().join("skills/review/SKILL.md").exists());
    assert!(dir.path().join("skills/verify/SKILL.md").exists());
    assert!(dir.path().join("MEMORY.md").exists());
    assert!(dir.path().join("references/code-quality.md").exists());
    assert!(dir.path().join("references/skill-design.md").exists());
    // Standard should NOT have specs/sessions dirs
    assert!(!dir.path().join(".strata/specs").exists());
    assert!(!dir.path().join(".strata/sessions").exists());
}
