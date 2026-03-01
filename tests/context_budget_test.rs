#![expect(clippy::unwrap_used, reason = "test code - unwrap is acceptable")]
#![expect(clippy::expect_used, reason = "test code - expect is acceptable")]

mod common;

use assert_fs::prelude::*;

fn setup_project(dir: &assert_fs::TempDir) {
    dir.child("strata.toml")
        .write_str(
            r#"
[project]
name = "test"

[[project.domains]]
name = "Core"
prefix = "01"
"#,
        )
        .unwrap();
    dir.child("INDEX.md")
        .write_str("# Index\n\n| File | Description |\n|------|-------------|\n")
        .unwrap();
    dir.child("01-Core").create_dir_all().unwrap();
    dir.child("01-Core/RULES.md")
        .write_str("# Rules: Core\n\n## Purpose\nCore logic.\n\n## Boundaries\n- Only core.\n")
        .unwrap();
}

#[test]
fn test_context_budget_oversized_project_md() {
    let dir = common::temp_project();
    setup_project(&dir);

    // Write an oversized PROJECT.md (>3000 chars default budget)
    let big_content = "# Project\n\n".to_string() + &"x".repeat(3500);
    dir.child("PROJECT.md").write_str(&big_content).unwrap();

    let result = std::process::Command::new(common::strata_bin())
        .args(["lint", "--rule", "context-budget"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    let stdout = String::from_utf8_lossy(&result.stdout);
    assert!(
        stdout.contains("context-budget"),
        "Expected context-budget warning, got: {stdout}"
    );
    assert!(
        stdout.contains("PROJECT.md"),
        "Expected PROJECT.md in output, got: {stdout}"
    );
}

#[test]
fn test_context_budget_undersized_project_md() {
    let dir = common::temp_project();
    setup_project(&dir);

    // Write a short PROJECT.md (under 3000 chars)
    dir.child("PROJECT.md")
        .write_str("# Test Project\n\nA small project.\n")
        .unwrap();

    let result = std::process::Command::new(common::strata_bin())
        .args(["lint", "--rule", "context-budget"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    let stdout = String::from_utf8_lossy(&result.stdout);
    assert!(
        !stdout.contains("context-budget"),
        "Should have no context-budget warnings, got: {stdout}"
    );
}

#[test]
fn test_context_budget_custom_budget_override() {
    let dir = common::temp_project();

    // Set a very small custom budget
    dir.child("strata.toml")
        .write_str(
            r#"
[project]
name = "test"

[[project.domains]]
name = "Core"
prefix = "01"

[context]
project_budget = 50
"#,
        )
        .unwrap();
    dir.child("PROJECT.md")
        .write_str("# Test Project\n\nThis project has more than 50 characters of content.\n")
        .unwrap();
    dir.child("INDEX.md")
        .write_str("# Index\n\n| File | Description |\n|------|-------------|\n")
        .unwrap();
    dir.child("01-Core").create_dir_all().unwrap();
    dir.child("01-Core/RULES.md")
        .write_str("# Rules: Core\n\n## Purpose\nCore logic.\n\n## Boundaries\n- Only core.\n")
        .unwrap();

    let result = std::process::Command::new(common::strata_bin())
        .args(["lint", "--rule", "context-budget"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    let stdout = String::from_utf8_lossy(&result.stdout);
    assert!(
        stdout.contains("context-budget"),
        "Custom budget of 50 should trigger warning, got: {stdout}"
    );
    assert!(
        stdout.contains("budget is 50"),
        "Should show custom budget value, got: {stdout}"
    );
}

#[test]
fn test_context_budget_disableable() {
    let dir = common::temp_project();

    dir.child("strata.toml")
        .write_str(
            r#"
[project]
name = "test"

[[project.domains]]
name = "Core"
prefix = "01"

[lint]
disable = ["context-budget"]
"#,
        )
        .unwrap();
    // Oversized PROJECT.md
    let big_content = "# Project\n\n".to_string() + &"x".repeat(3500);
    dir.child("PROJECT.md").write_str(&big_content).unwrap();
    dir.child("INDEX.md")
        .write_str("# Index\n\n| File | Description |\n|------|-------------|\n")
        .unwrap();
    dir.child("01-Core").create_dir_all().unwrap();
    dir.child("01-Core/RULES.md")
        .write_str("# Rules: Core\n\n## Purpose\nCore logic.\n\n## Boundaries\n- Only core.\n")
        .unwrap();

    let result = std::process::Command::new(common::strata_bin())
        .args(["lint"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    let stdout = String::from_utf8_lossy(&result.stdout);
    assert!(
        !stdout.contains("context-budget"),
        "Disabled rule should not appear, got: {stdout}"
    );
}
