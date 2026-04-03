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
name = "update-test"

[[project.domains]]
name = "Core"
prefix = "01"
"#,
        )
        .unwrap();
    dir.child("PROJECT.md")
        .write_str("# Update Test\n\nA project for testing update.\n")
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
fn test_update_no_prior_generation() {
    let dir = common::temp_project();
    setup_project(&dir);

    let result = std::process::Command::new(common::strata_bin())
        .args(["update"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    assert!(
        result.status.success(),
        "update should succeed without prior generation: {}",
        String::from_utf8_lossy(&result.stderr)
    );
    // Should behave like a full generate
    assert!(
        dir.child(".strata/context.md").path().exists(),
        "context.md should be created"
    );
    assert!(
        dir.child(".strata/state.json").path().exists(),
        "state.json should be created"
    );
}

#[test]
fn test_update_no_changes() {
    let dir = common::temp_project();
    setup_project(&dir);

    // Generate first
    let gen_result = std::process::Command::new(common::strata_bin())
        .args(["generate"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata generate");
    assert!(gen_result.status.success());

    // Update without changes
    let result = std::process::Command::new(common::strata_bin())
        .args(["update"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata update");

    assert!(result.status.success());
    let stdout = String::from_utf8_lossy(&result.stdout);
    assert!(
        stdout.contains("up to date"),
        "Should report up to date: {stdout}"
    );
}

#[test]
fn test_update_after_source_change() {
    let dir = common::temp_project();
    setup_project(&dir);

    // Generate first
    let gen_result = std::process::Command::new(common::strata_bin())
        .args(["generate"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata generate");
    assert!(gen_result.status.success());

    let context_before = fs::read_to_string(dir.child(".strata/context.md").path()).unwrap();

    // Modify PROJECT.md
    fs::write(
        dir.child("PROJECT.md").path(),
        "# Update Test\n\nChanged purpose for testing.\n",
    )
    .unwrap();

    // Update should only write changed files
    let result = std::process::Command::new(common::strata_bin())
        .args(["update"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata update");

    assert!(result.status.success());
    let stdout = String::from_utf8_lossy(&result.stdout);
    assert!(
        stdout.contains("Updated"),
        "Should report updated files: {stdout}"
    );

    let context_after = fs::read_to_string(dir.child(".strata/context.md").path()).unwrap();
    assert_ne!(context_before, context_after, "context.md should change");
    assert!(
        context_after.contains("Changed purpose"),
        "Should reflect new content"
    );
}

#[test]
fn test_update_preserves_human_content() {
    let dir = common::temp_project();
    setup_project(&dir);

    // Generate first
    let gen_result = std::process::Command::new(common::strata_bin())
        .args(["generate"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata generate");
    assert!(gen_result.status.success());

    // Add human content above marker
    let context_path = dir.child(".strata/context.md").path().to_path_buf();
    let original = fs::read_to_string(&context_path).unwrap();
    let with_human = format!("My custom notes.\n\n{original}");
    fs::write(&context_path, &with_human).unwrap();

    // Modify source so update has something to regenerate
    fs::write(
        dir.child("PROJECT.md").path(),
        "# Update Test\n\nNew purpose.\n",
    )
    .unwrap();

    // Update
    let result = std::process::Command::new(common::strata_bin())
        .args(["update"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata update");

    assert!(result.status.success());

    let updated = fs::read_to_string(&context_path).unwrap();
    assert!(
        updated.contains("My custom notes"),
        "Human content should survive update"
    );
}

#[test]
fn test_update_then_diff_clean() {
    let dir = common::temp_project();
    setup_project(&dir);

    // Generate
    let gen_result = std::process::Command::new(common::strata_bin())
        .args(["generate"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata generate");
    assert!(gen_result.status.success());

    // Modify source
    fs::write(
        dir.child("PROJECT.md").path(),
        "# Update Test\n\nDifferent text.\n",
    )
    .unwrap();

    // Update
    let upd = std::process::Command::new(common::strata_bin())
        .args(["update"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata update");
    assert!(upd.status.success());

    // Diff should show "up to date"
    let diff = std::process::Command::new(common::strata_bin())
        .args(["diff"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata diff");
    assert!(diff.status.success());
    let stdout = String::from_utf8_lossy(&diff.stdout);
    assert!(
        stdout.contains("up to date"),
        "diff should be clean after update: {stdout}"
    );
}
