use crate::config::{StrataConfig, default_memory_files};
use crate::lint::{Diagnostic, LintRule, Severity};
use crate::scanner::ProjectScan;
use std::path::Path;

pub struct MemoryStructure;

impl LintRule for MemoryStructure {
    fn name(&self) -> &'static str {
        "memory-structure"
    }

    fn severity(&self) -> Severity {
        Severity::Info
    }

    fn check(&self, scan: &ProjectScan, root: &Path, config: &StrataConfig) -> Vec<Diagnostic> {
        let mut diagnostics = Vec::new();
        let is_explicitly_configured = config.memory.files != default_memory_files();

        for filename in &config.memory.files {
            let abs_path = root.join(filename);
            let scanned = scan
                .memory_files
                .iter()
                .find(|m| m.path.to_string_lossy() == *filename);

            match scanned {
                None if !abs_path.exists() && is_explicitly_configured => {
                    diagnostics.push(Diagnostic {
                        rule: self.name().to_string(),
                        severity: self.severity(),
                        message: format!("{filename} is configured but does not exist"),
                        location: filename.clone(),
                    });
                }
                Some(meta) if !meta.has_headings => {
                    diagnostics.push(Diagnostic {
                        rule: self.name().to_string(),
                        severity: self.severity(),
                        message: format!(
                            "{filename} has no markdown headings - flat text is harder for agents to navigate"
                        ),
                        location: filename.clone(),
                    });
                }
                _ => {}
            }
        }

        diagnostics
    }
}

#[cfg(test)]
#[expect(clippy::unwrap_used, reason = "test code")]
mod tests {
    use super::*;
    use crate::config::{ContextConfig, LintConfig, MemoryConfig, ProjectConfig, StructureConfig};
    use crate::scanner::memory::MemoryFileMeta;
    use std::collections::HashMap;
    use std::path::PathBuf;

    fn config_with_files(files: &[&str]) -> StrataConfig {
        StrataConfig {
            project: ProjectConfig {
                name: "test".to_string(),
                description: String::new(),
                domains: vec![],
            },
            structure: StructureConfig::default(),
            lint: LintConfig::default(),
            context: ContextConfig::default(),
            memory: MemoryConfig {
                files: files.iter().map(|s| (*s).to_string()).collect(),
                budget: 3200,
            },
        }
    }

    fn scan_with_memory(root: PathBuf, memory_files: Vec<MemoryFileMeta>) -> ProjectScan {
        ProjectScan {
            files: vec![],
            index_entries: vec![],
            crosslinks: vec![],
            descriptions: HashMap::new(),
            domain_rules: HashMap::new(),
            skills: vec![],
            memory_files,
            root,
        }
    }

    #[test]
    fn missing_file_with_default_config_silent() {
        let dir = tempfile::tempdir().unwrap();
        let scan = scan_with_memory(dir.path().to_path_buf(), vec![]);
        // Default config = ["MEMORY.md"], file doesn't exist -> silent
        let config = config_with_files(&["MEMORY.md"]);
        let diags = MemoryStructure.check(&scan, dir.path(), &config);
        assert!(diags.is_empty());
    }

    #[test]
    fn missing_file_with_explicit_config_warns() {
        let dir = tempfile::tempdir().unwrap();
        let scan = scan_with_memory(dir.path().to_path_buf(), vec![]);
        // Explicitly configured non-default files
        let config = config_with_files(&["CLAUDE.md"]);
        let diags = MemoryStructure.check(&scan, dir.path(), &config);
        assert_eq!(diags.len(), 1);
        assert!(diags[0].message.contains("does not exist"));
    }

    #[test]
    fn file_without_headings_warns() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(dir.path().join("MEMORY.md"), "Just text.\nNo headings.\n").unwrap();

        let scan = scan_with_memory(
            dir.path().to_path_buf(),
            vec![MemoryFileMeta {
                path: PathBuf::from("MEMORY.md"),
                char_count: 25,
                has_headings: false,
            }],
        );
        let config = config_with_files(&["MEMORY.md"]);
        let diags = MemoryStructure.check(&scan, dir.path(), &config);
        assert_eq!(diags.len(), 1);
        assert!(diags[0].message.contains("no markdown headings"));
    }

    #[test]
    fn well_formed_file_no_diagnostics() {
        let dir = tempfile::tempdir().unwrap();
        std::fs::write(
            dir.path().join("MEMORY.md"),
            "# Memory\n\n## Section\nContent.\n",
        )
        .unwrap();

        let scan = scan_with_memory(
            dir.path().to_path_buf(),
            vec![MemoryFileMeta {
                path: PathBuf::from("MEMORY.md"),
                char_count: 30,
                has_headings: true,
            }],
        );
        let config = config_with_files(&["MEMORY.md"]);
        let diags = MemoryStructure.check(&scan, dir.path(), &config);
        assert!(diags.is_empty());
    }
}
