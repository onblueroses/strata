/// Extract a description from file content.
/// Tries YAML frontmatter first, then falls back to first heading.
pub fn extract_description(content: &str) -> Option<String> {
    // Try YAML frontmatter
    if let Some(desc) = extract_yaml_description(content) {
        return Some(desc);
    }

    // Fallback: first heading
    extract_first_heading(content)
}

/// Parse YAML frontmatter block (between --- delimiters) and extract `description` field.
fn extract_yaml_description(content: &str) -> Option<String> {
    let trimmed = content.trim_start();
    if !trimmed.starts_with("---") {
        return None;
    }

    let after_first = &trimmed[3..];
    let end = after_first.find("\n---")?;
    let frontmatter = &after_first[..end];

    // Simple key: value parsing (avoids yaml dependency)
    for line in frontmatter.lines() {
        let line = line.trim();
        if let Some(rest) = line.strip_prefix("description:") {
            let value = rest.trim().trim_matches('"').trim_matches('\'');
            if !value.is_empty() {
                return Some(value.to_string());
            }
        }
    }

    None
}

/// Extract the text of the first markdown heading.
fn extract_first_heading(content: &str) -> Option<String> {
    for line in content.lines() {
        let trimmed = line.trim();
        if let Some(heading) = trimmed.strip_prefix('#') {
            let heading = heading.trim_start_matches('#').trim();
            if !heading.is_empty() {
                return Some(heading.to_string());
            }
        }
    }
    None
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_yaml_frontmatter() {
        let content = r"---
title: My File
description: This is a test file
---
# Content here
";
        assert_eq!(
            extract_description(content),
            Some("This is a test file".to_string())
        );
    }

    #[test]
    fn test_quoted_description() {
        let content = r#"---
description: "Quoted description"
---
"#;
        assert_eq!(
            extract_description(content),
            Some("Quoted description".to_string())
        );
    }

    #[test]
    fn test_heading_fallback() {
        let content = "# My Document\n\nSome content here.";
        assert_eq!(
            extract_description(content),
            Some("My Document".to_string())
        );
    }

    #[test]
    fn test_no_description() {
        let content = "Just some plain text without any structure.";
        assert_eq!(extract_description(content), None);
    }

    #[test]
    fn test_h2_heading() {
        let content = "## Second Level\n\nContent.";
        assert_eq!(
            extract_description(content),
            Some("Second Level".to_string())
        );
    }
}
