use crate::config::MemoryConfig;
use std::path::{Path, PathBuf};

/// Metadata about a memory layer file (MEMORY.md, CLAUDE.md, etc.).
#[derive(Debug, Clone)]
pub struct MemoryFileMeta {
    /// Relative path from project root.
    pub path: PathBuf,
    /// Total character count.
    pub char_count: usize,
    /// Whether the file contains at least one markdown heading (## or #).
    pub has_headings: bool,
}

/// Scan configured memory files and collect metadata.
pub fn scan_memory_files(root: &Path, config: &MemoryConfig) -> Vec<MemoryFileMeta> {
    config
        .files
        .iter()
        .filter_map(|filename| {
            let abs_path = root.join(filename);
            let content = std::fs::read_to_string(&abs_path).ok()?;
            let has_headings = content.lines().any(|line| line.starts_with('#'));
            Some(MemoryFileMeta {
                path: PathBuf::from(filename),
                char_count: content.len(),
                has_headings,
            })
        })
        .collect()
}

#[cfg(test)]
#[expect(clippy::unwrap_used, reason = "test code")]
mod tests {
    use super::*;

    fn config_with(files: &[&str]) -> MemoryConfig {
        MemoryConfig {
            files: files.iter().map(|s| (*s).to_string()).collect(),
            budget: 3200,
        }
    }

    #[test]
    fn existing_file_with_headings() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(
            dir.path().join("MEMORY.md"),
            "# Workspace\n\n## Projects\n\nSome content.\n",
        )
        .unwrap();

        let results = scan_memory_files(dir.path(), &config_with(&["MEMORY.md"]));
        assert_eq!(results.len(), 1);
        assert!(results[0].has_headings);
        assert!(results[0].char_count > 0);
    }

    #[test]
    fn existing_file_without_headings() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(
            dir.path().join("MEMORY.md"),
            "Just plain text.\nNo structure.\n",
        )
        .unwrap();

        let results = scan_memory_files(dir.path(), &config_with(&["MEMORY.md"]));
        assert_eq!(results.len(), 1);
        assert!(!results[0].has_headings);
    }

    #[test]
    fn missing_file_skipped() {
        let dir = tempfile::tempdir().unwrap();
        let results = scan_memory_files(dir.path(), &config_with(&["MEMORY.md"]));
        assert!(results.is_empty());
    }

    #[test]
    fn multiple_files_mixed() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(dir.path().join("MEMORY.md"), "## Section\nContent.\n").unwrap();
        // CLAUDE.md does not exist

        let results = scan_memory_files(dir.path(), &config_with(&["MEMORY.md", "CLAUDE.md"]));
        assert_eq!(results.len(), 1);
        assert_eq!(results[0].path, PathBuf::from("MEMORY.md"));
    }
}
