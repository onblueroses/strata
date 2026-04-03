#![expect(clippy::unwrap_used, reason = "test code - unwrap is acceptable")]
#![expect(clippy::expect_used, reason = "test code - expect is acceptable")]

mod common;

use assert_fs::prelude::*;

#[test]
fn test_config_not_found() {
    let dir = common::temp_project();
    let result = std::process::Command::new(common::strata_bin())
        .args(["check"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    assert!(!result.status.success());
    let stderr = String::from_utf8_lossy(&result.stderr);
    assert!(
        stderr.contains("Not a strata project") || stderr.contains("strata.toml"),
        "Expected 'Not a strata project' error, got: {stderr}"
    );
}

#[test]
fn test_config_minimal_toml() {
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
    dir.child("INDEX.md")
        .write_str("# Index\n\n| File | Description |\n|------|-------------|\n")
        .unwrap();

    let result = std::process::Command::new(common::strata_bin())
        .args(["check"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    // Should pass - minimal project with no domains
    assert!(
        result.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&result.stderr)
    );
}
