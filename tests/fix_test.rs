mod common;

use assert_fs::prelude::*;
use std::fs;

fn setup_project(dir: &assert_fs::TempDir) {
    dir.child("strata.toml")
        .write_str(
            r#"
[project]
name = "test"

[[project.domains]]
name = "Core"
prefix = "01"

[[project.domains]]
name = "Docs"
prefix = "02"
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
}

#[test]
fn test_fix_generates_missing_rules() {
    let dir = common::temp_project();
    setup_project(&dir);
    // 02-Docs has no RULES.md

    let result = std::process::Command::new(common::strata_bin())
        .args(["fix"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    assert!(result.status.success());

    // RULES.md should now exist
    assert!(
        dir.child("02-Docs/RULES.md").path().exists(),
        "fix should create missing RULES.md"
    );

    let content = fs::read_to_string(dir.child("02-Docs/RULES.md").path()).unwrap();
    assert!(content.contains("Rules: Docs"));
    assert!(content.contains("Purpose"));
    assert!(content.contains("Boundaries"));
}

#[test]
fn test_fix_dry_run() {
    let dir = common::temp_project();
    setup_project(&dir);
    // 02-Docs has no RULES.md

    let result = std::process::Command::new(common::strata_bin())
        .args(["fix", "--dry-run"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    assert!(result.status.success());

    // RULES.md should NOT exist (dry run)
    assert!(
        !dir.child("02-Docs/RULES.md").path().exists(),
        "dry-run should not create files"
    );

    let stdout = String::from_utf8_lossy(&result.stdout);
    assert!(stdout.contains("Would create"));
}

#[test]
fn test_fix_adds_unindexed_files() {
    let dir = common::temp_project();
    setup_project(&dir);
    dir.child("02-Docs").create_dir_all().unwrap();
    dir.child("02-Docs/RULES.md")
        .write_str("# Rules: Docs\n\n## Purpose\nDocs.\n\n## Boundaries\n- Only docs.\n")
        .unwrap();

    // Create an unindexed file
    dir.child("01-Core/guide.md")
        .write_str("# Guide\n\nSome guide content.\n")
        .unwrap();

    let result = std::process::Command::new(common::strata_bin())
        .args(["fix"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    assert!(result.status.success());

    let index = fs::read_to_string(dir.child("INDEX.md").path()).unwrap();
    assert!(
        index.contains("01-Core/guide.md"),
        "INDEX.md should contain the added file. Content: {}",
        index
    );
}
