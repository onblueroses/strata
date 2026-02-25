mod common;

use assert_fs::prelude::*;
use std::fs;

/// End-to-end test: init -> check -> lint -> break -> check fails -> fix -> check passes
#[test]
fn test_full_workflow() {
    let dir = common::temp_project();
    let bin = common::strata_bin();

    // Step 1: Init
    let result = std::process::Command::new(&bin)
        .args([
            "init",
            "--name",
            "e2e-test",
            "--domains",
            "Core,Docs",
            "--path",
        ])
        .arg(dir.path())
        .output()
        .expect("init failed");
    assert!(
        result.status.success(),
        "init: {}",
        String::from_utf8_lossy(&result.stderr)
    );

    // Step 2: Check passes on fresh project
    let result = std::process::Command::new(&bin)
        .args(["check"])
        .current_dir(dir.path())
        .output()
        .expect("check failed");
    assert!(
        result.status.success(),
        "check on fresh: {}",
        String::from_utf8_lossy(&result.stderr)
    );

    // Step 3: Lint runs (may have info-level findings)
    let result = std::process::Command::new(&bin)
        .args(["lint"])
        .current_dir(dir.path())
        .output()
        .expect("lint failed");
    // Lint should pass (no errors) on fresh project
    assert!(
        result.status.success(),
        "lint on fresh: {}",
        String::from_utf8_lossy(&result.stderr)
    );

    // Step 4: Break the project - remove a RULES.md
    fs::remove_file(dir.child("02-Docs/RULES.md").path()).unwrap();

    // Step 5: Check should now fail
    let result = std::process::Command::new(&bin)
        .args(["check"])
        .current_dir(dir.path())
        .output()
        .expect("check failed");
    assert!(!result.status.success(), "check should fail after breaking");

    // Step 6: Add an unindexed file
    dir.child("01-Core/notes.md")
        .write_str("# Notes\n\nSome notes.\n")
        .unwrap();

    // Step 7: Fix should repair
    let result = std::process::Command::new(&bin)
        .args(["fix"])
        .current_dir(dir.path())
        .output()
        .expect("fix failed");
    assert!(
        result.status.success(),
        "fix: {}",
        String::from_utf8_lossy(&result.stderr)
    );

    // Verify RULES.md was regenerated
    assert!(dir.child("02-Docs/RULES.md").path().exists());

    // Verify unindexed file was added to INDEX.md
    let index = fs::read_to_string(dir.child("INDEX.md").path()).unwrap();
    assert!(
        index.contains("01-Core/notes.md"),
        "INDEX.md should contain notes.md"
    );

    // Step 8: Check should pass again
    let result = std::process::Command::new(&bin)
        .args(["check"])
        .current_dir(dir.path())
        .output()
        .expect("check failed");
    assert!(
        result.status.success(),
        "check after fix: {}",
        String::from_utf8_lossy(&result.stderr)
    );

    // Step 9: Install hooks (create fake .git dir)
    dir.child(".git/hooks").create_dir_all().unwrap();
    let result = std::process::Command::new(&bin)
        .args(["install-hooks"])
        .current_dir(dir.path())
        .output()
        .expect("hooks failed");
    assert!(
        result.status.success(),
        "hooks: {}",
        String::from_utf8_lossy(&result.stderr)
    );
    assert!(dir.child(".git/hooks/pre-commit").path().exists());

    // Step 10: JSON lint output
    let result = std::process::Command::new(&bin)
        .args(["lint", "--format", "json"])
        .current_dir(dir.path())
        .output()
        .expect("lint json failed");
    let stdout = String::from_utf8_lossy(&result.stdout);
    assert!(stdout.starts_with('['), "JSON output: {}", stdout);
}
