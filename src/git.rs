use std::path::Path;
use std::process::Command;

/// Get the short HEAD commit hash, or None if not a git repo / git not installed.
pub fn head_commit(root: &Path) -> Option<String> {
    let output = Command::new("git")
        .args(["rev-parse", "--short", "HEAD"])
        .current_dir(root)
        .output()
        .ok()?;

    if !output.status.success() {
        return None;
    }

    let hash = String::from_utf8_lossy(&output.stdout).trim().to_string();
    if hash.is_empty() { None } else { Some(hash) }
}

/// Count commits between `from` and `to` (exclusive..inclusive).
pub fn commit_distance(root: &Path, from: &str, to: &str) -> Option<usize> {
    let output = Command::new("git")
        .args(["rev-list", "--count", &format!("{from}..{to}")])
        .current_dir(root)
        .output()
        .ok()?;

    if !output.status.success() {
        return None;
    }

    String::from_utf8_lossy(&output.stdout).trim().parse().ok()
}

/// Check whether `root` is inside a git repository.
#[cfg_attr(not(test), expect(dead_code, reason = "public API for downstream use"))]
pub fn is_git_repo(root: &Path) -> bool {
    Command::new("git")
        .args(["rev-parse", "--git-dir"])
        .current_dir(root)
        .output()
        .is_ok_and(|o| o.status.success())
}

#[cfg(test)]
#[expect(clippy::unwrap_used, reason = "test code")]
mod tests {
    use super::*;

    fn init_git_repo(dir: &Path) {
        Command::new("git")
            .args(["init"])
            .current_dir(dir)
            .output()
            .unwrap();
        Command::new("git")
            .args(["config", "user.email", "test@test.com"])
            .current_dir(dir)
            .output()
            .unwrap();
        Command::new("git")
            .args(["config", "user.name", "Test"])
            .current_dir(dir)
            .output()
            .unwrap();
    }

    fn commit_file(dir: &Path, name: &str, content: &str) {
        std::fs::write(dir.join(name), content).unwrap();
        Command::new("git")
            .args(["add", name])
            .current_dir(dir)
            .output()
            .unwrap();
        Command::new("git")
            .args(["commit", "-m", &format!("add {name}")])
            .current_dir(dir)
            .output()
            .unwrap();
    }

    #[test]
    fn test_not_a_git_repo() {
        let dir = tempfile::tempdir().unwrap();
        assert!(!is_git_repo(dir.path()));
        assert!(head_commit(dir.path()).is_none());
    }

    #[test]
    fn test_head_commit_after_init() {
        let dir = tempfile::tempdir().unwrap();
        init_git_repo(dir.path());
        // No commits yet
        assert!(head_commit(dir.path()).is_none());
    }

    #[test]
    fn test_head_commit_with_commit() {
        let dir = tempfile::tempdir().unwrap();
        init_git_repo(dir.path());
        commit_file(dir.path(), "README.md", "# Hello");

        let hash = head_commit(dir.path()).unwrap();
        assert!(!hash.is_empty());
        assert!(hash.len() <= 12); // short hash
    }

    #[test]
    fn test_commit_distance() {
        let dir = tempfile::tempdir().unwrap();
        init_git_repo(dir.path());
        commit_file(dir.path(), "a.txt", "a");
        let first = head_commit(dir.path()).unwrap();

        commit_file(dir.path(), "b.txt", "b");
        commit_file(dir.path(), "c.txt", "c");
        let latest = head_commit(dir.path()).unwrap();

        let dist = commit_distance(dir.path(), &first, &latest).unwrap();
        assert_eq!(dist, 2);
    }

    #[test]
    fn test_is_git_repo() {
        let dir = tempfile::tempdir().unwrap();
        assert!(!is_git_repo(dir.path()));

        init_git_repo(dir.path());
        assert!(is_git_repo(dir.path()));
    }
}
