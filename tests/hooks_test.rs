mod common;

use assert_fs::prelude::*;
use std::fs;

#[test]
fn test_hooks_requires_git_repo() {
    let dir = common::temp_project();
    dir.child("strata.toml")
        .write_str(
            r#"
[project]
name = "test"
"#,
        )
        .unwrap();

    let result = std::process::Command::new(common::strata_bin())
        .args(["install-hooks"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    assert!(!result.status.success());
    let stderr = String::from_utf8_lossy(&result.stderr);
    assert!(
        stderr.contains("git") || stderr.contains("Not a git"),
        "Expected git error, got: {}",
        stderr
    );
}

#[test]
fn test_hooks_installs_pre_commit() {
    let dir = common::temp_project();
    dir.child("strata.toml")
        .write_str(
            r#"
[project]
name = "test"
"#,
        )
        .unwrap();

    // Create a fake .git directory
    dir.child(".git/hooks").create_dir_all().unwrap();

    let result = std::process::Command::new(common::strata_bin())
        .args(["install-hooks"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    assert!(
        result.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&result.stderr)
    );

    let hook_path = dir.child(".git/hooks/pre-commit");
    assert!(hook_path.path().exists());

    let content = fs::read_to_string(hook_path.path()).unwrap();
    assert!(content.contains("strata check"));
}
