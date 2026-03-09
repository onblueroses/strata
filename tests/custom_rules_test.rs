#![expect(clippy::unwrap_used, reason = "test code - unwrap is acceptable")]
#![expect(clippy::expect_used, reason = "test code - expect is acceptable")]

mod common;

use assert_cmd::Command;
use assert_fs::prelude::*;
use predicates::prelude::*;

fn minimal_strata_toml(extra: &str) -> String {
    format!(
        r#"
[project]
name = "test-project"
{extra}
"#
    )
}

fn make_project(dir: &assert_fs::TempDir) {
    dir.child("PROJECT.md")
        .write_str("# Test\ndescription: A test project")
        .unwrap();
    dir.child("INDEX.md")
        .write_str("# Index\n\n| File | Description |\n|------|-------------|\n")
        .unwrap();
}

// --- file_exists ---

#[test]
fn test_file_exists_missing_file_emits_warning() {
    let dir = common::temp_project();
    make_project(&dir);

    dir.child("strata.toml")
        .write_str(&minimal_strata_toml(
            r#"
[[custom_rules]]
name = "require-changelog"
severity = "warning"
check = "file_exists"
glob = "CHANGELOG.md"
message = "CHANGELOG.md is missing"
"#,
        ))
        .unwrap();

    Command::new(common::strata_bin())
        .args(["lint", "--format", "json"])
        .current_dir(dir.path())
        .assert()
        .stdout(predicate::str::contains("require-changelog"));
}

#[test]
fn test_file_exists_present_file_no_diagnostic() {
    let dir = common::temp_project();
    make_project(&dir);

    dir.child("strata.toml")
        .write_str(&minimal_strata_toml(
            r#"
[[custom_rules]]
name = "require-changelog"
severity = "warning"
check = "file_exists"
glob = "CHANGELOG.md"
message = "CHANGELOG.md is missing"
"#,
        ))
        .unwrap();

    // Create the file that the rule requires
    dir.child("CHANGELOG.md")
        .write_str("# Changelog\ndescription: changelog")
        .unwrap();

    let output = Command::new(common::strata_bin())
        .args(["lint", "--format", "json"])
        .current_dir(dir.path())
        .output()
        .expect("strata failed");

    let json: serde_json::Value = serde_json::from_slice(&output.stdout).expect("invalid json");
    let rules: Vec<&str> = json
        .as_array()
        .unwrap()
        .iter()
        .filter_map(|d| d["rule"].as_str())
        .collect();
    assert!(!rules.contains(&"require-changelog"), "got: {rules:?}");
}

// --- content_contains ---

#[test]
fn test_content_contains_pattern_found_emits_diagnostic() {
    let dir = common::temp_project();
    make_project(&dir);

    dir.child("strata.toml")
        .write_str(&minimal_strata_toml(
            r#"
[[custom_rules]]
name = "no-bare-todos"
severity = "error"
check = "content_contains"
glob = "**/*.md"
pattern = "TODO"
negate = false
message = "bare TODO found"
"#,
        ))
        .unwrap();

    dir.child("docs/notes.md")
        .write_str("# Notes\ndescription: notes\n\nTODO: fix this")
        .unwrap();

    Command::new(common::strata_bin())
        .args(["lint", "--format", "json"])
        .current_dir(dir.path())
        .assert()
        .stdout(predicate::str::contains("no-bare-todos"));
}

#[test]
fn test_content_contains_negate_pattern_absent_emits_diagnostic() {
    let dir = common::temp_project();
    make_project(&dir);

    dir.child("strata.toml")
        .write_str(&minimal_strata_toml(
            r#"
[[custom_rules]]
name = "must-have-version"
severity = "warning"
check = "content_contains"
glob = "PROJECT.md"
pattern = "version:"
negate = true
message = "PROJECT.md is missing version field"
"#,
        ))
        .unwrap();

    // PROJECT.md exists but doesn't contain "version:"
    Command::new(common::strata_bin())
        .args(["lint", "--format", "json"])
        .current_dir(dir.path())
        .assert()
        .stdout(predicate::str::contains("must-have-version"));
}

// --- frontmatter_key ---

#[test]
fn test_frontmatter_key_missing_key_emits_diagnostic() {
    let dir = common::temp_project();
    make_project(&dir);

    dir.child("strata.toml")
        .write_str(&minimal_strata_toml(
            r#"
[[custom_rules]]
name = "descriptions-required"
severity = "warning"
check = "frontmatter_key"
glob = "docs/**/*.md"
key = "description"
message = "missing description"
"#,
        ))
        .unwrap();

    // A doc file with no heading or frontmatter so extract_description returns None
    dir.child("docs/api.md")
        .write_str("Some API documentation with no heading and no frontmatter.")
        .unwrap();

    Command::new(common::strata_bin())
        .args(["lint", "--format", "json"])
        .current_dir(dir.path())
        .assert()
        .stdout(predicate::str::contains("descriptions-required"));
}

// --- JSON output includes rule name ---

#[test]
fn test_custom_rule_name_in_json_output() {
    let dir = common::temp_project();
    make_project(&dir);

    dir.child("strata.toml")
        .write_str(&minimal_strata_toml(
            r#"
[[custom_rules]]
name = "require-readme"
severity = "error"
check = "file_exists"
glob = "README.md"
message = "README.md is missing"
"#,
        ))
        .unwrap();

    let output = Command::new(common::strata_bin())
        .args(["lint", "--format", "json"])
        .current_dir(dir.path())
        .output()
        .expect("strata failed");

    let json: serde_json::Value = serde_json::from_slice(&output.stdout).expect("invalid json");
    let rules: Vec<&str> = json
        .as_array()
        .unwrap()
        .iter()
        .filter_map(|d| d["rule"].as_str())
        .collect();
    assert!(rules.contains(&"require-readme"), "got: {rules:?}");

    // Severity should be "error"
    let diag = json
        .as_array()
        .unwrap()
        .iter()
        .find(|d| d["rule"].as_str() == Some("require-readme"))
        .unwrap();
    assert_eq!(diag["severity"].as_str(), Some("error"));
}
