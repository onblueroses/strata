/// Parse crosslinks from file content.
/// Supports:
/// - Markdown links: [text](path)
/// - Wiki links: [[path]]
pub fn parse_links(content: &str) -> Vec<String> {
    let mut links = Vec::new();

    // Markdown links: [text](path)
    // Skip external URLs (http://, https://, mailto:)
    let chars = content.char_indices().peekable();
    for (i, ch) in chars {
        if ch == '[' {
            // Find closing ]
            let mut depth = 1;
            let mut j = i + 1;
            for (idx, c) in content[i + 1..].char_indices() {
                match c {
                    '[' => depth += 1,
                    ']' => {
                        depth -= 1;
                        if depth == 0 {
                            j = i + 1 + idx;
                            break;
                        }
                    }
                    _ => {}
                }
            }
            // Check for ( immediately after ]
            if j + 1 < content.len() && content.as_bytes()[j + 1] == b'(' {
                if let Some(end) = content[j + 2..].find(')') {
                    let target = &content[j + 2..j + 2 + end];
                    if !target.starts_with("http://")
                        && !target.starts_with("https://")
                        && !target.starts_with("mailto:")
                        && !target.starts_with('#')
                        && !target.is_empty()
                    {
                        // Strip any anchor
                        let target = target.split('#').next().unwrap_or(target);
                        if !target.is_empty() {
                            links.push(target.to_string());
                        }
                    }
                }
            }
            // Wiki links: [[path]]
            if i + 1 < content.len() && content.as_bytes()[i + 1] == b'[' {
                if let Some(end) = content[i + 2..].find("]]") {
                    let target = &content[i + 2..i + 2 + end];
                    if !target.is_empty() && !target.contains("://") {
                        // Strip any pipe display text: [[path|display]]
                        let target = target.split('|').next().unwrap_or(target);
                        links.push(target.to_string());
                    }
                }
            }
        }
    }

    links.sort();
    links.dedup();
    links
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_markdown_links() {
        let content = "See [config](config/settings.toml) and [docs](01-Core/README.md).";
        let links = parse_links(content);
        assert!(links.contains(&"config/settings.toml".to_string()));
        assert!(links.contains(&"01-Core/README.md".to_string()));
    }

    #[test]
    fn test_wiki_links() {
        let content = "Related: [[01-Core/README.md]] and [[config/settings.toml]]";
        let links = parse_links(content);
        assert!(links.contains(&"01-Core/README.md".to_string()));
        assert!(links.contains(&"config/settings.toml".to_string()));
    }

    #[test]
    fn test_ignores_external_urls() {
        let content = "Visit [site](https://example.com) and [mail](mailto:test@example.com)";
        let links = parse_links(content);
        assert!(links.is_empty());
    }

    #[test]
    fn test_strips_anchors() {
        let content = "See [section](README.md#installation)";
        let links = parse_links(content);
        assert!(links.contains(&"README.md".to_string()));
    }

    #[test]
    fn test_wiki_link_with_display() {
        let content = "See [[path/to/file.md|Display Text]]";
        let links = parse_links(content);
        assert!(links.contains(&"path/to/file.md".to_string()));
    }
}
