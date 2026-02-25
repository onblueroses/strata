mod common;

use assert_fs::prelude::*;
use std::fs;

#[test]
fn test_init_non_interactive() {
    let dir = common::temp_project();

    let result = std::process::Command::new(common::strata_bin())
        .args([
            "init",
            "--name",
            "test-project",
            "--domains",
            "Core,Docs,Scripts",
            "--path",
        ])
        .arg(dir.path())
        .output()
        .expect("Failed to run strata");

    let stdout = String::from_utf8_lossy(&result.stdout);
    let stderr = String::from_utf8_lossy(&result.stderr);
    assert!(
        result.status.success(),
        "stdout: {}\nstderr: {}",
        stdout,
        stderr
    );

    // Check strata.toml exists
    assert!(dir.child("strata.toml").path().exists());

    // Check PROJECT.md exists
    assert!(dir.child("PROJECT.md").path().exists());

    // Check INDEX.md exists
    assert!(dir.child("INDEX.md").path().exists());

    // Check domain directories
    assert!(dir.child("01-Core").path().exists());
    assert!(dir.child("02-Docs").path().exists());
    assert!(dir.child("03-Scripts").path().exists());

    // Check RULES.md in each domain
    assert!(dir.child("01-Core/RULES.md").path().exists());
    assert!(dir.child("02-Docs/RULES.md").path().exists());
    assert!(dir.child("03-Scripts/RULES.md").path().exists());

    // Check .strata directory
    assert!(dir.child(".strata").path().exists());

    // Check config directory
    assert!(dir.child("config").path().exists());

    // Check archive directory
    assert!(dir.child("archive").path().exists());

    // Verify strata.toml content
    let config = fs::read_to_string(dir.child("strata.toml").path()).unwrap();
    assert!(config.contains("test-project"));
    assert!(config.contains("Core"));
    assert!(config.contains("Docs"));
    assert!(config.contains("Scripts"));
}

#[test]
fn test_init_already_initialized() {
    let dir = common::temp_project();

    // First init
    let result = std::process::Command::new(common::strata_bin())
        .args([
            "init",
            "--name",
            "test-project",
            "--domains",
            "Core",
            "--path",
        ])
        .arg(dir.path())
        .output()
        .expect("Failed to run strata");
    assert!(result.status.success());

    // Second init should fail
    let result = std::process::Command::new(common::strata_bin())
        .args([
            "init",
            "--name",
            "test-project",
            "--domains",
            "Core",
            "--path",
        ])
        .arg(dir.path())
        .output()
        .expect("Failed to run strata");
    assert!(!result.status.success());

    let stderr = String::from_utf8_lossy(&result.stderr);
    assert!(
        stderr.contains("already initialized"),
        "Expected 'already initialized' error, got: {}",
        stderr
    );
}

#[test]
fn test_init_creates_valid_project() {
    let dir = common::temp_project();

    // Init
    let result = std::process::Command::new(common::strata_bin())
        .args([
            "init",
            "--name",
            "valid-project",
            "--domains",
            "Core,Docs",
            "--path",
        ])
        .arg(dir.path())
        .output()
        .expect("Failed to run strata");
    assert!(result.status.success());

    // Check should pass on freshly initialized project
    let result = std::process::Command::new(common::strata_bin())
        .args(["check"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    let stdout = String::from_utf8_lossy(&result.stdout);
    let stderr = String::from_utf8_lossy(&result.stderr);
    assert!(
        result.status.success(),
        "Check failed on fresh project:\nstdout: {}\nstderr: {}",
        stdout,
        stderr
    );
}
