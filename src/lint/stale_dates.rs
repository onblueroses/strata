use crate::config::StrataConfig;
use crate::lint::{Diagnostic, LintRule, Severity, now_epoch_secs, parse_yyyy_mm_dd};
use crate::scanner::ProjectScan;
use std::path::Path;

pub struct StaleDates;

impl LintRule for StaleDates {
    fn name(&self) -> &'static str {
        "stale-dates"
    }

    fn severity(&self) -> Severity {
        Severity::Warning
    }

    fn check(&self, scan: &ProjectScan, root: &Path, config: &StrataConfig) -> Vec<Diagnostic> {
        let now = now_epoch_secs();
        let verified_threshold = u64::from(config.lint.stale_verified_days) * 86400;
        let updated_threshold = u64::from(config.lint.stale_updated_days) * 86400;
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
                    verified_threshold,
                    updated_threshold,
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
    verified_threshold: u64,
    updated_threshold: u64,
    diagnostics: &mut Vec<Diagnostic>,
) {
    for (line_num, line) in content.lines().enumerate() {
        let trimmed = line.trim();

        // last_verified: YYYY-MM-DD
        if let Some(rest) = trimmed.strip_prefix("last_verified:") {
            if let Some(age) = date_age(rest.trim(), now) {
                if age > verified_threshold {
                    let days = age / 86400;
                    diagnostics.push(
                        Diagnostic::new(
                            "stale-dates",
                            Severity::Warning,
                            format!(
                                "last_verified is {days} day(s) old (threshold: {} days)",
                                verified_threshold / 86400
                            ),
                            location,
                        )
                        .with_span(line_num as u32 + 1, 1),
                    );
                }
            }
            continue;
        }

        // _Last updated: YYYY-MM-DD_ (with or without italic markers)
        let updated_date = trimmed
            .strip_prefix("_Last updated:")
            .or_else(|| trimmed.strip_prefix("Last updated:"))
            .or_else(|| trimmed.strip_prefix("last_updated:"));

        if let Some(rest) = updated_date {
            let cleaned = rest.trim().trim_end_matches('_');
            if let Some(age) = date_age(cleaned, now) {
                if age > updated_threshold {
                    let days = age / 86400;
                    diagnostics.push(
                        Diagnostic::new(
                            "stale-dates",
                            Severity::Warning,
                            format!(
                                "Last updated is {days} day(s) old (threshold: {} days)",
                                updated_threshold / 86400
                            ),
                            location,
                        )
                        .with_span(line_num as u32 + 1, 1),
                    );
                }
            }
        }
    }
}

fn date_age(text: &str, now: u64) -> Option<u64> {
    // Extract first YYYY-MM-DD pattern from the text
    let date_str = text.split_whitespace().next()?;
    let epoch = parse_yyyy_mm_dd(date_str)?;
    Some(now.saturating_sub(epoch))
}

#[cfg(test)]
#[expect(clippy::expect_used, reason = "test code")]
mod tests {
    use super::*;

    fn now_fixed() -> u64 {
        parse_yyyy_mm_dd("2026-03-19").expect("test date")
    }

    #[test]
    fn stale_verified_produces_diagnostic() {
        let mut diags = Vec::new();
        let content = "# Entity\n## Status\nlast_verified: 2026-03-01\n";
        check_file_content(
            "test.md",
            content,
            now_fixed(),
            7 * 86400,
            60 * 86400,
            &mut diags,
        );
        assert_eq!(diags.len(), 1);
        assert!(diags[0].message.contains("18 day(s) old"));
        assert_eq!(diags[0].line, Some(3));
    }

    #[test]
    fn recent_verified_no_diagnostic() {
        let mut diags = Vec::new();
        let content = "last_verified: 2026-03-18\n";
        check_file_content(
            "test.md",
            content,
            now_fixed(),
            7 * 86400,
            60 * 86400,
            &mut diags,
        );
        assert!(diags.is_empty());
    }

    #[test]
    fn stale_last_updated_uses_updated_threshold() {
        let mut diags = Vec::new();
        let content = "_Last updated: 2025-12-01_\n";
        check_file_content(
            "test.md",
            content,
            now_fixed(),
            7 * 86400,
            60 * 86400,
            &mut diags,
        );
        assert_eq!(diags.len(), 1);
        assert!(diags[0].message.contains("Last updated"));
    }

    #[test]
    fn unparseable_date_no_diagnostic() {
        let mut diags = Vec::new();
        let content = "last_verified: not-a-date\n";
        check_file_content(
            "test.md",
            content,
            now_fixed(),
            7 * 86400,
            60 * 86400,
            &mut diags,
        );
        assert!(diags.is_empty());
    }

    #[test]
    fn recent_last_updated_no_diagnostic() {
        let mut diags = Vec::new();
        let content = "_Last updated: 2026-03-15_\n";
        check_file_content(
            "test.md",
            content,
            now_fixed(),
            7 * 86400,
            60 * 86400,
            &mut diags,
        );
        assert!(diags.is_empty());
    }

    #[test]
    fn custom_thresholds_respected() {
        let mut diags = Vec::new();
        // With a 30-day threshold, 18 days ago should NOT trigger
        let content = "last_verified: 2026-03-01\n";
        check_file_content(
            "test.md",
            content,
            now_fixed(),
            30 * 86400,
            60 * 86400,
            &mut diags,
        );
        assert!(diags.is_empty());
    }
}
