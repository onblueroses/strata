use crate::config::StrataConfig;
use crate::lint::{Diagnostic, LintRule, Severity};
use crate::scanner::ProjectScan;
use std::path::Path;

pub struct DeadLinks;

impl LintRule for DeadLinks {
    fn name(&self) -> &'static str {
        "dead-links"
    }

    fn severity(&self) -> Severity {
        Severity::Error
    }

    fn check(&self, scan: &ProjectScan, _root: &Path, _config: &StrataConfig) -> Vec<Diagnostic> {
        scan.dead_links()
            .iter()
            .map(|(source, target)| Diagnostic {
                rule: self.name().to_string(),
                severity: self.severity(),
                message: format!("Dead crosslink to '{target}'"),
                location: source.to_string_lossy().replace('\\', "/"),
            })
            .collect()
    }
}
