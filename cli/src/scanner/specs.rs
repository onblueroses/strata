use crate::config::SpecsConfig;
use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};

/// Status of a spec file.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "kebab-case")]
pub enum SpecStatus {
    InProgress,
    Complete,
    Abandoned,
}

/// Metadata extracted from a spec markdown file.
#[derive(Debug, Clone)]
pub struct SpecMeta {
    /// Spec filename (without path).
    pub name: String,
    /// Relative path from project root.
    pub path: PathBuf,
    /// Parsed status field.
    pub status: Option<SpecStatus>,
    /// Session ID from the spec's Session field.
    pub session_id: Option<String>,
    /// Number of phase headings found.
    pub phase_count: usize,
    /// Total steps (checkbox lines).
    pub total_steps: usize,
    /// Completed steps (checked checkboxes).
    pub completed_steps: usize,
    /// Whether the spec has a `>> Current Step` section.
    pub has_current_step: bool,
    /// Number of rows in the Decisions table.
    #[cfg_attr(
        not(test),
        expect(dead_code, reason = "used by spec list/status commands")
    )]
    pub decision_count: usize,
    /// Last modification time as Unix timestamp.
    pub mtime_secs: u64,
}

/// Parse a single spec markdown file into `SpecMeta`.
pub fn parse_spec(path: &Path, relative_path: PathBuf) -> Option<SpecMeta> {
    let content = std::fs::read_to_string(path).ok()?;
    let name = path
        .file_stem()
        .and_then(|s| s.to_str())
        .unwrap_or("unknown")
        .to_string();

    let mut status = None;
    let mut session_id = None;
    let mut phase_count = 0;
    let mut total_steps = 0;
    let mut completed_steps = 0;
    let mut has_current_step = false;
    let mut decision_count = 0;
    let mut in_decisions_table = false;

    for line in content.lines() {
        let trimmed = line.trim();

        // Parse Status field
        if let Some(val) = trimmed.strip_prefix("Status:") {
            let val = val.trim().trim_matches('`');
            status = match val.to_lowercase().as_str() {
                "in-progress" | "in_progress" => Some(SpecStatus::InProgress),
                "complete" | "completed" => Some(SpecStatus::Complete),
                "abandoned" => Some(SpecStatus::Abandoned),
                _ => None,
            };
        }

        // Parse Session field
        if let Some(val) = trimmed.strip_prefix("Session:") {
            let val = val.trim().trim_matches('`');
            if !val.is_empty() {
                session_id = Some(val.to_string());
            }
        }

        // Count phases (### Phase headings)
        if trimmed.starts_with("### Phase") || trimmed.starts_with("## Phase") {
            phase_count += 1;
        }

        // Count steps (checkboxes)
        if trimmed.starts_with("- [ ] ") {
            total_steps += 1;
        } else if trimmed.starts_with("- [x] ") || trimmed.starts_with("- [X] ") {
            total_steps += 1;
            completed_steps += 1;
        }

        // Check for Current Step section
        if trimmed.contains(">> Current Step") {
            has_current_step = true;
        }

        // Count decision table rows
        if trimmed.starts_with("| ") && trimmed.ends_with(" |") {
            if trimmed.contains("Decision") && trimmed.contains("Rationale") {
                in_decisions_table = true;
            } else if in_decisions_table {
                // Skip separator rows
                if !trimmed.contains("---") {
                    decision_count += 1;
                }
            }
        } else if in_decisions_table && !trimmed.starts_with('|') {
            in_decisions_table = false;
        }
    }

    let mtime_secs = std::fs::metadata(path)
        .and_then(|m| m.modified())
        .ok()
        .and_then(|t| t.duration_since(std::time::UNIX_EPOCH).ok())
        .map_or(0, |d| d.as_secs());

    Some(SpecMeta {
        name,
        path: relative_path,
        status,
        session_id,
        phase_count,
        total_steps,
        completed_steps,
        has_current_step,
        decision_count,
        mtime_secs,
    })
}

/// Scan the specs directory and collect metadata.
pub fn scan_specs(root: &Path, config: &SpecsConfig) -> Vec<SpecMeta> {
    let specs_dir = root.join(&config.dir);
    if !specs_dir.is_dir() {
        return Vec::new();
    }

    let Ok(entries) = std::fs::read_dir(&specs_dir) else {
        return Vec::new();
    };

    let mut specs: Vec<SpecMeta> = entries
        .flatten()
        .filter(|e| {
            e.path().is_file()
                && e.path()
                    .extension()
                    .and_then(|ext| ext.to_str())
                    .is_some_and(|ext| ext == "md")
        })
        .filter_map(|e| {
            let abs = e.path();
            let rel = abs.strip_prefix(root).unwrap_or(&abs).to_path_buf();
            parse_spec(&abs, rel)
        })
        .collect();

    specs.sort_by(|a, b| a.name.cmp(&b.name));
    specs
}

#[cfg(test)]
#[expect(clippy::unwrap_used, reason = "test code")]
mod tests {
    use super::*;

    #[test]
    fn parse_spec_full() {
        let dir = tempfile::tempdir().unwrap();
        let spec_path = dir.path().join("test-feature.md");
        std::fs::write(
            &spec_path,
            r"# Test Feature

Status: `in-progress`
Session: `abc12345`

## Decisions

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Use X | Because Y |

### Phase A: Setup

- [x] Step one
- [ ] Step two
- [ ] Step three

>> Current Step: Step two
",
        )
        .unwrap();

        let meta = parse_spec(&spec_path, PathBuf::from(".strata/specs/test-feature.md")).unwrap();
        assert_eq!(meta.name, "test-feature");
        assert_eq!(meta.status, Some(SpecStatus::InProgress));
        assert_eq!(meta.session_id.as_deref(), Some("abc12345"));
        assert_eq!(meta.phase_count, 1);
        assert_eq!(meta.total_steps, 3);
        assert_eq!(meta.completed_steps, 1);
        assert!(meta.has_current_step);
        assert_eq!(meta.decision_count, 1);
    }

    #[test]
    fn parse_spec_complete() {
        let dir = tempfile::tempdir().unwrap();
        let spec_path = dir.path().join("done.md");
        std::fs::write(
            &spec_path,
            "# Done\n\nStatus: `complete`\n\n- [x] All done\n",
        )
        .unwrap();

        let meta = parse_spec(&spec_path, PathBuf::from(".strata/specs/done.md")).unwrap();
        assert_eq!(meta.status, Some(SpecStatus::Complete));
        assert_eq!(meta.total_steps, 1);
        assert_eq!(meta.completed_steps, 1);
    }

    #[test]
    fn scan_specs_empty_dir() {
        let dir = tempfile::tempdir().unwrap();
        let config = SpecsConfig::default();
        let specs = scan_specs(dir.path(), &config);
        assert!(specs.is_empty());
    }

    #[test]
    fn scan_specs_finds_files() {
        let dir = tempfile::tempdir().unwrap();
        let specs_dir = dir.path().join(".strata").join("specs");
        std::fs::create_dir_all(&specs_dir).unwrap();
        std::fs::write(
            specs_dir.join("alpha.md"),
            "# Alpha\n\nStatus: `in-progress`\n",
        )
        .unwrap();
        std::fs::write(specs_dir.join("beta.md"), "# Beta\n\nStatus: `complete`\n").unwrap();

        let config = SpecsConfig::default();
        let specs = scan_specs(dir.path(), &config);
        assert_eq!(specs.len(), 2);
        assert_eq!(specs[0].name, "alpha");
        assert_eq!(specs[1].name, "beta");
    }
}
