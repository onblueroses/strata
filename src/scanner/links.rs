/// Parse crosslinks from file content.
/// Supports:
/// - Markdown links: `[text](path)`
/// - Wiki links: `[[path]]`
///
/// Skips links inside fenced code blocks and inline code spans.
/// Skips absolute URL-style paths (starting with `/`).
pub fn parse_links(content: &str) -> Vec<String> {
    let cleaned = strip_code_regions(content);
    let mut links = Vec::new();

    let bytes = cleaned.as_bytes();
    let len = bytes.len();
    let mut i = 0;

    while i < len {
        if bytes[i] == b'[' {
            // Wiki links: [[path]] or [[path|display]]
            if i + 1 < len && bytes[i + 1] == b'[' {
                if let Some(end) = cleaned[i + 2..].find("]]") {
                    let target = &cleaned[i + 2..i + 2 + end];
                    if !target.is_empty() && !target.contains("://") {
                        let target = target.split('|').next().unwrap_or(target);
                        if !target.starts_with('/') {
                            links.push(target.to_string());
                        }
                    }
                    i = i + 2 + end + 2;
                    continue;
                }
            }

            // Markdown links: [text](path)
            // Find matching closing ]
            let mut depth = 1;
            let mut j = i + 1;
            while j < len {
                match bytes[j] {
                    b'[' => depth += 1,
                    b']' => {
                        depth -= 1;
                        if depth == 0 {
                            break;
                        }
                    }
                    _ => {}
                }
                j += 1;
            }

            // Check for ( immediately after ]
            if depth == 0 && j + 1 < len && bytes[j + 1] == b'(' {
                if let Some(end) = cleaned[j + 2..].find(')') {
                    let target = &cleaned[j + 2..j + 2 + end];
                    if !target.starts_with("http://")
                        && !target.starts_with("https://")
                        && !target.starts_with("mailto:")
                        && !target.starts_with('#')
                        && !target.starts_with('/')
                        && !target.is_empty()
                    {
                        // Strip any anchor
                        let target = target.split('#').next().unwrap_or(target);
                        if !target.is_empty() {
                            links.push(target.to_string());
                        }
                    }
                    i = j + 2 + end + 1;
                    continue;
                }
            }
        }
        i += 1;
    }

    links.sort();
    links.dedup();
    links
}

/// Determine the length (in bytes) of the UTF-8 character starting at `byte`.
fn utf8_char_len(byte: u8) -> usize {
    match byte {
        0xC0..=0xDF => 2,
        0xE0..=0xEF => 3,
        0xF0..=0xF7 => 4,
        _ => 1, // ASCII or continuation byte (advance one to resync)
    }
}

/// Remove fenced code blocks and inline code spans from content,
/// replacing them with spaces to preserve character offsets.
fn strip_code_regions(content: &str) -> String {
    let mut result = String::with_capacity(content.len());
    let lines: Vec<&str> = content.lines().collect();
    let mut in_fence = false;
    let mut fence_marker = "";

    for (idx, line) in lines.iter().enumerate() {
        if idx > 0 {
            result.push('\n');
        }

        if in_fence {
            if line.trim_start().starts_with(fence_marker)
                && line
                    .trim_start()
                    .trim_start_matches(fence_marker.chars().next().unwrap_or('`'))
                    .trim()
                    .is_empty()
            {
                in_fence = false;
            }
            // Replace fenced line with spaces
            for ch in line.chars() {
                if ch == '\t' {
                    result.push('\t');
                } else {
                    result.push(' ');
                }
            }
        } else {
            let trimmed = line.trim_start();
            if trimmed.starts_with("```") {
                in_fence = true;
                fence_marker = "```";
                for ch in line.chars() {
                    if ch == '\t' {
                        result.push('\t');
                    } else {
                        result.push(' ');
                    }
                }
            } else if trimmed.starts_with("~~~") {
                in_fence = true;
                fence_marker = "~~~";
                for ch in line.chars() {
                    if ch == '\t' {
                        result.push('\t');
                    } else {
                        result.push(' ');
                    }
                }
            } else {
                // Strip inline code spans
                result.push_str(&strip_inline_code(line));
            }
        }
    }

    result
}

/// Replace inline code spans (`...`) with spaces.
fn strip_inline_code(line: &str) -> String {
    let mut result = String::with_capacity(line.len());
    let bytes = line.as_bytes();
    let len = bytes.len();
    let mut i = 0;

    while i < len {
        if bytes[i] == b'`' {
            // Count consecutive backticks for the opening
            let start = i;
            while i < len && bytes[i] == b'`' {
                i += 1;
            }
            let tick_count = i - start;

            // Find matching closing backticks
            let mut found_close = false;
            let content_start = i;
            while i <= len - tick_count {
                if bytes[i] == b'`' {
                    let mut count = 0;
                    while i < len && bytes[i] == b'`' {
                        count += 1;
                        i += 1;
                    }
                    if count == tick_count {
                        // Replace the entire code span with spaces
                        for _ in 0..(i - start) {
                            result.push(' ');
                        }
                        found_close = true;
                        break;
                    }
                    // Not a match, continue searching
                } else {
                    i += 1;
                }
            }

            if !found_close {
                // No matching close - treat backticks as literal
                result.push_str(&line[start..content_start]);
                i = content_start;
            }
        } else {
            // Safe: after stripping code spans the remaining chars are link syntax
            // (ASCII brackets/parens/text). Non-ASCII bytes here are literal content
            // that should be preserved as-is via the source string.
            let ch_len = utf8_char_len(bytes[i]);
            let end = (i + ch_len).min(len);
            result.push_str(&line[i..end]);
            i = end;
        }
    }

    result
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

    #[test]
    fn test_ignores_links_in_fenced_code_blocks() {
        let content =
            "Before\n```\n[link](some/path.md)\n[[wiki-link]]\n```\nAfter [real](real.md)";
        let links = parse_links(content);
        assert_eq!(links, vec!["real.md"]);
    }

    #[test]
    fn test_ignores_links_in_inline_code() {
        let content = "Use `[link](some/path.md)` for links. See [real](real.md).";
        let links = parse_links(content);
        assert_eq!(links, vec!["real.md"]);
    }

    #[test]
    fn test_ignores_absolute_url_paths() {
        let content = "See [page](/wissen/denkmal-afa) and [local](docs/readme.md)";
        let links = parse_links(content);
        assert_eq!(links, vec!["docs/readme.md"]);
    }

    #[test]
    fn test_ignores_wiki_links_with_absolute_paths() {
        let content = "See [[/absolute/path]] and [[relative/path]]";
        let links = parse_links(content);
        assert_eq!(links, vec!["relative/path"]);
    }

    #[test]
    fn test_tilde_fenced_code_blocks() {
        let content = "~~~\n[link](hidden.md)\n~~~\n[visible](shown.md)";
        let links = parse_links(content);
        assert_eq!(links, vec!["shown.md"]);
    }
}
