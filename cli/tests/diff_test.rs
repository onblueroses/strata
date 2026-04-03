#![expect(clippy::unwrap_used, reason = "test code - unwrap is acceptable")]
#![expect(clippy::expect_used, reason = "test code - expect is acceptable")]

mod common;

use assert_fs::prelude::*;
use std::fs;

fn setup_project(dir: &assert_fs::TempDir) {
    dir.child("strata.toml")
        .write_str(
            r#"
[project]
name = "diff-test"

[[project.domains]]
name = "Core"
prefix = "01"
"#,
        )
        .unwrap();
    dir.child("PROJECT.md")
        .write_str("# Diff Test\n\nA project for testing diff.\n")
        .unwrap();
    dir.child("INDEX.md")
        .write_str("# Index\n\n| File | Description |\n|------|-------------|\n")
        .unwrap();
    dir.child(".strata").create_dir_all().unwrap();
    dir.child("01-Core").create_dir_all().unwrap();
    dir.child("01-Core/RULES.md")
        .write_str("# Rules: Core\n\n## Purpose\nCore logic.\n\n## Boundaries\n- None.\n")
        .unwrap();
}

#[test]
fn test_diff_no_prior_generation() {
    let dir = common::temp_project();
    setup_project(&dir);

    let result = std::process::Command::new(common::strata_bin())
        .args(["diff"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    assert!(result.status.success());
    let stdout = String::from_utf8_lossy(&result.stdout);
    assert!(
        stdout.contains("No previous generation"),
        "Should show helpful message: {stdout}"
    );
}

#[test]
fn test_diff_no_changes_after_generate() {
    let dir = common::temp_project();
    setup_project(&dir);

    // Generate first
    let gen_result = std::process::Command::new(common::strata_bin())
        .args(["generate"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata generate");
    assert!(gen_result.status.success());

    // state.json should exist
    assert!(
        dir.child(".strata/state.json").path().exists(),
        "state.json should be created after generate"
    );

    // Diff should show no changes
    let diff_result = std::process::Command::new(common::strata_bin())
        .args(["diff"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata diff");
    assert!(diff_result.status.success());
    let stdout = String::from_utf8_lossy(&diff_result.stdout);
    assert!(
        stdout.contains("up to date"),
        "Should report up to date: {stdout}"
    );
}

#[test]
fn test_diff_detects_source_change() {
    let dir = common::temp_project();
    setup_project(&dir);

    // Generate
    let gen_result = std::process::Command::new(common::strata_bin())
        .args(["generate"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata generate");
    assert!(gen_result.status.success());

    // Modify a source file
    fs::write(
        dir.child("PROJECT.md").path(),
        "# Diff Test\n\nUpdated purpose text.\n",
    )
    .unwrap();

    // Diff should show changes
    let diff_result = std::process::Command::new(common::strata_bin())
        .args(["diff"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata diff");
    assert!(diff_result.status.success());
    let stdout = String::from_utf8_lossy(&diff_result.stdout);
    assert!(
        stdout.contains("modified"),
        "Should report modified files: {stdout}"
    );
    assert!(
        stdout.contains("would change"),
        "Should show change count: {stdout}"
    );
}

#[test]
fn test_diff_shows_content_lines() {
    let dir = common::temp_project();
    setup_project(&dir);

    // Generate to create state
    let gen_result = std::process::Command::new(common::strata_bin())
        .args(["generate"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata generate");
    assert!(gen_result.status.success());

    // Modify a source file so generated content changes
    fs::write(
        dir.child("PROJECT.md").path(),
        "# Diff Test\n\nUpdated purpose text.\n",
    )
    .unwrap();

    let diff_result = std::process::Command::new(common::strata_bin())
        .args(["diff"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata diff");
    assert!(diff_result.status.success());
    let stdout = String::from_utf8_lossy(&diff_result.stdout);
    // Diff content lines should appear (+ for added, - for removed)
    assert!(
        stdout.contains('+') || stdout.contains('-'),
        "Should show diff lines with +/- prefixes: {stdout}"
    );
}

#[test]
fn test_diff_clean_after_regeneration() {
    let dir = common::temp_project();
    setup_project(&dir);

    // Generate
    let gen1 = std::process::Command::new(common::strata_bin())
        .args(["generate"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata generate");
    assert!(gen1.status.success());

    // Modify source
    fs::write(
        dir.child("PROJECT.md").path(),
        "# Diff Test\n\nChanged again.\n",
    )
    .unwrap();

    // Regenerate
    let gen2 = std::process::Command::new(common::strata_bin())
        .args(["generate"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata generate");
    assert!(gen2.status.success());

    // Diff should be clean
    let diff_result = std::process::Command::new(common::strata_bin())
        .args(["diff"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata diff");
    assert!(diff_result.status.success());
    let stdout = String::from_utf8_lossy(&diff_result.stdout);
    assert!(
        stdout.contains("up to date"),
        "Should be clean after regeneration: {stdout}"
    );
}
