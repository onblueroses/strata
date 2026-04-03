use assert_cmd::Command;
use predicates::prelude::*;
use std::path::PathBuf;

#[expect(
    deprecated,
    reason = "cargo_bin API is deprecated but still the standard way to locate test binaries"
)]
fn strata_bin() -> PathBuf {
    assert_cmd::cargo::cargo_bin("strata")
}

#[test]
fn test_bash_completions_nonempty() {
    Command::new(strata_bin())
        .args(["completions", "bash"])
        .assert()
        .success()
        .stdout(predicate::str::contains("strata"))
        .stdout(predicate::str::is_empty().not());
}

#[test]
fn test_zsh_completions_nonempty() {
    Command::new(strata_bin())
        .args(["completions", "zsh"])
        .assert()
        .success()
        .stdout(predicate::str::contains("strata"))
        .stdout(predicate::str::is_empty().not());
}

#[test]
fn test_fish_completions_nonempty() {
    Command::new(strata_bin())
        .args(["completions", "fish"])
        .assert()
        .success()
        .stdout(predicate::str::contains("strata"))
        .stdout(predicate::str::is_empty().not());
}

#[test]
fn test_powershell_completions_nonempty() {
    Command::new(strata_bin())
        .args(["completions", "powershell"])
        .assert()
        .success()
        .stdout(predicate::str::is_empty().not());
}
