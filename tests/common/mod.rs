use assert_fs::TempDir;
use std::path::PathBuf;

/// Create a temp directory and return it.
pub fn temp_project() -> TempDir {
    TempDir::new().expect("Failed to create temp directory")
}

/// Get the strata binary path for integration tests.
#[allow(deprecated)]
pub fn strata_bin() -> PathBuf {
    assert_cmd::cargo::cargo_bin("strata")
}
