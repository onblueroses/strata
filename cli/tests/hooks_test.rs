#![expect(clippy::unwrap_used, reason = "test code - unwrap is acceptable")]
#![expect(clippy::expect_used, reason = "test code - expect is acceptable")]

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
        "Expected git error, got: {stderr}"
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

#[test]
fn test_hooks_pre_commit_enforcement_enabled() {
    let dir = common::temp_project();
    dir.child("strata.toml")
        .write_str(
            r#"
[project]
name = "test"

[hooks]
enforce = true
"#,
        )
        .unwrap();
    dir.child(".git/hooks").create_dir_all().unwrap();

    let result = std::process::Command::new(common::strata_bin())
        .args(["install-hooks"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    assert!(result.status.success());

    let content = fs::read_to_string(dir.child(".git/hooks/pre-commit").path()).unwrap();
    assert!(
        content.contains("BLOCKED"),
        "Enforcement hook should contain BLOCKED text"
    );
    assert!(
        content.contains("review-passed"),
        "Should check for review marker"
    );
}

#[test]
fn test_hooks_pre_commit_enforcement_disabled() {
    let dir = common::temp_project();
    dir.child("strata.toml")
        .write_str(
            r#"
[project]
name = "test"

[hooks]
enforce = false
"#,
        )
        .unwrap();
    dir.child(".git/hooks").create_dir_all().unwrap();

    let result = std::process::Command::new(common::strata_bin())
        .args(["install-hooks"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    assert!(result.status.success());

    let content = fs::read_to_string(dir.child(".git/hooks/pre-commit").path()).unwrap();
    assert!(
        !content.contains("BLOCKED"),
        "Non-enforcement hook should not contain BLOCKED text"
    );
    assert!(
        content.contains("NOTE"),
        "Should have a warning note instead"
    );
}

#[test]
fn test_init_standard_creates_enforcement_hooks() {
    let dir = common::temp_project();

    let result = std::process::Command::new(common::strata_bin())
        .args([
            "init",
            "--name",
            "test-project",
            "--domains",
            "Core",
            "--preset",
            "standard",
        ])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    assert!(
        result.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&result.stderr)
    );

    // Session-stop hook should have enforcement
    let stop_hook = dir
        .child(".strata/hooks/session-stop.sh")
        .path()
        .to_path_buf();
    assert!(stop_hook.exists(), "session-stop.sh should exist");
    let stop_content = fs::read_to_string(&stop_hook).unwrap();
    assert!(
        stop_content.contains("BLOCKED"),
        "session-stop should enforce verification"
    );

    // Claude Code settings.json should be generated
    let settings = dir.child(".claude/settings.json").path().to_path_buf();
    assert!(settings.exists(), ".claude/settings.json should exist");
    let settings_content = fs::read_to_string(&settings).unwrap();
    assert!(
        settings_content.contains("session-stop.sh"),
        "settings.json should wire the stop hook"
    );
}

#[test]
fn test_init_standard_no_enforce_flag() {
    let dir = common::temp_project();

    let result = std::process::Command::new(common::strata_bin())
        .args([
            "init",
            "--name",
            "test-project",
            "--domains",
            "Core",
            "--preset",
            "standard",
            "--no-enforce",
        ])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    assert!(
        result.status.success(),
        "stderr: {}",
        String::from_utf8_lossy(&result.stderr)
    );

    // Session-stop hook should NOT have enforcement
    let stop_hook = dir
        .child(".strata/hooks/session-stop.sh")
        .path()
        .to_path_buf();
    let stop_content = fs::read_to_string(&stop_hook).unwrap();
    assert!(
        !stop_content.contains("BLOCKED"),
        "session-stop should NOT enforce when --no-enforce is used"
    );
    assert!(
        stop_content.contains("NOTE"),
        "should have warning note instead of enforcement"
    );
}
