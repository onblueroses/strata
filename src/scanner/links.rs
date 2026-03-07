/// A parsed crosslink with its source location in the file.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct LinkInfo {
    pub target: String,
    pub line: u32,
    pub column: u32,
}

/// Build a table mapping byte offset -> (1-based line, 1-based column).
fn build_line_starts(content: &str) -> Vec<usize> {
    let mut starts = vec![0];
    for (i, b) in content.bytes().enumerate() {
        if b == b'\n' {
            starts.push(i + 1);
        }
    }
    starts
}

fn offset_to_line_col(line_starts: &[usize], offset: usize) -> (u32, u32) {
    let line_idx = match line_starts.binary_search(&offset) {
        Ok(i) => i,
        Err(i) => i.saturating_sub(1),
    };
    let col = offset - line_starts[line_idx];
    ((line_idx + 1) as u32, (col + 1) as u32)
}

/// Parse crosslinks from file content, returning target paths with source positions.
/// Supports:
/// - Markdown links: `[text](path)`
/// - Wiki links: `[[path]]`
///
/// Skips links inside fenced code blocks and inline code spans.
/// Skips absolute URL-style paths (starting with `/`).
pub fn parse_links(content: &str) -> Vec<LinkInfo> {
    let cleaned = strip_code_regions(content);
    let line_starts = build_line_starts(content);
    let mut links = Vec::new();
    let mut seen = std::collections::HashSet::new();

    let bytes = cleaned.as_bytes();
    let len = bytes.len();
    let mut i = 0;

    while i < len {
        if bytes[i] == b'[' {
            let link_start = i;

            // Wiki links: [[path]] or [[path|display]]
            if i + 1 < len && bytes[i + 1] == b'[' {
                if let Some(end) = cleaned[i + 2..].find("]]") {
                    let target = &cleaned[i + 2..i + 2 + end];
                    if !target.is_empty() && !target.contains("://") {
                        let target = target.split('|').next().unwrap_or(target);
                        if !target.starts_with('/') && seen.insert(target.to_string()) {
                            let (line, col) = offset_to_line_col(&line_starts, link_start);
                            links.push(LinkInfo {
                                target: target.to_string(),
                                line,
                                column: col,
                            });
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
                        if !target.is_empty() && seen.insert(target.to_string()) {
                            let (line, col) = offset_to_line_col(&line_starts, link_start);
                            links.push(LinkInfo {
                                target: target.to_string(),
                                line,
                                column: col,
                            });
                        }
                    }
                    i = j + 2 + end + 1;
                    continue;
                }
            }
        }
        i += 1;
    }

    links.sort_by(|a, b| a.target.cmp(&b.target));
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

    fn targets(links: &[LinkInfo]) -> Vec<&str> {
        links.iter().map(|l| l.target.as_str()).collect()
    }

    #[test]
    fn test_markdown_links() {
        let content = "See [config](config/settings.toml) and [docs](01-Core/README.md).";
        let links = parse_links(content);
        let t = targets(&links);
        assert!(t.contains(&"config/settings.toml"));
        assert!(t.contains(&"01-Core/README.md"));
    }

    #[test]
    fn test_wiki_links() {
        let content = "Related: [[01-Core/README.md]] and [[config/settings.toml]]";
        let links = parse_links(content);
        let t = targets(&links);
        assert!(t.contains(&"01-Core/README.md"));
        assert!(t.contains(&"config/settings.toml"));
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
        assert!(targets(&links).contains(&"README.md"));
    }

    #[test]
    fn test_wiki_link_with_display() {
        let content = "See [[path/to/file.md|Display Text]]";
        let links = parse_links(content);
        assert!(targets(&links).contains(&"path/to/file.md"));
    }

    #[test]
    fn test_ignores_links_in_fenced_code_blocks() {
        let content =
            "Before\n```\n[link](some/path.md)\n[[wiki-link]]\n```\nAfter [real](real.md)";
        let links = parse_links(content);
        assert_eq!(targets(&links), vec!["real.md"]);
    }

    #[test]
    fn test_ignores_links_in_inline_code() {
        let content = "Use `[link](some/path.md)` for links. See [real](real.md).";
        let links = parse_links(content);
        assert_eq!(targets(&links), vec!["real.md"]);
    }

    #[test]
    fn test_ignores_absolute_url_paths() {
        let content = "See [page](/wissen/denkmal-afa) and [local](docs/readme.md)";
        let links = parse_links(content);
        assert_eq!(targets(&links), vec!["docs/readme.md"]);
    }

    #[test]
    fn test_ignores_wiki_links_with_absolute_paths() {
        let content = "See [[/absolute/path]] and [[relative/path]]";
        let links = parse_links(content);
        assert_eq!(targets(&links), vec!["relative/path"]);
    }

    #[test]
    fn test_tilde_fenced_code_blocks() {
        let content = "~~~\n[link](hidden.md)\n~~~\n[visible](shown.md)";
        let links = parse_links(content);
        assert_eq!(targets(&links), vec!["shown.md"]);
    }

    #[test]
    fn test_link_positions() {
        let content = "Line 1\n[link](target.md)\nLine 3";
        let links = parse_links(content);
        assert_eq!(links.len(), 1);
        assert_eq!(links[0].line, 2);
        assert_eq!(links[0].column, 1);
    }

    #[test]
    fn test_wiki_link_position() {
        let content = "Some text [[wiki-target]]";
        let links = parse_links(content);
        assert_eq!(links.len(), 1);
        assert_eq!(links[0].line, 1);
        assert_eq!(links[0].column, 11);
    }
}
