use crate::config::StrataConfig;
use crate::lint::{Diagnostic, LintRule, Severity, now_epoch_secs, parse_yyyy_mm_dd};
use crate::scanner::ProjectScan;
use std::path::Path;

pub struct WaitingMarkers;

impl LintRule for WaitingMarkers {
    fn name(&self) -> &'static str {
        "waiting-markers"
    }

    fn severity(&self) -> Severity {
        Severity::Warning
    }

    fn check(&self, scan: &ProjectScan, root: &Path, config: &StrataConfig) -> Vec<Diagnostic> {
        let now = now_epoch_secs();
        let threshold = u64::from(config.lint.stale_waiting_days) * 86400;
        let mut diagnostics = Vec::new();

        for file in &scan.files {
            if file.extension().is_some_and(|e| e == "md") {
                let abs = root.join(file);
                let Ok(content) = std::fs::read_to_string(&abs) else {
                    continue;
                };
                check_file_content(
                    file.to_string_lossy().as_ref(),
                    &content,
                    now,
                    threshold,
                    &mut diagnostics,
                );
            }
        }

        diagnostics
    }
}

fn check_file_content(
    location: &str,
    content: &str,
    now: u64,
    threshold: u64,
    diagnostics: &mut Vec<Diagnostic>,
) {
    for (line_num, line) in content.lines().enumerate() {
        let Some(waiting_start) = line.find("WAITING (") else {
            continue;
        };

        let after_paren = &line[waiting_start + "WAITING (".len()..];

        // Look for a YYYY-MM-DD date within the marker text (up to closing paren or 60 chars)
        let search_window = after_paren.find(')').map_or_else(
            || &after_paren[..after_paren.len().min(60)],
            |i| &after_paren[..i],
        );

        if let Some(epoch) = extract_date(search_window) {
            let age = now.saturating_sub(epoch);
            if age > threshold {
                let days = age / 86400;
                let marker_text: String = line[waiting_start..].chars().take(80).collect();
                diagnostics.push(
                    Diagnostic::new(
                        "waiting-markers",
                        Severity::Warning,
                        format!(
                            "WAITING marker is {days} day(s) old (threshold: {} days): {marker_text}",
                            threshold / 86400
                        ),
                        location,
                    )
                    .with_span(line_num as u32 + 1, waiting_start as u32 + 1),
                );
            }
        }
    }
}

/// Find the first YYYY-MM-DD date in a text fragment.
fn extract_date(text: &str) -> Option<u64> {
    // Skip optional "since " prefix
    let text = text.strip_prefix("since ").unwrap_or(text);

    for word in text.split_whitespace() {
        let cleaned = word.trim_matches(|c: char| !c.is_ascii_digit() && c != '-');
        if let Some(epoch) = parse_yyyy_mm_dd(cleaned) {
            return Some(epoch);
        }
    }
    None
}

#[cfg(test)]
#[expect(clippy::expect_used, reason = "test code")]
mod tests {
    use super::*;

    fn now_fixed() -> u64 {
        parse_yyyy_mm_dd("2026-03-19").expect("test date")
    }

    #[test]
    fn old_waiting_produces_diagnostic() {
        let mut diags = Vec::new();
        let content = "- Task item WAITING (partner reply, since 2026-01-15)\n";
        check_file_content("backlog.md", content, now_fixed(), 30 * 86400, &mut diags);
        assert_eq!(diags.len(), 1);
        assert!(diags[0].message.contains("63 day(s) old"));
    }

    #[test]
    fn recent_waiting_no_diagnostic() {
        let mut diags = Vec::new();
        let content = "- Task item WAITING (review, since 2026-03-10)\n";
        check_file_content("backlog.md", content, now_fixed(), 30 * 86400, &mut diags);
        assert!(diags.is_empty());
    }

    #[test]
    fn waiting_with_date_no_since() {
        let mut diags = Vec::new();
        let content = "Something WAITING (2025-12-01)\n";
        check_file_content("state.md", content, now_fixed(), 30 * 86400, &mut diags);
        assert_eq!(diags.len(), 1);
    }

    #[test]
    fn waiting_without_date_no_diagnostic() {
        let mut diags = Vec::new();
        let content = "Item WAITING (no date here)\n";
        check_file_content("file.md", content, now_fixed(), 30 * 86400, &mut diags);
        assert!(diags.is_empty());
    }

    #[test]
    fn custom_threshold_respected() {
        let mut diags = Vec::new();
        // 63 days old, but threshold is 90 - should not trigger
        let content = "- Task WAITING (since 2026-01-15)\n";
        check_file_content("file.md", content, now_fixed(), 90 * 86400, &mut diags);
        assert!(diags.is_empty());
    }
}
