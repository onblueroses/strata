mod common;

use assert_fs::prelude::*;

/// Combine stdout and stderr for checking output.
fn combined_output(result: &std::process::Output) -> String {
    let stdout = String::from_utf8_lossy(&result.stdout);
    let stderr = String::from_utf8_lossy(&result.stderr);
    format!("{}{}", stdout, stderr)
}

#[test]
fn test_check_missing_index() {
    let dir = common::temp_project();
    dir.child("strata.toml")
        .write_str(
            r#"
[project]
name = "test"
"#,
        )
        .unwrap();
    dir.child("PROJECT.md").write_str("# Test").unwrap();

    let result = std::process::Command::new(common::strata_bin())
        .args(["check"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    assert!(!result.status.success());
    let output = combined_output(&result);
    assert!(
        output.contains("INDEX.md"),
        "Expected INDEX.md mention in: {}",
        output
    );
}

#[test]
fn test_check_missing_project_md() {
    let dir = common::temp_project();
    dir.child("strata.toml")
        .write_str(
            r#"
[project]
name = "test"
"#,
        )
        .unwrap();
    dir.child("INDEX.md")
        .write_str("# Index\n\n| File | Description |\n|------|-------------|\n")
        .unwrap();

    let result = std::process::Command::new(common::strata_bin())
        .args(["check"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    assert!(!result.status.success());
    let output = combined_output(&result);
    assert!(
        output.contains("PROJECT.md"),
        "Expected PROJECT.md mention in: {}",
        output
    );
}

#[test]
fn test_check_missing_rules_md() {
    let dir = common::temp_project();
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
    dir.child("PROJECT.md").write_str("# Test").unwrap();
    dir.child("INDEX.md")
        .write_str("# Index\n\n| File | Description |\n|------|-------------|\n")
        .unwrap();
    dir.child("01-Core").create_dir_all().unwrap();

    let result = std::process::Command::new(common::strata_bin())
        .args(["check"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    assert!(!result.status.success());
    let output = combined_output(&result);
    assert!(
        output.contains("01-Core/RULES.md"),
        "Expected RULES.md mention in: {}",
        output
    );
}

#[test]
fn test_check_passes_valid_project() {
    let dir = common::temp_project();
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
    dir.child("PROJECT.md").write_str("# Test").unwrap();
    dir.child("INDEX.md")
        .write_str("# Index\n\n| File | Description |\n|------|-------------|\n")
        .unwrap();
    dir.child("01-Core").create_dir_all().unwrap();
    dir.child("01-Core/RULES.md")
        .write_str("# Rules: Core\n\n## Purpose\nCore logic.\n\n## Boundaries\n- Only core.\n")
        .unwrap();

    let result = std::process::Command::new(common::strata_bin())
        .args(["check"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    assert!(
        result.status.success(),
        "stdout: {}\nstderr: {}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );
}
