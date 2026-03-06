use crate::config::StrataConfig;
use crate::lint::{Diagnostic, LintRule, Severity};
use crate::scanner::ProjectScan;
use crate::scanner::specs::SpecStatus;
use std::path::Path;

pub struct SpecOwnership;

impl LintRule for SpecOwnership {
    fn name(&self) -> &'static str {
        "spec-ownership"
    }

    fn severity(&self) -> Severity {
        Severity::Info
    }

    fn check(&self, scan: &ProjectScan, _root: &Path, config: &StrataConfig) -> Vec<Diagnostic> {
        if !config.specs.require_session_ownership {
            return Vec::new();
        }

        scan.specs
            .iter()
            .filter(|s| s.status == Some(SpecStatus::InProgress) && s.session_id.is_none())
            .map(|s| Diagnostic {
                rule: self.name().to_string(),
                severity: self.severity(),
                message: format!(
                    "In-progress spec '{}' has no Session field - ownership cannot be tracked",
                    s.name
                ),
                location: s.path.to_string_lossy().to_string(),
            })
            .collect()
    }
}
