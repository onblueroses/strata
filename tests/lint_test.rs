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
fn test_lint_rules_completeness_error() {
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
    // RULES.md without Purpose or Boundaries
    dir.child("01-Core/RULES.md")
        .write_str("# Rules: Core\n\nSome text without sections.\n")
        .unwrap();

    let result = std::process::Command::new(common::strata_bin())
        .args(["lint"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    assert!(!result.status.success());
    let combined = format!(
        "{}{}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );
    assert!(
        combined.contains("rules-completeness"),
        "Output: {combined}"
    );
    assert!(combined.contains("Purpose"), "Output: {combined}");
}

#[test]
fn test_lint_empty_folders_info() {
    let dir = common::temp_project();
    setup_project(&dir);
    // 01-Core has only RULES.md, no content files

    let result = std::process::Command::new(common::strata_bin())
        .args(["lint"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    // empty-folders is Info severity, should not cause failure
    let stdout = String::from_utf8_lossy(&result.stdout);
    assert!(stdout.contains("empty-folders") || result.status.success());
}

#[test]
fn test_lint_json_output() {
    let dir = common::temp_project();
    setup_project(&dir);

    let result = std::process::Command::new(common::strata_bin())
        .args(["lint", "--format", "json"])
        .env("NO_COLOR", "1")
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    let stdout = String::from_utf8_lossy(&result.stdout);
    let json: serde_json::Value = serde_json::from_str(&stdout).expect("Should be valid JSON");
    insta::assert_json_snapshot!("lint_json_output", json);
}

#[test]
fn test_lint_sarif_output() {
    let dir = common::temp_project();
    setup_project(&dir);

    let result = std::process::Command::new(common::strata_bin())
        .args(["lint", "--format", "sarif"])
        .env("NO_COLOR", "1")
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    let stdout = String::from_utf8_lossy(&result.stdout);
    let json: serde_json::Value =
        serde_json::from_str(&stdout).expect("Should be valid SARIF JSON");

    // Verify SARIF structure
    assert_eq!(json["version"], "2.1.0");
    assert!(json["runs"].is_array());
    assert_eq!(json["runs"][0]["tool"]["driver"]["name"], "strata");
    insta::assert_json_snapshot!("lint_sarif_output", json, {
        ".runs[0].tool.driver.version" => "[version]",
    });
}

#[test]
fn test_lint_quiet_mode() {
    let dir = common::temp_project();
    setup_project(&dir);

    let result = std::process::Command::new(common::strata_bin())
        .args(["lint", "--quiet"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    let stdout = String::from_utf8_lossy(&result.stdout);
    // Quiet mode should produce no diagnostic output
    assert!(
        !stdout.contains("Lint Diagnostics"),
        "Quiet mode should suppress output"
    );
}

#[test]
fn test_lint_rule_filter() {
    let dir = common::temp_project();
    setup_project(&dir);

    let result = std::process::Command::new(common::strata_bin())
        .args(["lint", "--rule", "empty-folders"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    let stdout = String::from_utf8_lossy(&result.stdout);
    // Should only show empty-folders rule
    assert!(!stdout.contains("rules-completeness"));
    assert!(!stdout.contains("dead-links"));
}

#[test]
fn test_lint_stale_dates_warning() {
    let dir = common::temp_project();
    setup_project(&dir);
    // Create a markdown file with a very old last_verified date
    dir.child("01-Core/entity.md")
        .write_str("# Entity\n## Status\nlast_verified: 2020-01-01\n\nSome content.\n")
        .unwrap();

    let result = std::process::Command::new(common::strata_bin())
        .args(["lint", "--rule", "stale-dates"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    let combined = format!(
        "{}{}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );
    assert!(combined.contains("stale-dates"), "Output: {combined}");
    assert!(
        combined.contains("last_verified"),
        "Should mention last_verified: {combined}"
    );
}

#[test]
fn test_lint_waiting_markers_warning() {
    let dir = common::temp_project();
    setup_project(&dir);
    // Create a markdown file with a very old WAITING marker
    dir.child("01-Core/backlog.md")
        .write_str("# Backlog\n\n- Task one WAITING (partner reply, since 2020-01-01)\n")
        .unwrap();

    let result = std::process::Command::new(common::strata_bin())
        .args(["lint", "--rule", "waiting-markers"])
        .current_dir(dir.path())
        .output()
        .expect("Failed to run strata");

    let combined = format!(
        "{}{}",
        String::from_utf8_lossy(&result.stdout),
        String::from_utf8_lossy(&result.stderr)
    );
    assert!(combined.contains("waiting-markers"), "Output: {combined}");
    assert!(
        combined.contains("WAITING"),
        "Should mention WAITING marker: {combined}"
    );
}
