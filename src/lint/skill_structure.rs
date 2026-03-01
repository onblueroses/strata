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

                let skill_meta = scan
                    .skills
                    .iter()
                    .find(|s| s.path.starts_with(format!("skills/{dir_name}")));

                // Check that SKILL.md has a name field
                let has_name = skill_meta.is_some_and(|s| s.name.is_some());
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

                // Check that SKILL.md has a description field
                let has_description = skill_meta.is_some_and(|s| s.description.is_some());
                if !has_description {
                    diagnostics.push(Diagnostic {
                        rule: self.name().to_string(),
                        severity: Severity::Info,
                        message: format!(
                            "SKILL.md for '{dir_name}' is missing a 'description' field in frontmatter"
                        ),
                        location: format!("skills/{dir_name}/SKILL.md"),
                    });
                }
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
    use crate::scanner::skills::SkillMeta;
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
        }
    }

    fn scan_with_skills(root: PathBuf, skills: Vec<SkillMeta>) -> ProjectScan {
        ProjectScan {
            files: vec![],
            index_entries: vec![],
            crosslinks: vec![],
            descriptions: HashMap::new(),
            domain_rules: HashMap::new(),
            skills,
            memory_files: vec![],
            root,
        }
    }

    #[test]
    fn no_skills_dir_is_silent() {
        let dir = tempfile::tempdir().unwrap();
        let scan = scan_with_skills(dir.path().to_path_buf(), vec![]);
        let diags = SkillStructure.check(&scan, dir.path(), &empty_config());
        assert!(diags.is_empty());
    }

    #[test]
    fn skill_missing_description_emits_info() {
        let dir = tempfile::tempdir().unwrap();
        let skills_dir = dir.path().join("skills").join("my-skill");
        std::fs::create_dir_all(&skills_dir).unwrap();
        std::fs::write(skills_dir.join("SKILL.md"), "---\nname: my-skill\n---\n").unwrap();
        std::fs::write(dir.path().join("skills").join("README.md"), "# Skills\n").unwrap();

        let scan = scan_with_skills(
            dir.path().to_path_buf(),
            vec![SkillMeta {
                name: Some("my-skill".to_string()),
                description: None,
                trigger: None,
                path: PathBuf::from("skills/my-skill/SKILL.md"),
                char_count: 30,
            }],
        );

        let diags = SkillStructure.check(&scan, dir.path(), &empty_config());
        let info_diags: Vec<_> = diags
            .iter()
            .filter(|d| d.severity == Severity::Info)
            .collect();
        assert_eq!(info_diags.len(), 1);
        assert!(info_diags[0].message.contains("description"));
    }

    #[test]
    fn skill_with_description_no_info() {
        let dir = tempfile::tempdir().unwrap();
        let skills_dir = dir.path().join("skills").join("my-skill");
        std::fs::create_dir_all(&skills_dir).unwrap();
        std::fs::write(
            skills_dir.join("SKILL.md"),
            "---\nname: my-skill\ndescription: Does stuff\n---\n",
        )
        .unwrap();
        std::fs::write(dir.path().join("skills").join("README.md"), "# Skills\n").unwrap();

        let scan = scan_with_skills(
            dir.path().to_path_buf(),
            vec![SkillMeta {
                name: Some("my-skill".to_string()),
                description: Some("Does stuff".to_string()),
                trigger: None,
                path: PathBuf::from("skills/my-skill/SKILL.md"),
                char_count: 50,
            }],
        );

        let diags = SkillStructure.check(&scan, dir.path(), &empty_config());
        let info_diags: Vec<_> = diags
            .iter()
            .filter(|d| d.severity == Severity::Info)
            .collect();
        assert!(info_diags.is_empty());
    }
}
