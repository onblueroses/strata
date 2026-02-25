use crate::error::Result;
use std::path::Path;

/// Parsed content of a RULES.md file.
#[derive(Debug, Clone)]
#[expect(
    dead_code,
    reason = "purpose_text and boundaries_text are public API for future lint rules"
)]
pub struct DomainRules {
    pub has_purpose: bool,
    pub has_boundaries: bool,
    pub purpose_text: String,
    pub boundaries_text: String,
}

/// Parse a RULES.md file, checking for required sections.
pub fn parse_rules(path: &Path) -> Result<DomainRules> {
    let content = std::fs::read_to_string(path)?;

    let mut has_purpose = false;
    let mut has_boundaries = false;
    let mut purpose_text = String::new();
    let mut boundaries_text = String::new();
    let mut current_section: Option<&str> = None;

    for line in content.lines() {
        let trimmed = line.trim();

        if trimmed.starts_with("## ") || trimmed.starts_with("# ") {
            let heading = trimmed.trim_start_matches('#').trim().to_lowercase();

            if heading.contains("purpose") {
                has_purpose = true;
                current_section = Some("purpose");
                continue;
            } else if heading.contains("boundaries") || heading.contains("boundary") {
                has_boundaries = true;
                current_section = Some("boundaries");
                continue;
            }
            current_section = None;
        }

        match current_section {
            Some("purpose") => {
                if !trimmed.is_empty() {
                    if !purpose_text.is_empty() {
                        purpose_text.push('\n');
                    }
                    purpose_text.push_str(trimmed);
                }
            }
            Some("boundaries") => {
                if !trimmed.is_empty() {
                    if !boundaries_text.is_empty() {
                        boundaries_text.push('\n');
                    }
                    boundaries_text.push_str(trimmed);
                }
            }
            _ => {}
        }
    }

    Ok(DomainRules {
        has_purpose,
        has_boundaries,
        purpose_text,
        boundaries_text,
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_parse_complete_rules() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("RULES.md");
        std::fs::write(
            &path,
            r#"# Rules: Core

## Purpose
This domain contains the core business logic.

## Boundaries
- Only pure functions, no IO
- No external dependencies
"#,
        )
        .unwrap();

        let rules = parse_rules(&path).unwrap();
        assert!(rules.has_purpose);
        assert!(rules.has_boundaries);
        assert!(rules.purpose_text.contains("core business logic"));
    }

    #[test]
    fn test_parse_missing_sections() {
        let dir = tempfile::tempdir().unwrap();
        let path = dir.path().join("RULES.md");
        std::fs::write(&path, "# Rules: Test\n\nSome content without sections.\n").unwrap();

        let rules = parse_rules(&path).unwrap();
        assert!(!rules.has_purpose);
        assert!(!rules.has_boundaries);
    }
}
