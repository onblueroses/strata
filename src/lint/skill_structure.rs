use crate::config::StrataConfig;
use crate::lint::{Diagnostic, LintRule, Severity};
use crate::scanner::ProjectScan;
use std::path::Path;

pub struct SkillStructure;

impl LintRule for SkillStructure {
    fn name(&self) -> &'static str {
        "skill-structure"
    }

    fn severity(&self) -> Severity {
        Severity::Warning
    }

    fn check(&self, scan: &ProjectScan, root: &Path, _config: &StrataConfig) -> Vec<Diagnostic> {
        let skills_dir = root.join("skills");
        if !skills_dir.is_dir() {
            return Vec::new(); // No skills/ directory = silent
        }

        let mut diagnostics = Vec::new();

        // Check for README.md in skills/
        if !skills_dir.join("README.md").exists() {
            diagnostics.push(Diagnostic {
                rule: self.name().to_string(),
                severity: self.severity(),
                message: "skills/ directory is missing README.md".to_string(),
                location: "skills/README.md".to_string(),
            });
        }

        // Check each subdirectory of skills/ for SKILL.md
        if let Ok(entries) = std::fs::read_dir(&skills_dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if !path.is_dir() {
                    continue;
                }

                let dir_name = entry.file_name();
                let dir_name = dir_name.to_string_lossy();
                let skill_md_path = path.join("SKILL.md");

                if !skill_md_path.exists() {
                    diagnostics.push(Diagnostic {
                        rule: self.name().to_string(),
                        severity: self.severity(),
                        message: format!("Skill '{dir_name}' is missing SKILL.md"),
                        location: format!("skills/{dir_name}/SKILL.md"),
                    });
                    continue;
                }

                // Check that SKILL.md has a name field
                let has_name = scan
                    .skills
                    .iter()
                    .any(|s| s.path.starts_with(format!("skills/{dir_name}")) && s.name.is_some());

                if !has_name {
                    diagnostics.push(Diagnostic {
                        rule: self.name().to_string(),
                        severity: self.severity(),
                        message: format!(
                            "SKILL.md for '{dir_name}' is missing a 'name' field in frontmatter"
                        ),
                        location: format!("skills/{dir_name}/SKILL.md"),
                    });
                }
            }
        }

        diagnostics
    }
}
