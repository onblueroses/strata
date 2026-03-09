use crate::config::StrataConfig;
use crate::lint::{Diagnostic, LintRule, Severity};
use crate::scanner::ProjectScan;
use std::path::Path;

pub struct HookStructure;

impl LintRule for HookStructure {
    fn name(&self) -> &'static str {
        "hook-structure"
    }

    fn severity(&self) -> Severity {
        Severity::Warning
    }

    fn check(&self, scan: &ProjectScan, _root: &Path, _config: &StrataConfig) -> Vec<Diagnostic> {
        let mut diagnostics = Vec::new();

        for hook in &scan.hooks {
            let loc = hook.path.to_string_lossy().to_string();

            if !hook.exists {
                diagnostics.push(Diagnostic::new(
                    self.name(),
                    self.severity(),
                    format!(
                        "Hook '{}' is configured but file does not exist",
                        hook.event
                    ),
                    loc,
                ));
                continue;
            }

            if !hook.has_shebang {
                diagnostics.push(Diagnostic::new(
                    self.name(),
                    self.severity(),
                    format!(
                        "Hook '{}' is missing a shebang line (#!/usr/bin/env bash)",
                        hook.event
                    ),
                    loc.clone(),
                ));
            }

            if !hook.is_executable {
                diagnostics.push(Diagnostic::new(
                    self.name(),
                    self.severity(),
                    format!("Hook '{}' is not executable (chmod +x)", hook.event),
                    loc,
                ));
            }
        }

        diagnostics
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
    fn no_hooks_is_clean() {
        let dir = tempfile::tempdir().unwrap();
        let scan = scan_with_hooks(dir.path().to_path_buf(), vec![]);
        let diags = HookStructure.check(&scan, dir.path(), &empty_config());
        assert!(diags.is_empty());
    }

    #[test]
    fn missing_file_warns() {
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
        let diags = HookStructure.check(&scan, dir.path(), &empty_config());
        assert_eq!(diags.len(), 1);
        assert!(diags[0].message.contains("does not exist"));
    }

    #[test]
    fn missing_shebang_warns() {
        let dir = tempfile::tempdir().unwrap();
        let scan = scan_with_hooks(
            dir.path().to_path_buf(),
            vec![HookMeta {
                event: "session_start".to_string(),
                path: PathBuf::from(".strata/hooks/session-start.sh"),
                exists: true,
                is_executable: true,
                has_shebang: false,
                char_count: 20,
            }],
        );
        let diags = HookStructure.check(&scan, dir.path(), &empty_config());
        assert_eq!(diags.len(), 1);
        assert!(diags[0].message.contains("shebang"));
    }

    #[test]
    fn well_formed_hook_no_diagnostics() {
        let dir = tempfile::tempdir().unwrap();
        let scan = scan_with_hooks(
            dir.path().to_path_buf(),
            vec![HookMeta {
                event: "session_start".to_string(),
                path: PathBuf::from(".strata/hooks/session-start.sh"),
                exists: true,
                is_executable: true,
                has_shebang: true,
                char_count: 50,
            }],
        );
        let diags = HookStructure.check(&scan, dir.path(), &empty_config());
        assert!(diags.is_empty());
    }
}
