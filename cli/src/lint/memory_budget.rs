use crate::config::StrataConfig;
use crate::lint::{Diagnostic, LintRule, Severity};
use crate::scanner::ProjectScan;
use std::path::Path;

pub struct MemoryBudget;

impl LintRule for MemoryBudget {
    fn name(&self) -> &'static str {
        "memory-budget"
    }

    fn severity(&self) -> Severity {
        Severity::Warning
    }

    fn check(&self, scan: &ProjectScan, _root: &Path, config: &StrataConfig) -> Vec<Diagnostic> {
        let budget = config.memory.budget as usize;

        scan.memory_files
            .iter()
            .filter(|m| m.char_count > budget)
            .map(|m| {
                let location = m.path.to_string_lossy().replace('\\', "/");
                Diagnostic::new(
                    self.name(),
                    self.severity(),
                    format!("{location} is {} chars, budget is {budget}", m.char_count),
                    location,
                )
            })
            .collect()
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::config::{
        ContextConfig, HooksConfig, LintConfig, MemoryConfig, ProjectConfig, SessionsConfig,
        SkillsConfig, SpecsConfig, StructureConfig, TargetsConfig, WorkspaceConfig,
    };
    use crate::scanner::memory::MemoryFileMeta;
    use std::collections::HashMap;
    use std::path::PathBuf;

    fn config_with_budget(budget: u32) -> StrataConfig {
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
                files: vec!["MEMORY.md".to_string()],
                budget,
            },
            hooks: HooksConfig::default(),
            specs: SpecsConfig::default(),
            sessions: SessionsConfig::default(),
            targets: TargetsConfig::default(),
            skills: SkillsConfig::default(),
            custom_rules: vec![],
            workspace: WorkspaceConfig::default(),
        }
    }

    fn scan_with_memory(memory_files: Vec<MemoryFileMeta>) -> ProjectScan {
        ProjectScan {
            files: vec![],
            index_entries: vec![],
            crosslinks: vec![],
            descriptions: HashMap::new(),
            domain_rules: HashMap::new(),
            skills: vec![],
            memory_files,
            hooks: vec![],
            specs: vec![],
            sessions: vec![],
            project_type: crate::scanner::project_type::ProjectType::unknown(),
            root: PathBuf::from("/tmp/test"),
        }
    }

    #[test]
    fn under_budget_no_diagnostic() {
        let scan = scan_with_memory(vec![MemoryFileMeta {
            path: PathBuf::from("MEMORY.md"),
            char_count: 1000,
            has_headings: true,
        }]);
        let diags = MemoryBudget.check(&scan, Path::new("/tmp/test"), &config_with_budget(3200));
        assert!(diags.is_empty());
    }

    #[test]
    fn over_budget_emits_warning() {
        let scan = scan_with_memory(vec![MemoryFileMeta {
            path: PathBuf::from("MEMORY.md"),
            char_count: 5000,
            has_headings: true,
        }]);
        let diags = MemoryBudget.check(&scan, Path::new("/tmp/test"), &config_with_budget(3200));
        assert_eq!(diags.len(), 1);
        assert_eq!(diags[0].severity, Severity::Warning);
        assert!(diags[0].message.contains("5000"));
        assert!(diags[0].message.contains("3200"));
    }

    #[test]
    fn exact_budget_no_diagnostic() {
        let scan = scan_with_memory(vec![MemoryFileMeta {
            path: PathBuf::from("MEMORY.md"),
            char_count: 3200,
            has_headings: true,
        }]);
        let diags = MemoryBudget.check(&scan, Path::new("/tmp/test"), &config_with_budget(3200));
        assert!(diags.is_empty());
    }
}
