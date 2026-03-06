#![expect(clippy::unwrap_used, reason = "test code - unwrap is acceptable")]
#![expect(clippy::expect_used, reason = "test code - expect is acceptable")]

mod common;

use assert_cmd::Command;
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
    // Minimal should NOT have hooks or skills
    assert!(!dir.path().join(".strata/hooks").exists());
    assert!(!dir.path().join("skills/review").exists());
    assert!(!dir.path().join("MEMORY.md").exists());
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
    assert!(dir.path().join("MEMORY.md").exists());
    // Standard should NOT have specs/sessions dirs
    assert!(!dir.path().join(".strata/specs").exists());
    assert!(!dir.path().join(".strata/sessions").exists());
}
