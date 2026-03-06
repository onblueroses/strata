use crate::config::StrataConfig;
use crate::lint::{Diagnostic, LintRule, Severity};
use crate::scanner::ProjectScan;
use crate::scanner::specs::SpecStatus;
use std::path::Path;

pub struct SpecStructure;

impl LintRule for SpecStructure {
    fn name(&self) -> &'static str {
        "spec-structure"
    }

    fn severity(&self) -> Severity {
        Severity::Warning
    }

    fn check(&self, scan: &ProjectScan, _root: &Path, config: &StrataConfig) -> Vec<Diagnostic> {
        let mut diagnostics = Vec::new();
        let max_steps = config.specs.max_steps_per_phase as usize;

        for spec in &scan.specs {
            let loc = spec.path.to_string_lossy().to_string();

            if spec.status.is_none() {
                diagnostics.push(Diagnostic {
                    rule: self.name().to_string(),
                    severity: self.severity(),
                    message: format!("Spec '{}' is missing a Status field", spec.name),
                    location: loc.clone(),
                });
            }

            if spec.status == Some(SpecStatus::InProgress) && !spec.has_current_step {
                diagnostics.push(Diagnostic {
                    rule: self.name().to_string(),
                    severity: self.severity(),
                    message: format!(
                        "In-progress spec '{}' is missing a '>> Current Step' section",
                        spec.name
                    ),
                    location: loc.clone(),
                });
            }

            // Check steps per phase (rough: total_steps / phase_count)
            if spec.phase_count > 0 && spec.total_steps > max_steps * spec.phase_count {
                diagnostics.push(Diagnostic {
                    rule: self.name().to_string(),
                    severity: self.severity(),
                    message: format!(
                        "Spec '{}' averages {} steps/phase (max: {max_steps})",
                        spec.name,
                        spec.total_steps / spec.phase_count
                    ),
                    location: loc,
                });
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
        SkillsConfig, SpecsConfig, StructureConfig, TargetsConfig,
    };
    use crate::scanner::specs::SpecMeta;
    use std::collections::HashMap;
    use std::path::PathBuf;

    fn default_config() -> StrataConfig {
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
        }
    }

    fn scan_with_specs(root: PathBuf, specs: Vec<SpecMeta>) -> ProjectScan {
        ProjectScan {
            files: vec![],
            index_entries: vec![],
            crosslinks: vec![],
            descriptions: HashMap::new(),
            domain_rules: HashMap::new(),
            skills: vec![],
            memory_files: vec![],
            hooks: vec![],
            specs,
            sessions: vec![],
            root,
        }
    }

    #[test]
    fn in_progress_without_current_step() {
        let dir = tempfile::tempdir().unwrap();
        let scan = scan_with_specs(
            dir.path().to_path_buf(),
            vec![SpecMeta {
                name: "test".to_string(),
                path: PathBuf::from(".strata/specs/test.md"),
                status: Some(SpecStatus::InProgress),
                session_id: None,
                phase_count: 1,
                total_steps: 3,
                completed_steps: 0,
                has_current_step: false,
                decision_count: 0,
                mtime_secs: 0,
            }],
        );
        let diags = SpecStructure.check(&scan, dir.path(), &default_config());
        assert!(diags.iter().any(|d| d.message.contains("Current Step")));
    }

    #[test]
    fn complete_spec_without_current_step_ok() {
        let dir = tempfile::tempdir().unwrap();
        let scan = scan_with_specs(
            dir.path().to_path_buf(),
            vec![SpecMeta {
                name: "done".to_string(),
                path: PathBuf::from(".strata/specs/done.md"),
                status: Some(SpecStatus::Complete),
                session_id: None,
                phase_count: 1,
                total_steps: 3,
                completed_steps: 3,
                has_current_step: false,
                decision_count: 0,
                mtime_secs: 0,
            }],
        );
        let diags = SpecStructure.check(&scan, dir.path(), &default_config());
        assert!(diags.is_empty());
    }
}
