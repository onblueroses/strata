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
            diagnostics.push(Diagnostic::new(
                self.name(),
                self.severity(),
                "skills/ directory is missing README.md",
                "skills/README.md",
            ));
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
                    diagnostics.push(Diagnostic::new(
                        self.name(),
                        self.severity(),
                        format!("Skill '{dir_name}' is missing SKILL.md"),
                        format!("skills/{dir_name}/SKILL.md"),
                    ));
                    continue;
                }

                let skill_meta = scan
                    .skills
                    .iter()
                    .find(|s| s.path.starts_with(format!("skills/{dir_name}")));

                // Check that SKILL.md has a name field
                let has_name = skill_meta.is_some_and(|s| s.name.is_some());
                if !has_name {
                    diagnostics.push(Diagnostic::new(
                        self.name(),
                        self.severity(),
                        format!(
                            "SKILL.md for '{dir_name}' is missing a 'name' field in frontmatter"
                        ),
                        format!("skills/{dir_name}/SKILL.md"),
                    ));
                }

                // Check that SKILL.md has a description field
                let has_description = skill_meta.is_some_and(|s| s.description.is_some());
                if !has_description {
                    diagnostics.push(Diagnostic::new(
                        self.name(),
                        Severity::Info,
                        format!(
                            "SKILL.md for '{dir_name}' is missing a 'description' field in frontmatter"
                        ),
                        format!("skills/{dir_name}/SKILL.md"),
                    ));
                }

                let Some(meta) = skill_meta else {
                    continue;
                };

                // Name must be kebab-case and <= 64 chars
                if let Some(name) = &meta.name {
                    if name.len() > 64 {
                        diagnostics.push(Diagnostic::new(
                            self.name(),
                            self.severity(),
                            format!(
                                "Skill name '{name}' exceeds 64 characters ({} chars)",
                                name.len()
                            ),
                            format!("skills/{dir_name}/SKILL.md"),
                        ));
                    }
                    if !is_kebab_case(name) {
                        diagnostics.push(Diagnostic::new(
                            self.name(),
                            self.severity(),
                            format!(
                                "Skill name '{name}' is not kebab-case (use lowercase letters, digits, and hyphens)"
                            ),
                            format!("skills/{dir_name}/SKILL.md"),
                        ));
                    }
                }

                // Description should be <= 1024 chars (Claude Code limit)
                if let Some(desc) = &meta.description {
                    if desc.len() > 1024 {
                        diagnostics.push(Diagnostic::new(
                            self.name(),
                            self.severity(),
                            format!(
                                "Skill description for '{dir_name}' exceeds 1024 characters ({} chars) - Claude Code truncates beyond this",
                                desc.len()
                            ),
                            format!("skills/{dir_name}/SKILL.md"),
                        ));
                    }
                }

                // Body size tiers: 500+ lines without references/ is a warning
                if meta.line_count > 500 && !meta.has_references_dir {
                    diagnostics.push(Diagnostic::new(
                        self.name(),
                        self.severity(),
                        format!(
                            "SKILL.md for '{dir_name}' is {} lines - consider splitting detail into a references/ subdirectory",
                            meta.line_count
                        ),
                        format!("skills/{dir_name}/SKILL.md"),
                    ));
                }
            }
        }

        diagnostics
    }
}

/// Returns true if the string is valid kebab-case: lowercase ASCII letters,
/// digits, and hyphens, not starting or ending with a hyphen.
fn is_kebab_case(s: &str) -> bool {
    if s.is_empty() {
        return false;
    }
    let bytes = s.as_bytes();
    if bytes[0] == b'-' || bytes[bytes.len() - 1] == b'-' {
        return false;
    }
    s.bytes()
        .all(|b| b.is_ascii_lowercase() || b.is_ascii_digit() || b == b'-')
}

#[cfg(test)]
#[expect(clippy::unwrap_used, reason = "test code")]
mod tests {
    use super::*;
    use crate::config::{
        ContextConfig, HooksConfig, LintConfig, MemoryConfig, ProjectConfig, SessionsConfig,
        SkillsConfig, SpecsConfig, StructureConfig, TargetsConfig,
    };
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
            hooks: HooksConfig::default(),
            specs: SpecsConfig::default(),
            sessions: SessionsConfig::default(),
            targets: TargetsConfig::default(),
            skills: SkillsConfig::default(),
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
            hooks: vec![],
            specs: vec![],
            sessions: vec![],
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
                line_count: 5,
                has_references_dir: false,
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
                line_count: 5,
                has_references_dir: false,
            }],
        );

        let diags = SkillStructure.check(&scan, dir.path(), &empty_config());
        let info_diags: Vec<_> = diags
            .iter()
            .filter(|d| d.severity == Severity::Info)
            .collect();
        assert!(info_diags.is_empty());
    }

    #[test]
    fn skill_name_not_kebab_case_warns() {
        let dir = tempfile::tempdir().unwrap();
        let skills_dir = dir.path().join("skills").join("MySkill");
        std::fs::create_dir_all(&skills_dir).unwrap();
        std::fs::write(
            skills_dir.join("SKILL.md"),
            "---\nname: MySkill\ndescription: Bad name\n---\n",
        )
        .unwrap();
        std::fs::write(dir.path().join("skills").join("README.md"), "# Skills\n").unwrap();

        let scan = scan_with_skills(
            dir.path().to_path_buf(),
            vec![SkillMeta {
                name: Some("MySkill".to_string()),
                description: Some("Bad name".to_string()),
                trigger: None,
                path: PathBuf::from("skills/MySkill/SKILL.md"),
                char_count: 50,
                line_count: 5,
                has_references_dir: false,
            }],
        );

        let diags = SkillStructure.check(&scan, dir.path(), &empty_config());
        assert!(diags.iter().any(|d| d.message.contains("kebab-case")));
    }

    #[test]
    fn skill_name_too_long_warns() {
        let dir = tempfile::tempdir().unwrap();
        let long_name = "a".repeat(65);
        let skills_dir = dir.path().join("skills").join(&long_name);
        std::fs::create_dir_all(&skills_dir).unwrap();
        std::fs::write(
            skills_dir.join("SKILL.md"),
            format!("---\nname: {long_name}\ndescription: Long\n---\n"),
        )
        .unwrap();
        std::fs::write(dir.path().join("skills").join("README.md"), "# Skills\n").unwrap();

        let scan = scan_with_skills(
            dir.path().to_path_buf(),
            vec![SkillMeta {
                name: Some(long_name.clone()),
                description: Some("Long".to_string()),
                trigger: None,
                path: PathBuf::from(format!("skills/{long_name}/SKILL.md")),
                char_count: 80,
                line_count: 5,
                has_references_dir: false,
            }],
        );

        let diags = SkillStructure.check(&scan, dir.path(), &empty_config());
        assert!(diags.iter().any(|d| d.message.contains("exceeds 64")));
    }

    #[test]
    fn skill_description_over_1024_warns() {
        let dir = tempfile::tempdir().unwrap();
        let skills_dir = dir.path().join("skills").join("verbose");
        std::fs::create_dir_all(&skills_dir).unwrap();
        let long_desc = "x".repeat(1025);
        std::fs::write(
            skills_dir.join("SKILL.md"),
            format!("---\nname: verbose\ndescription: {long_desc}\n---\n"),
        )
        .unwrap();
        std::fs::write(dir.path().join("skills").join("README.md"), "# Skills\n").unwrap();

        let scan = scan_with_skills(
            dir.path().to_path_buf(),
            vec![SkillMeta {
                name: Some("verbose".to_string()),
                description: Some(long_desc),
                trigger: None,
                path: PathBuf::from("skills/verbose/SKILL.md"),
                char_count: 1100,
                line_count: 5,
                has_references_dir: false,
            }],
        );

        let diags = SkillStructure.check(&scan, dir.path(), &empty_config());
        assert!(diags.iter().any(|d| d.message.contains("1024 characters")));
    }

    #[test]
    fn large_skill_without_references_warns() {
        let dir = tempfile::tempdir().unwrap();
        let skills_dir = dir.path().join("skills").join("big-skill");
        std::fs::create_dir_all(&skills_dir).unwrap();
        std::fs::write(skills_dir.join("SKILL.md"), "---\nname: big-skill\n---\n").unwrap();
        std::fs::write(dir.path().join("skills").join("README.md"), "# Skills\n").unwrap();

        let scan = scan_with_skills(
            dir.path().to_path_buf(),
            vec![SkillMeta {
                name: Some("big-skill".to_string()),
                description: None,
                trigger: None,
                path: PathBuf::from("skills/big-skill/SKILL.md"),
                char_count: 20_000,
                line_count: 550,
                has_references_dir: false,
            }],
        );

        let diags = SkillStructure.check(&scan, dir.path(), &empty_config());
        assert!(diags.iter().any(|d| d.message.contains("references/")));
    }

    #[test]
    fn large_skill_with_references_no_warning() {
        let dir = tempfile::tempdir().unwrap();
        let skills_dir = dir.path().join("skills").join("big-skill");
        std::fs::create_dir_all(&skills_dir).unwrap();
        std::fs::write(skills_dir.join("SKILL.md"), "---\nname: big-skill\n---\n").unwrap();
        std::fs::write(dir.path().join("skills").join("README.md"), "# Skills\n").unwrap();

        let scan = scan_with_skills(
            dir.path().to_path_buf(),
            vec![SkillMeta {
                name: Some("big-skill".to_string()),
                description: None,
                trigger: None,
                path: PathBuf::from("skills/big-skill/SKILL.md"),
                char_count: 20_000,
                line_count: 550,
                has_references_dir: true,
            }],
        );

        let diags = SkillStructure.check(&scan, dir.path(), &empty_config());
        assert!(!diags.iter().any(|d| d.message.contains("references/")));
    }

    #[test]
    fn test_is_kebab_case() {
        assert!(is_kebab_case("my-skill"));
        assert!(is_kebab_case("review"));
        assert!(is_kebab_case("code-review-2"));
        assert!(!is_kebab_case("MySkill"));
        assert!(!is_kebab_case("my_skill"));
        assert!(!is_kebab_case("-leading"));
        assert!(!is_kebab_case("trailing-"));
        assert!(!is_kebab_case(""));
    }
}
