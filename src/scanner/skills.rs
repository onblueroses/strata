use crate::error::Result;
use std::path::{Path, PathBuf};

/// Metadata extracted from a skill's SKILL.md frontmatter.
#[derive(Debug, Clone)]
pub struct SkillMeta {
    /// Skill name from frontmatter `name:` field.
    pub name: Option<String>,
    /// One-line description from frontmatter `description:` field.
    pub description: Option<String>,
    /// Trigger condition from frontmatter `trigger:` field.
    #[cfg_attr(
        not(test),
        expect(dead_code, reason = "parsed for future skill execution support")
    )]
    pub(crate) trigger: Option<String>,
    /// Relative path to SKILL.md from project root.
    pub path: PathBuf,
    /// Total character count of the SKILL.md file.
    pub char_count: usize,
    /// Total line count of the SKILL.md file.
    pub line_count: usize,
    /// Whether a `references/` subdirectory exists alongside SKILL.md.
    pub has_references_dir: bool,
}

/// Parse a single SKILL.md file into `SkillMeta`.
pub fn parse_skill(path: &Path, relative_path: PathBuf) -> Result<SkillMeta> {
    let content = std::fs::read_to_string(path)?;
    let char_count = content.len();
    let line_count = content.lines().count();
    let has_references_dir = path.parent().is_some_and(|p| p.join("references").is_dir());

    let mut name = None;
    let mut description = None;
    let mut trigger = None;
    let mut in_frontmatter = false;

    for (i, line) in content.lines().enumerate() {
        let trimmed = line.trim();

        // Detect YAML frontmatter boundaries
        if trimmed == "---" {
            if i == 0 {
                in_frontmatter = true;
                continue;
            } else if in_frontmatter {
                break; // end of frontmatter
            }
        }

        if !in_frontmatter {
            continue;
        }

        if let Some(value) = trimmed.strip_prefix("name:") {
            name = Some(
                value
                    .trim()
                    .trim_matches('"')
                    .trim_matches('\'')
                    .to_string(),
            );
        } else if let Some(value) = trimmed.strip_prefix("description:") {
            description = Some(
                value
                    .trim()
                    .trim_matches('"')
                    .trim_matches('\'')
                    .to_string(),
            );
        } else if let Some(value) = trimmed.strip_prefix("trigger:") {
            trigger = Some(
                value
                    .trim()
                    .trim_matches('"')
                    .trim_matches('\'')
                    .to_string(),
            );
        }
    }

    Ok(SkillMeta {
        name,
        description,
        trigger,
        path: relative_path,
        char_count,
        line_count,
        has_references_dir,
    })
}

/// Scan `skills/*/SKILL.md` under the project root.
pub fn scan_skills(root: &Path) -> Vec<SkillMeta> {
    let skills_dir = root.join("skills");
    if !skills_dir.is_dir() {
        return Vec::new();
    }

    let mut skills = Vec::new();

    let Ok(entries) = std::fs::read_dir(&skills_dir) else {
        return Vec::new();
    };

    for entry in entries.flatten() {
        let entry_path = entry.path();
        if !entry_path.is_dir() {
            continue;
        }
        let skill_md = entry_path.join("SKILL.md");
        if !skill_md.exists() {
            continue;
        }

        let relative = skill_md
            .strip_prefix(root)
            .unwrap_or(&skill_md)
            .to_path_buf();

        if let Ok(meta) = parse_skill(&skill_md, relative) {
            skills.push(meta);
        }
    }

    skills.sort_by(|a, b| a.path.cmp(&b.path));
    skills
}

#[cfg(test)]
#[expect(clippy::unwrap_used, reason = "test code")]
mod tests {
    use super::*;

    #[test]
    fn test_parse_skill_full_frontmatter() {
        let dir = tempfile::tempdir().unwrap();
        let skill_md = dir.path().join("SKILL.md");
        std::fs::write(
            &skill_md,
            r"---
name: my-skill
description: A useful skill for testing
trigger: when user asks about testing
---

# My Skill

Body content here.
",
        )
        .unwrap();

        let meta = parse_skill(&skill_md, PathBuf::from("skills/my-skill/SKILL.md")).unwrap();
        assert_eq!(meta.name.as_deref(), Some("my-skill"));
        assert_eq!(
            meta.description.as_deref(),
            Some("A useful skill for testing")
        );
        assert_eq!(
            meta.trigger.as_deref(),
            Some("when user asks about testing")
        );
        assert!(meta.char_count > 0);
        assert!(meta.line_count > 0);
        assert!(!meta.has_references_dir);
    }

    #[test]
    fn test_parse_skill_with_references_dir() {
        let dir = tempfile::tempdir().unwrap();
        let skill_dir = dir.path().join("my-skill");
        std::fs::create_dir_all(skill_dir.join("references")).unwrap();
        let skill_md = skill_dir.join("SKILL.md");
        std::fs::write(
            &skill_md,
            "---\nname: my-skill\ndescription: Has refs\n---\n",
        )
        .unwrap();

        let meta = parse_skill(&skill_md, PathBuf::from("skills/my-skill/SKILL.md")).unwrap();
        assert!(meta.has_references_dir);
    }

    #[test]
    fn test_parse_skill_missing_fields() {
        let dir = tempfile::tempdir().unwrap();
        let skill_md = dir.path().join("SKILL.md");
        std::fs::write(
            &skill_md,
            r"---
name: minimal
---

# Minimal Skill
",
        )
        .unwrap();

        let meta = parse_skill(&skill_md, PathBuf::from("skills/minimal/SKILL.md")).unwrap();
        assert_eq!(meta.name.as_deref(), Some("minimal"));
        assert!(meta.description.is_none());
        assert!(meta.trigger.is_none());
    }

    #[test]
    fn test_parse_skill_no_frontmatter() {
        let dir = tempfile::tempdir().unwrap();
        let skill_md = dir.path().join("SKILL.md");
        std::fs::write(
            &skill_md,
            "# A skill without frontmatter\n\nJust content.\n",
        )
        .unwrap();

        let meta = parse_skill(&skill_md, PathBuf::from("skills/nofm/SKILL.md")).unwrap();
        assert!(meta.name.is_none());
        assert!(meta.description.is_none());
    }

    #[test]
    fn test_scan_skills_empty() {
        let dir = tempfile::tempdir().unwrap();
        // No skills/ directory at all
        let skills = scan_skills(dir.path());
        assert!(skills.is_empty());
    }

    #[test]
    fn test_scan_skills_two_skills() {
        let dir = tempfile::tempdir().unwrap();
        let skills_dir = dir.path().join("skills");

        // Create two skill directories
        let skill_a = skills_dir.join("alpha");
        let skill_b = skills_dir.join("beta");
        std::fs::create_dir_all(&skill_a).unwrap();
        std::fs::create_dir_all(&skill_b).unwrap();

        std::fs::write(
            skill_a.join("SKILL.md"),
            "---\nname: alpha\ndescription: First skill\n---\n",
        )
        .unwrap();
        std::fs::write(
            skill_b.join("SKILL.md"),
            "---\nname: beta\ndescription: Second skill\n---\n",
        )
        .unwrap();

        let skills = scan_skills(dir.path());
        assert_eq!(skills.len(), 2);
        assert_eq!(skills[0].name.as_deref(), Some("alpha"));
        assert_eq!(skills[1].name.as_deref(), Some("beta"));
    }
}
