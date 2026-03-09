use crate::config::StrataConfig;
use crate::lint::{Diagnostic, LintRule, Severity};
use crate::scanner::ProjectScan;
use std::path::Path;

/// Maximum recommended character count for a hook script.
const HOOK_CHAR_BUDGET: usize = 2000;

pub struct HookBudget;

impl LintRule for HookBudget {
    fn name(&self) -> &'static str {
        "hook-budget"
    }

    fn severity(&self) -> Severity {
        Severity::Warning
    }

    fn check(&self, scan: &ProjectScan, _root: &Path, _config: &StrataConfig) -> Vec<Diagnostic> {
        scan.hooks
            .iter()
            .filter(|h| h.exists && h.char_count > HOOK_CHAR_BUDGET)
            .map(|h| Diagnostic::new(
                self.name(),
                self.severity(),
                format!(
                    "Hook '{}' is {} chars (budget: {HOOK_CHAR_BUDGET}). Consider extracting logic to a separate script.",
                    h.event, h.char_count
                ),
                h.path.to_string_lossy().to_string(),
            ))
            .collect()
    }
}

#[cfg(test)]
#[expect(clippy::unwrap_used, reason = "test code")]
mod tests {
    use super::*;
    use crate::config::{
        ContextConfig, HooksConfig, LintConfig, MemoryConfig, ProjectConfig, SessionsConfig,
        SkillsConfig, SpecsConfig, StructureConfig, TargetsConfig, WorkspaceConfig,
    };
    use crate::scanner::hooks::HookMeta;
    use std::collections::HashMap;
    use std::path::PathBuf;

    fn empty_config() -> StrataConfig {
        StrataConfig {
            project: ProjectConfig {
                name: "test".to_string(),
                description: String::new(),
                domains: vec![],
            },
            structure: StructureConfig::default(),
            lint: LintConfig::default(),
            context: ContextConfig::default(),
            memory: MemoryConfig::default(),
            hooks: HooksConfig::default(),
            specs: SpecsConfig::default(),
            sessions: SessionsConfig::default(),
            targets: TargetsConfig::default(),
            skills: SkillsConfig::default(),
            custom_rules: vec![],
            workspace: WorkspaceConfig::default(),
        }
    }

    fn scan_with_hooks(root: PathBuf, hooks: Vec<HookMeta>) -> ProjectScan {
        ProjectScan {
            files: vec![],
            index_entries: vec![],
            crosslinks: vec![],
            descriptions: HashMap::new(),
            domain_rules: HashMap::new(),
            skills: vec![],
            memory_files: vec![],
            hooks,
            specs: vec![],
            sessions: vec![],
            project_type: crate::scanner::project_type::ProjectType::unknown(),
            root,
        }
    }

    #[test]
    fn under_budget_is_clean() {
        let dir = tempfile::tempdir().unwrap();
        let scan = scan_with_hooks(
            dir.path().to_path_buf(),
            vec![HookMeta {
                event: "session_start".to_string(),
                path: PathBuf::from(".strata/hooks/session-start.sh"),
                exists: true,
                is_executable: true,
                has_shebang: true,
                char_count: 100,
            }],
        );
        let diags = HookBudget.check(&scan, dir.path(), &empty_config());
        assert!(diags.is_empty());
    }

    #[test]
    fn over_budget_warns() {
        let dir = tempfile::tempdir().unwrap();
        let scan = scan_with_hooks(
            dir.path().to_path_buf(),
            vec![HookMeta {
                event: "session_start".to_string(),
                path: PathBuf::from(".strata/hooks/session-start.sh"),
                exists: true,
                is_executable: true,
                has_shebang: true,
                char_count: 3000,
            }],
        );
        let diags = HookBudget.check(&scan, dir.path(), &empty_config());
        assert_eq!(diags.len(), 1);
        assert!(diags[0].message.contains("3000"));
    }

    #[test]
    fn non_existent_hook_skipped() {
        let dir = tempfile::tempdir().unwrap();
        let scan = scan_with_hooks(
            dir.path().to_path_buf(),
            vec![HookMeta {
                event: "session_start".to_string(),
                path: PathBuf::from(".strata/hooks/session-start.sh"),
                exists: false,
                is_executable: false,
                has_shebang: false,
                char_count: 0,
            }],
        );
        let diags = HookBudget.check(&scan, dir.path(), &empty_config());
        assert!(diags.is_empty());
    }
}
