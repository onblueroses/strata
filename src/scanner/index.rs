use crate::error::Result;
use std::path::Path;

/// A single entry from INDEX.md.
#[derive(Debug, Clone)]
#[allow(dead_code)]
pub struct IndexEntry {
    pub path: String,
    pub description: String,
}

/// Parse INDEX.md table rows into IndexEntry structs.
/// Expected format: | `path/to/file` | Description text |
pub fn parse_index(index_path: &Path) -> Result<Vec<IndexEntry>> {
    let content = std::fs::read_to_string(index_path)?;
    let mut entries = Vec::new();

    for line in content.lines() {
        let line = line.trim();
        if !line.starts_with('|') || !line.ends_with('|') {
            continue;
        }

        let parts: Vec<&str> = line.split('|').collect();
        if parts.len() < 3 {
            continue;
        }

        let path_cell = parts[1].trim();
        let desc_cell = if parts.len() > 2 { parts[2].trim() } else { "" };

        // Skip header rows
        if path_cell.starts_with("---")
            || path_cell.starts_with("File")
            || path_cell.starts_with("Path")
        {
            continue;
        }

        // Extract path from backticks if present
        let path = path_cell
            .trim_start_matches('`')
            .trim_end_matches('`')
            .trim();

        if path.is_empty() {
            continue;
        }

        entries.push(IndexEntry {
            path: path.to_string(),
            description: desc_cell.to_string(),
        });
    }

    Ok(entries)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::io::Write;

    #[test]
    fn test_parse_index() {
        let dir = tempfile::tempdir().unwrap();
        let index_path = dir.path().join("INDEX.md");
        let mut f = std::fs::File::create(&index_path).unwrap();
        writeln!(f, "# Index").unwrap();
        writeln!(f).unwrap();
        writeln!(f, "| File | Description |").unwrap();
        writeln!(f, "|------|-------------|").unwrap();
        writeln!(f, "| `src/main.rs` | Entry point |").unwrap();
        writeln!(f, "| `README.md` | Project readme |").unwrap();

        let entries = parse_index(&index_path).unwrap();
        assert_eq!(entries.len(), 2);
        assert_eq!(entries[0].path, "src/main.rs");
        assert_eq!(entries[0].description, "Entry point");
        assert_eq!(entries[1].path, "README.md");
    }

    #[test]
    fn test_parse_empty_index() {
        let dir = tempfile::tempdir().unwrap();
        let index_path = dir.path().join("INDEX.md");
        std::fs::write(&index_path, "# Index\n\nNo table here.\n").unwrap();

        let entries = parse_index(&index_path).unwrap();
        assert!(entries.is_empty());
    }
}
