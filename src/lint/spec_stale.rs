use crate::config::StrataConfig;
use crate::lint::{Diagnostic, LintRule, Severity};
use crate::scanner::ProjectScan;
use crate::scanner::specs::SpecStatus;
use std::path::Path;

pub struct SpecStale;

impl LintRule for SpecStale {
    fn name(&self) -> &'static str {
        "spec-stale"
    }

    fn severity(&self) -> Severity {
        Severity::Info
    }

    fn check(&self, scan: &ProjectScan, _root: &Path, config: &StrataConfig) -> Vec<Diagnostic> {
        let staleness_secs = u64::from(config.sessions.staleness_days) * 86400;
        let now = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .map_or(0, |d| d.as_secs());

        scan.specs
            .iter()
            .filter(|s| s.status == Some(SpecStatus::InProgress))
            .filter(|s| s.mtime_secs > 0 && now.saturating_sub(s.mtime_secs) > staleness_secs)
            .map(|s| {
                let days = (now - s.mtime_secs) / 86400;
                Diagnostic {
                    rule: self.name().to_string(),
                    severity: self.severity(),
                    message: format!(
                        "In-progress spec '{}' has not been modified in {days} day(s)",
                        s.name
                    ),
                    location: s.path.to_string_lossy().to_string(),
                }
            })
            .collect()
    }
}
